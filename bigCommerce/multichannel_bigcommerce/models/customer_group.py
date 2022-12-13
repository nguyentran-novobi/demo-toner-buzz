import logging

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from odoo.addons.queue_job.exception import RetryableJobError
from ..utils.bigcommerce_customer_group_helper import BigcommerceCustomerGroupHelper, BigCommerceCustomerGroupImporter, BigcommerceCustomerGroupImportBuilder, RateLimit, ExportError
from odoo.addons.channel_base_sdk.utils.common.exceptions import EmptyDataError
from odoo.addons.multichannel_bigcommerce.utils.bigcommerce_api_helper import NotFoundError


_logger = logging.getLogger(__name__)


class CustomGroup(models.Model):
    _inherit = 'channel.customer.group'

    has_all_categories_access = fields.Boolean(string='Has all categories access')
    categ_ids = fields.Many2many('product.channel.category', string='Categories')
    channel_pricelist_id = fields.Many2one('channel.pricelist', string='Price list')

    @api.onchange('has_all_categories_access')
    def _onchange_has_all_categories_access(self):
        if self.has_all_categories_access:
            self.update({
                'categ_ids': [(5, 0, 0)]
            })

    @api.model
    def bigcommerce_get_data(self, channel_id, ids=[], all_records=False):
        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)

        def prepare_importer():
            res = BigCommerceCustomerGroupImporter()
            res.channel = channel
            res.ids = ids
            res.all_records = all_records
            return res

        def prepare_builder(customer_groups):
            res = BigcommerceCustomerGroupImportBuilder()
            res.customer_groups = customer_groups
            res.channel_id = channel_id
            return res

        def fetch_customer_group(gen):
            while True:
                try:
                    customer_group, categories_on_bigcommerce_ids = next(gen)
                    yield customer_group, categories_on_bigcommerce_ids
                except StopIteration:
                    break

        def check_enough_categories(categ_ids, customer_group):
            categories = self.env['product.channel.category'].search([('id_on_channel', 'in', categ_ids),
                                                                      ('channel_id', '=', channel_id)])
            customer_group.update({
                'categ_ids': [(6, 0, categories.ids)] if categories.ids else [(5, 0, 0)],
                'channel_id': channel_id
            })
            if categ_ids and len(categ_ids) != len(categories):
                raise ExportError("Cannot import Customer Group. Missing categories")

        uuids = []
        datas = []
        importer = prepare_importer()

        for pulled in importer.do_import():
            try:
                if pulled.data:
                    datas.extend(pulled.data)
                    builder = prepare_builder(pulled.data)
                    vals_list = list(fetch_customer_group(builder.prepare()))
                    for customer_group_vals, categories_on_bigcommerce_ids in vals_list:
                        try:
                            # Check enough categories
                            check_enough_categories(categories_on_bigcommerce_ids, customer_group_vals)

                            record = self.sudo().search([('channel_id', '=', channel_id),
                                                         ('id_on_channel', '=', customer_group_vals['id_on_channel'])], limit=1)
                            # If a record is already existed
                            existed_record = True if record else False

                            log = self._bigcommerce_log(message='', data=dict(data=customer_group_vals), status='draft',
                                                        channel_id=channel_id, operation_type='import_others',
                                                        data_operation='by_ids' if ids else 'all')

                            job_uuid = self.with_context(log_id=log.id).create_jobs_for_synching(vals=customer_group_vals,
                                                                                                 update=existed_record,
                                                                                                 record=record)
                            log.update({'job_uuid': job_uuid})
                            uuids.append(job_uuid)

                            self._cr.commit()
                        except ExportError as e:
                            self._bigcommerce_log(message=str(e), data=dict(data=pulled.data), status='failed',
                                                  channel_id=channel_id, operation_type='import_others',
                                                  data_operation='by_ids' if ids else 'all')
                else:
                    if pulled.last_response and not pulled.last_response.ok():
                        _logger.error('Error while importing customer groups: %s', pulled.last_response.get_error())
                        channel.sudo().disconnect()

                    self._bigcommerce_log(message=str(pulled.last_response.get_error()), data=dict(data=pulled.data), status='failed',
                                          channel_id=channel_id, operation_type='import_others',
                                          data_operation='by_ids' if ids else 'all')
            except ExportError as e:
                self._bigcommerce_log(message=str(e), data=dict(data=pulled.data), status='failed',
                                      channel_id=channel_id, operation_type='import_others',
                                      data_operation='by_ids' if ids else 'all')
            except EmptyDataError:
                continue
        return datas, uuids

    def _bigcommerce_export_customer_group(self):
        helper = BigcommerceCustomerGroupHelper(self.channel_id)
        if self.id_on_channel:
            try:
                helper.update(self)
            except NotFoundError:
                try:
                    res = helper.create(self)
                    if res.ok():
                        self.message_post(body="A new record is created successfully on online store.")
                        self.with_context(for_synching=True).update({
                            'id_on_channel': str(res.data['id'])
                        })
                except (RateLimit, ExportError) as e:
                    self.message_post(body=e)

        elif not self.id_on_channel:
            res = helper.create(self)
            if res.ok():
                self.with_context(for_synching=True).update({
                    'id_on_channel': str(res.data['id'])
                })
        self.update({'need_to_export': False})

    def bigcommerce_export_customer_group(self):
        self.ensure_one()
        try:
            self._bigcommerce_export_customer_group()
        except RateLimit as e:
            if 'job_uuid' in self.env.context:
                raise RetryableJobError("Retry exporting customer groups")
            else:
                raise ValidationError(e)
        except ExportError as e:
            raise ValidationError(_('Cannot export customer group to Bigcommerce: %s' % str(e)))

    @api.model
    def _bigcommerce_log(self, message, data, status, channel_id, operation_type, res_id=False, data_operation='all'):
        return self.env['omni.log'].create({
            'datas': data,
            'channel_id': channel_id,
            'operation_type': operation_type,
            'data_type_id': self.env.ref('multichannel_bigcommerce.channel_customer_group_data_type').id,
            'data_operation': data_operation,
            'res_id': res_id,
            'res_model': 'channel.customer.group',
            'status': status,
            'message': message,
        })

    def bigcommerce_export_customer_groups(self):
        for customer_group in self:
            data = BigcommerceCustomerGroupHelper.prepare_data(customer_group)
            log = self._bigcommerce_log(message='', data=data, status='draft', channel_id=customer_group.channel_id.id,
                                        operation_type='export_others', res_id=customer_group.id)
            job_uuid = customer_group.with_context(log_id=log.id).with_delay().bigcommerce_export_customer_group().uuid
            log.update({'job_uuid': job_uuid})

    def bigcommerce_delete_customer_group(self):
        self.ensure_one()
        try:
            helper = BigcommerceCustomerGroupHelper(self.channel_id)
            helper.delete(self.id_on_channel)
            self.update({'id_on_channel': False})
        except ExportError as e:
            raise ValidationError(_('Cannot delete customer group on Bigcommerce: %s' % str(e)))

    def unlink(self):
        invalid_records = self.filtered(lambda g: g.channel_pricelist_id)
        if invalid_records:
            raise ValidationError(_("Cannot delete selected customer group(s). There are associated pricelist(s)."))
        return super().unlink()
