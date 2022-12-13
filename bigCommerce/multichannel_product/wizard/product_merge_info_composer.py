# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from ..models.product_template import TEMPLATE_FIELDS_TO_UPDATE
from ..models.product_channel import has_differ
import json


class ProductMergeInfoComposer(models.TransientModel):
    _name = 'product.merge.info.composer'
    _description = 'Product Merge Info Composer'

    product_tmpl_id = fields.Many2one('product.template', string='Product Template')
    product_template_merge_info_id = fields.Many2one('product.template.merge.info',
                                                     string='Channel')

    current_name = fields.Char(related='product_tmpl_id.name')
    current_lst_price = fields.Float(related='product_tmpl_id.lst_price')
    current_retail_price = fields.Float(related='product_tmpl_id.retail_price')
    current_sku = fields.Char(related='product_tmpl_id.default_code')
    current_mpn = fields.Char(related='product_tmpl_id.mpn')
    current_depth = fields.Float(related='product_tmpl_id.depth')
    current_height = fields.Float(related='product_tmpl_id.height')
    current_weight_in_oz = fields.Float(related='product_tmpl_id.weight_in_oz')
    current_width = fields.Float(related='product_tmpl_id.width')
    current_brand_id = fields.Many2one(related='product_tmpl_id.brand_id')
    current_upc = fields.Char(related='product_tmpl_id.upc')
    current_ean = fields.Char(related='product_tmpl_id.ean')
    current_isbn = fields.Char(related='product_tmpl_id.isbn')
    current_gtin = fields.Char(related='product_tmpl_id.gtin')
    current_description = fields.Html(related='product_tmpl_id.description')
    current_description_sale = fields.Text(related='product_tmpl_id.description_sale')
    current_type = fields.Selection(related='product_tmpl_id.type')

    new_name = fields.Char(string='New Name')
    new_lst_price = fields.Float(string='New Default Price')
    new_retail_price = fields.Float(string='New MSRP')
    new_sku = fields.Char(string='New SKU')
    new_mpn = fields.Char(string='New MPN')
    new_depth = fields.Float(string='New Depth')
    new_height = fields.Float(string='New Height')
    new_weight_in_oz = fields.Float(string='New Weight')
    new_width = fields.Float(string='New Width')
    new_brand_id = fields.Many2one('product.brand', string='New Brand')
    new_upc = fields.Char(string='New UPC')
    new_ean = fields.Char(string='New EAN')
    new_isbn = fields.Char(string='New ISBN')
    new_gtin = fields.Char(string='New GTIN')
    new_description = fields.Text(string='New Description')
    new_description_sale = fields.Text(string='New Description Sale')
    new_type = fields.Selection([('consu', 'Consumable'),
                                 ('service', 'Service'),
                                 ('product', 'Storable Product')], string='New Type')

    is_update_name = fields.Boolean(string='Update Name?')
    is_update_lst_price = fields.Boolean(string='Update Default Price?')
    is_update_retail_price = fields.Boolean(string='Update Retail Price?')
    is_update_sku = fields.Boolean(string='Update SKU?')
    is_update_mpn = fields.Boolean(string='Update MPN?')
    is_update_depth = fields.Boolean(string='Update Depth?')
    is_update_height = fields.Boolean(string='Update Height?')
    is_update_weight_in_oz = fields.Boolean(string='Update Weight?')
    is_update_width = fields.Boolean(string='Update Width?')
    is_update_brand_id = fields.Boolean(string='Update Brand?')
    is_update_upc = fields.Boolean(string='Update UPC?')
    is_update_ean = fields.Boolean(string='Update EAN?')
    is_update_gtin = fields.Boolean(string='Update GTIN?')
    is_update_isbn = fields.Boolean(string='Update ISBN?')
    is_update_variant = fields.Boolean(string='Update Variants?')
    is_update_description = fields.Boolean(string='Update Description?')
    is_update_description_sale = fields.Boolean(string='Update Description Sale?')
    is_update_type = fields.Boolean(string='Update Type?')

    is_show_name = fields.Boolean(string='Show Name?')
    is_show_lst_price = fields.Boolean(string='Show Default Price?')
    is_show_retail_price = fields.Boolean(string='Show Retail Price?')
    is_show_sku = fields.Boolean(string='Show SKU?')
    is_show_mpn = fields.Boolean(string='Show MPN?')
    is_show_depth = fields.Boolean(string='Show Depth?')
    is_show_height = fields.Boolean(string='Show Height?')
    is_show_weight_in_oz = fields.Boolean(string='Show Weight?')
    is_show_width = fields.Boolean(string='Show Width?')
    is_show_brand_id = fields.Boolean(string='Show Brand?')
    is_show_upc = fields.Boolean(string='Show UPC?')
    is_show_ean = fields.Boolean(string='Show EAN?')
    is_show_gtin = fields.Boolean(string='Show GTIN?')
    is_show_isbn = fields.Boolean(string='Show ISBN?')
    is_show_variant = fields.Boolean(string='Show Variants?')
    is_show_description = fields.Boolean(string='Show Description?')
    is_show_description_sale = fields.Boolean(string='Show Description Sale?')
    is_show_type = fields.Boolean(string='Show Type?')

    ignore_remaining_changes = fields.Boolean(string='Ignore Remaining Changes?')
    is_checked = fields.Boolean(string='Has checked', compute='_compute_checked_options')

    @api.depends('is_update_name', 'is_update_lst_price',
                 'is_update_retail_price',
                 'is_update_sku', 'is_update_mpn', 'is_update_depth', 'is_update_height',
                 'is_update_weight_in_oz', 'is_update_width', 'is_update_brand_id', 'is_update_upc',
                 'is_update_ean', 'is_update_gtin', 'is_update_isbn', 'is_update_variant',
                 'is_update_description', 'is_update_description_sale', 'is_update_type')
    def _compute_checked_options(self):
        fields = list(filter(lambda f: 'is_update' in f, self.fields_get()))
        for record in self:
            record.is_checked = any([record[field] for field in fields])

    def _has_changes_on_variant(self):
        for record in self:
            record.is_update_variant = True if record.product_template_merge_info_id.product_variant_merge_info_ids else False

    @api.onchange('product_template_merge_info_id')
    def on_change_value(self):
        if self.product_template_merge_info_id:
            data = json.loads(self.product_template_merge_info_id.data)
            if data:
                FIELDS = self.product_template_merge_info_id.product_channel_id.get_merged_template_fields()
                for field in FIELDS:
                    if 'new_%s' % field not in data:
                        continue
                    if '_ids' in field:
                        continue
                    elif '_id' in field:
                        data['is_show_%s' % field] = has_differ(self['current_%s' % field].id, data['new_%s' % field])
                    else:
                        if 'image' in field:
                            continue
                        data['is_show_%s' % field] = has_differ(self['current_%s' % field], data['new_%s' % field])
            data[
                'is_show_variant'] = True if self.product_template_merge_info_id.product_variant_merge_info_ids else False
            if data['is_show_variant'] and \
                    not self.product_template_merge_info_id.product_channel_id.attribute_line_ids and \
                    not self.product_tmpl_id.attribute_line_ids:
                data['is_update_variant'] = True
                data['is_show_variant'] = False
            self.update(data)

    def _prepare_data_for_changes_on_variant(self):
        self.ensure_one()
        attribute_lines = self.product_template_merge_info_id.product_channel_id.attribute_line_ids
        update_attribute = []
        updated_lines = self.env['product.template.attribute.line']
        for line in attribute_lines:
            template_line = self.product_tmpl_id.attribute_line_ids.filtered(
                lambda l: l.attribute_id.id == line.attribute_id.id)
            if template_line:
                update_attribute.append((1, template_line.id, {'value_ids': [(6, 0, line.value_ids.ids)]}))
                updated_lines += template_line
            else:
                update_attribute.append((0, 0, {'attribute_id': line.attribute_id.id,
                                                'value_ids': [(6, 0, line.value_ids.ids)]}))
        removed_lines = self.product_tmpl_id.attribute_line_ids - updated_lines
        for template_line in removed_lines:
            update_attribute.append((3, template_line.id))

        if update_attribute:
            self.product_tmpl_id.with_context(merge_request=True).sudo().write({'attribute_line_ids': update_attribute})

        updated_products = self.env['product.product']
        for product_channel_variant in self.product_template_merge_info_id.product_channel_id.product_variant_ids:
            CREATED_FIELDS, UPDATED_FIELDS = self.product_template_merge_info_id.product_channel_id.get_merged_variant_fields()

            def generate_vals(FIELDS, record, get_image=False):
                vals = {}
                for field in FIELDS:
                    if '_ids' in field:
                        continue
                    elif '_id' in field:
                        vals[field] = record[field]
                    else:
                        if not get_image and 'image' in field:
                            continue
                        vals[field] = record[field]
                return vals

            dict_value = generate_vals(UPDATED_FIELDS, product_channel_variant)

            # # Update image
            # dict_value['image_variant_1920'] = product_channel_variant.image_variant_1920

            # Update attribute values
            template_attribute_values = self.product_tmpl_id.template_attribute_value_ids.filtered(
                lambda at: at.product_attribute_value_id.id in product_channel_variant.attribute_value_ids.ids)

            dict_value.update({
                'product_template_attribute_value_ids': [(6, 0, template_attribute_values.ids)],
                'active': True,
                'product_channel_variant_ids': [(4, product_channel_variant.id)]
            })

            product_product = self.product_tmpl_id.with_context(active_test=False).product_variant_ids.filtered(
                lambda p: set(p.product_template_attribute_value_ids.mapped('product_attribute_value_id').ids) == set(
                    product_channel_variant.attribute_value_ids.ids))

            if product_product:
                product_product.with_context(for_synching=True, merge_request=True).sudo().write(dict_value)
                updated_products += product_product
            else:
                dict_value['product_tmpl_id'] = self.product_tmpl_id.id
                dict_value.update(generate_vals(list(set(CREATED_FIELDS) - set(UPDATED_FIELDS)), product_channel_variant, True))
                updated_products += product_product.with_context(for_synching=True,
                                                                 merge_request=True).sudo().create(dict_value)

        # Archive variants removed on channel
        removed_lines = self.product_tmpl_id.product_variant_ids - updated_products
        if removed_lines:
            removed_lines.with_context(for_synching=True, merge_request=True).sudo().write({'active': False})

        # Remove when changes on variants were already merged
        self.product_template_merge_info_id.product_variant_merge_info_ids.unlink()
        self.env.cr.commit()

    def merge(self):
        self.ensure_one()
        # Prevent errors happening when user have double click on button
        if not self.product_template_merge_info_id:
            return False
        vals = {}
        temp = {}
        FIELDS = self.product_template_merge_info_id.product_channel_id.get_merged_template_fields()
        for field in FIELDS:
            if '_ids' in field:
                if field == 'product_variant_ids':
                    if self['is_update_variant']:
                        self._prepare_data_for_changes_on_variant()
                    vals['product_variant_ids'] = []
            else:
                if self['is_update_%s' % field]:
                    if '_id' in field:
                        vals[field] = self['new_%s' % field].id
                        temp['new_%s' % field] = self['new_%s' % field].id
                    else:
                        vals[field] = self['new_%s' % field]
                        temp['new_%s' % field] = self['new_%s' % field]
                else:
                    if '_id' in field:
                        temp['new_%s' % field] = self['current_%s' % field].id
                    else:
                        if 'image' in field:
                            continue
                        temp['new_%s' % field] = self['current_%s' % field]

        if vals:
            if 'product_variant_ids' in vals:
                del vals['product_variant_ids']
            if vals:
                self.product_tmpl_id.with_context(merge_request=True).write(vals)

        if not self.ignore_remaining_changes:
            # Remove if all changes were already merged to master
            def _check_do_it_later():
                differs = []
                for field in TEMPLATE_FIELDS_TO_UPDATE:
                    if '_ids' in field:
                        if field == 'product_variant_ids':
                            if self['is_show_variant'] and not self['is_update_variant']:
                                differs.append(True)
                    else:
                        if self['is_show_' + field] and not self['is_update_' + field]:
                            differs.append(True)
                return any(differs)

            if not _check_do_it_later():
                self.product_template_merge_info_id.sudo().unlink()
        else:
            self.product_template_merge_info_id.sudo().unlink()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'res_id': self.product_tmpl_id.id,
            'view_mode': 'form',
            'target': 'main',
        }
