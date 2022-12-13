# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import functools

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero

from .product_channel import BULK_PRICING_DISCOUNT_TYPES


class ProductBulkPricingRule(models.Model):
    _name = 'product.bulk.pricing.rule'
    _description = 'Product Bulk Pricing Rule'

    _parent_codes = {
        'mapping': 'product_channel_id',
        'pricelist': 'channel_pricelist_rule_id',
    }
    _parent_fields = ('product_channel_id', 'channel_pricelist_rule_id')
    _parent_related_fields = (
        'product_channel_id.bulk_pricing_discount_type',
        'product_channel_id.currency_id',
        'channel_pricelist_rule_id.bulk_pricing_discount_type',
        'channel_pricelist_rule_id.currency_id',
    )
    _parent_price_fields = (
        'product_channel_id.sale_price',
        'product_channel_id.lst_price',
        'channel_pricelist_rule_id.is_override_sale_price',
        'channel_pricelist_rule_id.override_sale_price',
        'channel_pricelist_rule_id.is_override_lst_price',
        'channel_pricelist_rule_id.override_lst_price',
        'channel_pricelist_rule_id.product_sale_price',
        'channel_pricelist_rule_id.product_lst_price',
    )

    product_channel_id = fields.Many2one('product.channel', ondelete='cascade')
    channel_pricelist_rule_id = fields.Many2one('channel.pricelist.rule', ondelete='cascade')
    default_price = fields.Float(compute='_compute_default_price')
    quantity_min = fields.Integer('Min Quantity')
    quantity_max = fields.Integer('Max Quantity')
    discount_type = fields.Selection(
        selection=BULK_PRICING_DISCOUNT_TYPES,
        compute='_compute_related_parent_fields',
    )
    discount_amount = fields.Float(
        'Discount Amount',
        help='This field changes behavior each time discount type changes.'
             '\n* % Discount: Discount in percentage, i.e.: 53 means 53% or 0.53.'
             '\n* Fixed Amount: Fixed amount in product currency.'
             '\n* Off/Unit: Amount Off per unit in product currency.'
    )
    discount_amount_percent = fields.Float(related='discount_amount', string='% Discount', readonly=False)
    discount_amount_fixed = fields.Float(related='discount_amount', string='Fixed Amount', readonly=False)
    discount_amount_price = fields.Float(related='discount_amount', string='Off/Unit', readonly=False)
    currency_id = fields.Many2one('res.currency', compute='_compute_related_parent_fields')
    unit_price = fields.Monetary('Unit Price', compute='_compute_unit_price')

    id_on_channel = fields.Char(string='ID on Store', copy=False)

    @api.depends(*_parent_fields, *_parent_price_fields)
    def _compute_default_price(self):
        for record in self:
            parent_code = record._get_parent_code()
            method = '_bigcommerce_%s_get_default_price' % parent_code
            record.default_price = getattr(record, method)()

    def _get_parent_code(self):
        for pc, pf in self._parent_codes.items():
            if self[pf]:
                return pc

    def _bigcommerce_mapping_get_default_price(self):
        self.ensure_one()
        mapping = self.product_channel_id
        if mapping.currency_id.compare_amounts(mapping.sale_price, 0) > 0:
            res = mapping.sale_price
        else:
            res = mapping.lst_price
        return res

    def _bigcommerce_pricelist_get_default_price(self):
        self.ensure_one()
        pricelist = self.channel_pricelist_rule_id
        if pricelist.is_override_sale_price:
            res = pricelist.override_sale_price
        elif pricelist.is_override_lst_price:
            res = pricelist.override_lst_price
        elif pricelist.currency_id.compare_amounts(pricelist.product_sale_price, 0) > 0 \
                if pricelist.currency_id \
                else pricelist.product_sale_price > 0:
            res = pricelist.product_sale_price
        else:
            res = pricelist.product_lst_price
        return res

    def _get_parent(self):
        return functools.reduce(lambda x, y: x or y, (self[pf] for pf in self._parent_fields))

    @api.depends(
        *_parent_fields,
        *_parent_price_fields,
        'discount_amount_percent',
        'discount_amount_fixed',
        'discount_amount_price',
        'discount_type',
    )
    def _compute_unit_price(self):
        for record in self:
            if record.discount_type == 'percent':
                record.unit_price = record.default_price * (1 - record.discount_amount_percent / 100.0)
            elif record.discount_type == 'fixed':
                record.unit_price = record.discount_amount_fixed
            else:  # discount_type is price
                record.unit_price = max(record.default_price - record.discount_amount_price, 0.0)

    @api.depends(
        *_parent_fields,
        *_parent_related_fields,
    )
    def _compute_related_parent_fields(self):
        for record in self:
            parent_code = record._get_parent_code()
            method = '_%s_get_related_fields' % parent_code
            vals = getattr(record, method)()
            record.update(vals)

    def _mapping_get_related_fields(self):
        self.ensure_one()
        mapping = self.product_channel_id
        return {
            'discount_type': mapping.bulk_pricing_discount_type,
            'currency_id': mapping.currency_id.id,
        }

    def _pricelist_get_related_fields(self):
        self.ensure_one()
        pricelist = self.channel_pricelist_rule_id
        return {
            'discount_type': pricelist.bulk_pricing_discount_type,
            'currency_id': pricelist.currency_id.id,
        }

    @api.constrains(*_parent_fields)
    def _check_single_parent(self):
        for record in self:
            parent_count = sum(1 for pf in self._parent_fields if record[pf])
            if parent_count != 1:
                raise ValidationError(_('This bulk pricing rule does not attach to a particular rule!'))

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = self._adjust_related_empty_amounts_list(vals_list)
        res = super().create(vals_list)
        return res

    @api.model
    def _adjust_related_empty_amounts_list(self, vals_list):
        return list(map(self._adjust_related_empty_amounts, vals_list))

    @api.model
    def _adjust_related_empty_amounts(self, vals):
        related_amount_fields = ['discount_amount_percent', 'discount_amount_fixed', 'discount_amount_price']
        res = {
            k: v
            for k, v in vals.items()
            if k not in related_amount_fields or not float_is_zero(v, precision_digits=5)
        }
        return res
