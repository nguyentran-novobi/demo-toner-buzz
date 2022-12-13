# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

from ..utils import bigcommerce_pricelist_helper as pl_helper
from .product_channel import BULK_PRICING_DISCOUNT_TYPES


class ChannelPricelist(models.Model):
    _name = 'channel.pricelist'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Pricelist on Channel'

    name = fields.Char(required=True)
    pricelist_id = fields.Many2one('product.pricelist')
    channel_id = fields.Many2one('ecommerce.channel', string='Channel', required=True)
    channel_currency_ids = fields.Many2many(related='channel_id.currency_ids')
    currency_id = fields.Many2one('res.currency', string='Currency', domain="[('id', 'in', channel_currency_ids)]")
    rule_ids = fields.One2many('channel.pricelist.rule', 'pricelist_id')
    channel_customer_group_ids = fields.One2many('channel.customer.group', 'channel_pricelist_id',
                                                 string='Customer Groups')

    id_on_channel = fields.Char(string='ID on Store', copy=False)
    is_exported_to_store = fields.Boolean(string='Exported to Store', compute='_compute_is_exported_to_store')
    need_to_export = fields.Boolean(string='Need to Export', default=False)
    need_to_export_display = fields.Boolean(compute='_compute_need_to_export_display')

    is_published = fields.Boolean(string='Published on Storefront', default=False)
    is_sync_in_progress = fields.Boolean(default=False)

    def name_get(self):
        res = [
            (record.id, f'{record.name} ({record.currency_id.name})')
            for record in self
        ]
        return res

    @api.depends('id_on_channel')
    def _compute_is_exported_to_store(self):
        exported = self.filtered(lambda r: r.id_on_channel)
        exported.update({'is_exported_to_store': True})
        (self - exported).update({'is_exported_to_store': False})

    @api.depends('id_on_channel', 'need_to_export')
    def _compute_need_to_export_display(self):
        enabled = self.filtered(lambda r: r.is_exported_to_store and r.need_to_export)
        enabled.update({'need_to_export_display': True})
        (self - enabled).update({'need_to_export_display': False})

    @api.model
    def prepare_vals_from_master(self, pricelist, channel):
        method = '_prepare_%s_vals_from_master' % channel.platform
        return getattr(self, method)(pricelist, channel)

    @api.model
    def _prepare_bigcommerce_vals_from_master(self, pricelist, channel):
        helper = pl_helper.PricelistMaster2MappingMapper(pricelist, channel)
        res = helper.do_map()
        return res

    def export_to_channel(self):
        self.ensure_one()
        platform = self.channel_id.platform
        delayed_method = '%s_delayed_export_to_channel' % platform
        if hasattr(self, delayed_method) and not self.env.context.get('no_delay'):
            return getattr(self, delayed_method)()
        method = '%s_export_to_channel' % platform
        return getattr(self, method)()

    def bigcommerce_delayed_export_to_channel(self):
        self.ensure_one()
        self.with_context(for_synching=True).update({'is_sync_in_progress': True})
        return self.with_delay().bigcommerce_export_to_channel()

    def bigcommerce_export_to_channel(self):
        self.ensure_one()
        pl_helper.PricelistExportWorkflow.do_export(self)

    def _log_exceptions(self, title, exceptions):
        """
        Log exceptions on chatter
        :param exceptions: list of exceptions
        Each exception will include
        - title
        - reason
        """
        render_context = {
            'title': title,
            'exceptions': exceptions,
        }
        self._activity_schedule_with_view(
            'mail.mail_activity_data_warning',
            user_id=self.env.user.id,
            views_or_xmlid='multichannel_bigcommerce.exception_on_channel_pricelist',
            render_context=render_context
        )

    @api.model
    def channel_import_data(self, channel, ids, all_records):
        method = '{}_get_data'.format(channel.platform)
        if hasattr(self, method):
            getattr(self, method)(channel, ids=ids, all_records=all_records)

    @api.model
    def bigcommerce_get_data(self, channel, **kwargs):
        for delegate_vals in pl_helper.PricelistImportWorkflow.import_to_delegate(channel, **kwargs):
            self.delayed_process_import_data(delegate_vals, **kwargs)

    @api.model
    def delayed_process_import_data(self, delegate_vals, **kwargs):
        return self.with_delay().process_import_data(delegate_vals, **kwargs)

    @api.model
    def process_import_data(self, delegate_vals, **kwargs):
        pl_helper.PricelistDelegateWorkflow.save_delegate(self, delegate_vals, **kwargs)

    def write(self, vals):
        if not self.env.context.get('for_synching'):
            vals = {**{'need_to_export': True}, **vals}
        if 'channel_customer_group_ids' in vals:
            return super(ChannelPricelist, self.with_context(for_synching=True)).write(vals)
        return super().write(vals)


class ChannelPricelistRule(models.Model):
    _name = 'channel.pricelist.rule'
    _description = 'Rule of Pricelist on Channel'

    pricelist_id = fields.Many2one('channel.pricelist', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='pricelist_id.currency_id')
    channel_id = fields.Many2one(related='pricelist_id.channel_id')
    product_channel_variant_id = fields.Many2one(
        'product.channel.variant',
        string='Mapping Variant',
        required=True,
        ondelete='cascade',
        domain="[('channel_id', '=', channel_id)]",
    )

    product_default_code = fields.Char(string='Product SKU', related='product_channel_variant_id.default_code')
    product_lst_price = fields.Float(string='Product Base Price', related='product_channel_variant_id.lst_price')
    product_retail_price = fields.Float(string='Product MSRP', related='product_channel_variant_id.retail_price')
    product_sale_price = fields.Float(string='Product Sale Price', related='product_channel_variant_id.sale_price')

    is_override_lst_price = fields.Boolean(default=False)
    is_override_retail_price = fields.Boolean(default=False)
    is_override_sale_price = fields.Boolean(default=False)
    override_lst_price = fields.Float(string='Overriding Base Price', digits='Product Price')
    override_retail_price = fields.Float(string='Overriding MSRP', digits='Product Price')
    override_sale_price = fields.Float(string='Overriding Sale Price', digits='Product Price')

    lst_price = fields.Float(string='Base Price', compute='_compute_prices')
    retail_price = fields.Float(string='MSRP', compute='_compute_prices')
    sale_price = fields.Float(string='Sale Price', compute='_compute_prices')
    catalog_price = fields.Float(string='Catalog Price', compute='_compute_prices')

    bulk_pricing_discount_type = fields.Selection(
        selection=BULK_PRICING_DISCOUNT_TYPES,
        string='Bulk Pricing Discount Type',
        default='percent',
    )
    bulk_pricing_rule_ids = fields.One2many('product.bulk.pricing.rule', 'channel_pricelist_rule_id')

    @api.depends(
        'product_channel_variant_id',
        'is_override_lst_price',
        'is_override_retail_price',
        'is_override_sale_price',
        'override_lst_price',
        'override_retail_price',
        'override_sale_price',
    )
    def _compute_prices(self):
        price_fields = ('lst_price', 'retail_price', 'sale_price')
        for record in self:
            vals = {
                pf: record[f'override_{pf}'] if record[f'is_override_{pf}'] else record[f'product_{pf}']
                for pf in price_fields
            }

            if record.currency_id.compare_amounts(record.product_sale_price, 0) > 0:
                catalog_price = record.product_sale_price
            else:
                catalog_price = record.product_lst_price
            vals.update({
                'catalog_price': catalog_price
            })

            record.update(vals)
