# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from functools import *

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.channel_base_sdk.utils.common.exceptions import EmptyDataError
from odoo.addons.queue_job.exception import RetryableJobError
from odoo.addons.multichannel_bigcommerce.utils.bigcommerce_api_helper import RateLimit, ExportError, NotFoundError
from ..utils.bigcommerce_category_helper import BigcommerceCategoryHelper, BigCommerceCategoryImporter, \
    BigcommerceCategoryImportBuilder


_logger = logging.getLogger(__name__)


class ProductChannelCategory(models.Model):
    _inherit = "product.channel.category"

    bc_default_product_sort = fields.Selection([
        ('use_store_settings', 'Use Store Settings Default'),
        ('featured', 'Featured'),
        ('newest', 'Newest'),
        ('best_selling', 'Best selling'),
        ('alpha_asc', 'Alpha ASC'),
        ('alpha_desc', 'Alpha DESC'),
        ('avg_customer_review', 'Average Customer Review'),
        ('price_asc', 'Price ASC'),
        ('price_desc', 'Price DESC'),
    ], default='use_store_settings', string='Default Product Sort')

    @api.model
    def bigcommerce_get_data(self, channel_id, ids=[], all_records=False):
        """
        :param vals:
        [tree-form categories from api]
        :return:
        """
        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)

        def prepare_importer():
            res = BigCommerceCategoryImporter()
            res.channel = channel
            res.ids = ids
            res.all_records = all_records
            return res

        def prepare_tree_builder(categories, existed_records, category_ids):
            res = BigcommerceCategoryImportBuilder()

            existing_categories = existed_records.mapped('id_on_channel')
            new_options = list(filter(lambda x: x not in existing_categories, category_ids))

            res.channel_id = channel_id
            res.categories = categories
            res.existed_records = existed_records
            res.existing_categories = existing_categories
            res.new_options = new_options
            return res

        def prepare_detail_builder(categories):
            res = BigcommerceCategoryImportBuilder()
            res.categories = categories
            return res

        def fetch_category(gen):
            while True:
                try:
                    category = next(gen)
                    yield category
                except StopIteration:
                    break

        importer = prepare_importer()
        datas = importer.do_tree_import().data
        datas_all = []

        def flatten_tree(category):
            return ([y for x in category['children'] for y in flatten_tree(x)] + [category]) if category['children'] else [category]

        try:
            # get all category ids
            all_categories = list(reduce(lambda x, y: x + flatten_tree(y), datas, []))
            category_ids = [str(x['id']) for x in all_categories]
            existed_records = self.sudo().search([('id_on_channel', 'in', category_ids),
                                                  ('channel_id.id', '=', channel_id)])
            builder = prepare_tree_builder(datas, existed_records, category_ids)
            new_results, existing_results = builder.prepare_tree()
            if new_results:
                existed_records += self.with_context(for_synching=True).sudo().create(new_results)
            for vals in existing_results:
                record = existed_records.filtered(lambda r: r['id_on_channel'] == vals['id_on_channel'])
                record.with_context(for_synching=True).sudo().write(vals)

            for pulled in importer.do_detail_import():
                try:
                    if pulled.data:
                        datas_all.extend(pulled.data)
                        builder = prepare_detail_builder(pulled.data)
                        vals_list = list(fetch_category(builder.prepare_detail()))
                        for category_vals in vals_list:
                            record = self.sudo().search([('channel_id.id', '=', channel_id),
                                                         ('id_on_channel', '=', str(category_vals['id_on_channel']))], limit=1)
                            record.with_context(for_synching=True).update(category_vals)
                except EmptyDataError:
                    pass

            self._bigcommerce_log(message='', data=dict(data=datas_all), status='done', channel_id=channel_id,
                                  operation_type='import_others')
            return existed_records
        except Exception as e:
            _logger.exception(e)
            self._bigcommerce_log(message=str(e), data=dict(data=datas_all), status='failed', channel_id=channel_id,
                                  operation_type='import_others')

    @api.model
    def _bigcommerce_log(self, message, data, status, channel_id, operation_type, res_id=False):
        return self.env['omni.log'].create({
            'datas': data,
            'channel_id': channel_id,
            'operation_type': operation_type,
            'data_type_id': self.env.ref('multichannel_bigcommerce.channel_category_data_type').id,
            'data_operation': 'all',
            'res_id': res_id,
            'res_model': 'product.channel.category',
            'status': status,
            'message': message,
        })

    def _bigcommerce_export_category(self):
        helper = BigcommerceCategoryHelper(self.channel_id)
        if self.parent_id:
            self.parent_id._bigcommerce_export_category()
        if self.id_on_channel:
            try:
                helper.update(self)
            except NotFoundError:
                try:
                    res = helper.create(self)
                    if res.ok():
                        self.message_post(body="A new record is created successfully on online store.")
                        self.with_context(for_synching=True).update({
                            'id_on_channel': str(res.data['id']),
                        })
                except (RateLimit, ExportError) as e:
                    self.message_post(body=e)
        elif not self.id_on_channel:
            res = helper.create(self)
            if res.ok():
                self.with_context(for_synching=True).update({
                    'id_on_channel': str(res.data['id']),
                })
        self.with_context(for_synching=True).update({'need_to_export': False})

    def bigcommerce_export_category(self):
        self.ensure_one()
        try:
            self._bigcommerce_export_category()

        except RateLimit as e:
            if 'job_uuid' in self.env.context:
                raise RetryableJobError("Retry exporting categories")
            else:
                raise ValidationError(e)
        except ExportError as e:
            raise ValidationError(_('Cannot export category to Bigcommerce: %s' % str(e)))

    def bigcommerce_export_categories(self):
        for category in self:
            data = BigcommerceCategoryHelper.prepare_data(category)
            log = self._bigcommerce_log(message='', data=data, status='draft', channel_id=category.channel_id.id,
                                        operation_type='export_others', res_id=category.id)
            job_uuid = category.with_context(log_id=log.id).with_delay().bigcommerce_export_category().uuid
            log.update({'job_uuid': job_uuid})
