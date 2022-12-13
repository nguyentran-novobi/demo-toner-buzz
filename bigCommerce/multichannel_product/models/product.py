# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
import base64
import requests

from io import BytesIO

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

from ..utils.unit_converter import UnitConverter
from .product_template import BASE_VALUE

_logger = logging.getLogger(__name__)

FACTOR = {
    'FT-IN': 12,
    'LB-OZ': 16
}


class ProductProduct(models.Model):
    _inherit = "product.product"

    product_channel_variant_ids = fields.One2many('product.channel.variant', 'product_product_id',
                                                  string='Product Channel Variants')
    product_alternate_sku_ids = fields.One2many('product.alternate.sku', 'product_product_id',
                                                string='Product Alternate SKUs')

    retail_price = fields.Float(string='Retail Price')
    variant_price = fields.Float(string='Variant Price')
    depth = fields.Float(string='Depth')
    height = fields.Float(string='Height')
    width = fields.Float(string='Width')
    weight = fields.Float(inverse='_set_weight')
    weight_in_oz = fields.Float(
        string='Weight in oz',
        copy=False,
        readonly=True,
        inverse='_set_weight_in_oz',
        digits='Stock Weight',
    )

    gtin = fields.Char(string='Global Trade Item Number', readonly=False)
    upc = fields.Char(string='UPC', readonly=False)
    ean = fields.Char(string='EAN', readonly=False)
    isbn = fields.Char(string='ISBN', readonly=False)
    mpn = fields.Char(string='MPN')
    
    dimensions = fields.Char(string='Dimensions', compute='_compute_dimensions')
    is_custom_product = fields.Boolean('Custom Product', default=False, copy=False)

    @api.onchange('default_code')
    def _onchange_default_code(self):
        if self.product_channel_variant_ids:
            return {'warning': {
                'message': _(
                    "There are some Product Mappings which have %s as SKU. Changing the Internal Reference will delete all of them.",
                    self._origin.default_code),
            }}
        super()._onchange_default_code()

    def _compute_dimensions(self):
        for record in self:
            record.dimensions = f'{record.width}x{record.depth}x{record.height}'

    def check_unique_default_code(self):
        for record in self:
            if record.default_code:
                res = self.sudo().search([('default_code', '=', record.default_code)], limit=2)
                if len(res) > 1:
                    raise ValidationError(_('The SKU must be unique, this one is already assigned to another product.'))

    @api.constrains('upc', 'ean', 'gtin')
    def check_upc_ean_gtin(self):
        if 'for_synching' not in self.env.context:
            for record in self:
                if record.upc and record.upc != '' and (
                        not record.upc.isdigit() or len(record.upc) not in [6, 8, 12, 13]):
                    raise ValidationError(_('UPC or EAN must be numeric and have a length of 6, 8, 12 or 13 numbers.'))
                if record.ean and record.ean != '' and (
                        not record.ean.isdigit() or len(record.ean) not in [6, 8, 12, 13]):
                    raise ValidationError(_('UPC or EAN must be numeric and have a length of 6, 8, 12, or 13 numbers.'))
                if record.gtin and record.gtin != '' and (
                        not record.gtin.isdigit() or len(record.gtin) not in [8, 12, 13, 14]):
                    raise ValidationError(
                        _('Global Trade Number must be numeric and have a length of 8, 12, 13 or 14 numbers.'))

    def _prepare_product_channel_variant_data(self, channel, list_fields, map_variant=None):
        """
        This method is used in preparing data for creating or updating product channel variant from product.product
        :return:
        """
        self.ensure_one()
        vals = {}
        for variant_field in list_fields:
            if self._fields[variant_field].type == 'many2one':
                vals[variant_field] = self[variant_field].id
            else:
                vals[variant_field] = self[variant_field]

        attribute_values = self.product_template_attribute_value_ids.mapped('product_attribute_value_id')
        vals.update({
            'product_product_id': self.id,
            'currency_id': self.currency_id.id,
            'purchasing_disabled': True,
            'attribute_value_ids': [(6, 0, attribute_values.ids)],
            'weight_in_oz': self.weight_in_oz,
        })
        if map_variant:
            vals.update({
                'default_code': map_variant[self],
            })
        return vals

    def get_product_channel_variant(self, channel, map_variant=None):
        self.ensure_one()
        res = self.product_channel_variant_ids.filtered(lambda pc: pc.channel_id == channel)
        if map_variant:
            res = res.filtered(lambda pcv: pcv.default_code == map_variant[self])
        return res

    def action_open_free_qty(self):
        action = self.action_open_quants()
        action.update({
            'view_mode': 'list,form',
            'views': [(self.env.ref('multichannel_product.available_qty_tree_view').id, 'list'), (False, 'form')],
            'name': _('Available Qty')
        })
        return action

    @api.model
    def _get_image(self, image_url):
        try:
            if image_url:
                buffered = BytesIO(requests.get(image_url).content)
                img_base64 = base64.b64encode(buffered.getvalue())
                return img_base64
        except Exception as e:
            _logger.exception("Cannot get image from %s: %s", image_url, e)
            return None
            
    @api.model
    def create(self, vals):
        if self._name == 'product.product':
            if 'create_product_product' in self.env.context:
                if 'image_variant_1920' not in vals:
                    vals['image_variant_1920'] = self._get_image(vals.get('image_url'))

        product = super(ProductProduct, self.with_context(create_product_product=True)).create(vals)

        if product.is_product_variant:
            product.check_unique_default_code()

        return product

    def _set_default_values_from_master(self):
        self.ensure_one()
        default_vals = {}
        if 'for_synching' not in self.env.context and len(self.product_tmpl_id.product_variant_ids) > 1:
            if not self.weight_in_oz:
                default_vals['weight_in_oz'] = self.product_tmpl_id.weight_in_oz
            if not self.depth:
                default_vals['depth'] = self.product_tmpl_id.depth
            if not self.height:
                default_vals['height'] = self.product_tmpl_id.height
            if not self.width:
                default_vals['width'] = self.product_tmpl_id.width
            if not self.retail_price:
                default_vals['retail_price'] = self.product_tmpl_id.product_variant_ids[0].retail_price
            if not self.lst_price:
                default_vals['lst_price'] = self.product_tmpl_id.product_variant_ids[0].lst_price
            if not self.standard_price:
                default_vals['standard_price'] = self.product_tmpl_id.product_variant_ids[0].standard_price
            self.sudo().write(default_vals)
        return default_vals

    def remove_mapping(self, vals):
        if 'default_code' in vals and not 'for_synching' in self.env.context:
            self.mapped('product_channel_variant_ids').unlink()

    def write(self, vals):
        products = super().write(vals)
        self.check_unique_default_code()
        self.remove_mapping(vals)
        for product in self:
            if len(product.product_tmpl_id.product_variant_ids) == 1 and 'update_base_value' not in self.env.context:
                update_value = {}
                for field in BASE_VALUE:
                    if field in vals:
                        update_value[field] = vals[field]
                if update_value:
                    product.product_tmpl_id.sudo().with_context(update_base_value=True).write(update_value)
        return products

    def _set_weight(self):
        """Set weight in oz based on weight unit in system config"""
        weight_uom_system = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        weight_uom_oz = self.env.ref('uom.product_uom_oz')
        convert = UnitConverter(self).convert_weight
        for record in self:
            record.weight_in_oz = convert(record.weight, from_unit=weight_uom_system, to_unit=weight_uom_oz)

    def _set_weight_in_oz(self):
        """Set weight based on weight unit in system config"""
        weight_uom_system = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        weight_uom_oz = self.env.ref('uom.product_uom_oz')
        convert = UnitConverter(self).convert_weight
        for record in self:
            record.weight = convert(record.weight_in_oz, from_unit=weight_uom_oz, to_unit=weight_uom_system)

    def unlink(self):
        unsatisfied = self.mapped('product_channel_variant_ids')
        if unsatisfied:
            raise UserError(_('There are associated mappings. Please archive instead.'))
        return super(ProductProduct, self).unlink()
