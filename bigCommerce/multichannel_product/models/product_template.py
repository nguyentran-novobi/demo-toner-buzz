# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
import copy
from operator import attrgetter

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

from odoo.addons.omni_base.base_method import _standardize_vals

from ..utils.unit_converter import UnitConverter


class SKUMisMatchError(Exception):
    pass

class MissingSKU(Exception):
    pass

_logger = logging.getLogger(__name__)

# For Update to Channel
TEMPLATE_NORMAL_FIELDS_TO_UPDATE = ['name', 'default_code', 'weight_in_oz', 'depth', 'height', 'width', 'mpn',
                                    'upc', 'ean', 'isbn', 'gtin', 'retail_price', 'type']

TEMPLATE_RELATIONAL_FIELDS_TO_UPDATE = ['brand_id', 'product_variant_ids', 'product_channel_image_ids']

TEMPLATE_FIELDS_TO_UPDATE = TEMPLATE_NORMAL_FIELDS_TO_UPDATE + TEMPLATE_RELATIONAL_FIELDS_TO_UPDATE
VARIANT_FIELDS_TO_UPDATE = ['default_code', 'weight_in_oz', 'depth', 'height', 'width', 'mpn',
                            'upc', 'ean', 'isbn', 'gtin', 'retail_price', 'image_variant_1920']

# For List to Channel
TEMPLATE_NORMAL_FIELDS_TO_LIST = ['name', 'default_code', 'weight_in_oz', 'depth', 'height', 'width', 'mpn', 'lst_price',
                                  'upc', 'ean', 'isbn', 'gtin', 'retail_price', 'type',
                                  'description', 'description_sale', 'image_1920']

TEMPLATE_RELATIONAL_FIELDS_TO_LIST = ['brand_id', 'product_variant_ids', 'product_channel_image_ids']

TEMPLATE_FIELDS_TO_LIST = TEMPLATE_NORMAL_FIELDS_TO_LIST + TEMPLATE_RELATIONAL_FIELDS_TO_LIST
VARIANT_FIELDS_TO_LIST = ['default_code', 'lst_price', 'weight_in_oz', 'depth', 'height', 'width', 'mpn',
                          'upc', 'ean', 'isbn', 'gtin', 'retail_price', 'image_variant_1920']

FACTOR = {
    'FT-IN': 12,
    'LB-OZ': 16
}

BASE_VALUE = ['lst_price', 'retail_price', 'weight_in_oz', 'depth', 'height', 'width',
              'upc', 'ean', 'gtin', 'isbn', 'mpn']


# Define Exceptions
class MappingImportError(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class ProductTemplate(models.Model):
    _inherit = "product.template"
    _order = "id desc"

    product_channel_ids = fields.One2many('product.channel', 'product_tmpl_id', string='Products Channel')
    product_alternate_sku_ids = fields.One2many('product.alternate.sku', 'product_tmpl_id', string='Product Alternate SKUs')

    brand_id = fields.Many2one('product.brand', string='Brand')
    product_channel_count = fields.Integer('# Product Channels', compute='_compute_product_channel_stats', store=False)
    draft_channel_ids = fields.Many2many(
        'ecommerce.channel',
        string="Draft channels",
        compute='_compute_product_channel_stats',
        store=False,
    )
    active_channel_ids = fields.Many2many(
        'ecommerce.channel',
        string="Active channels",
        compute='_compute_product_channel_stats',
        store=False,
    )
    product_channel_image_ids = fields.One2many('product.channel.image', 
                                                'product_tmpl_id', 
                                                string='Images', copy=False)

    # Base Value
    lst_price = fields.Float(string='Sales Price', related='list_price', digits='Product Price', readonly=False)
    retail_price = fields.Float(string='MSRP', digits='Product Price')
    mpn = fields.Char(string='Manufacturer Part Number')
    depth = fields.Float(string='Depth')
    height = fields.Float(string='Height')
    width = fields.Float(string='Width')
    weight_in_oz = fields.Float(
        string='Weight in oz',
        help='Product weight in Ounce(oz)',
        compute='_compute_weight_in_oz',
        inverse='_set_weight_in_oz',
        copy=True,
        digits='Stock Weight',
    )
    upc = fields.Char(string='UPC')
    ean = fields.Char(string='EAN')
    gtin = fields.Char(string='GTIN')
    isbn = fields.Char(string='ISBN')

    weight = fields.Float(
        'Weight', compute=False, digits='Stock Weight',
        inverse='_set_weight', store=True,
        help="The weight of the contents in Kg, not including any packaging, etc.", copy=True)
    standard_price = fields.Float(string='Cost', digits='Product Price')

    dimensions = fields.Char(string='Dimensions', compute='_compute_dimensions')
    length_uom_name = fields.Char(string='Length unit of measure label', compute='_compute_length_uom_name')

    product_template_merge_info_ids = fields.One2many('product.template.merge.info', 'product_tmpl_id')

    is_show_variants = fields.Boolean(compute='_is_show_variants', help='Whether showing variants or not')

    # For updating image
    has_change_image = fields.Boolean(readonly=True,
                                      help='This will be used to know whether having changes on images or not')

    display_number_variants = fields.Integer(string='Variants', compute='_get_number_of_variants')

    template_attribute_value_ids = fields.One2many('product.template.attribute.value',
                                                   'product_tmpl_id', string='Template Attribute Value')

    free_qty = fields.Float(
        'Free To Use Quantity ', compute='_compute_free_qty',
        digits='Product Unit of Measure', compute_sudo=False)

    image_1920 = fields.Image(compute='_compute_image_1920', store=True)

    @api.onchange('default_code')
    def _onchange_default_code(self):
        if self.mapped('product_variant_ids.product_channel_variant_ids'):
            return {'warning': {
                'message': _(
                    "There are some Product Mappings which have %s as SKU. Changing the Internal Reference will delete all of them.",
                    self._origin.default_code),
            }}
        super()._onchange_default_code()

    @api.depends('product_channel_image_ids', 'product_channel_image_ids.is_thumbnail')
    def _compute_image_1920(self):
        for record in self:
            image = record.product_channel_image_ids.filtered(lambda r: r.is_thumbnail)
            record.image_1920 = image.image if image else False

    def _compute_dimensions(self):
        for record in self:
            record.dimensions = f'{record.width}x{record.depth}x{record.height}'

    def _compute_length_uom_name(self):
        self.length_uom_name = self._get_length_uom_name_from_ir_config_parameter()

    @api.model
    def _get_length_uom_name_from_ir_config_parameter(self):
        return self._get_length_uom_id_from_ir_config_parameter().display_name

    is_channel_sku_changed = fields.Boolean('Channel SKU changed', compute='_compute_is_channel_sku_changed',
                                            help='Indicates whether the SKU of the listing product'
                                                 ' is different than the associating master product.')

    def _compute_free_qty(self):
        for record in self:
            record.free_qty = sum(
                record.mapped('product_variant_ids.free_qty')
            )

    @api.depends('default_code', 'product_variant_ids')
    def _compute_is_channel_sku_changed(self):
        for record in self:
            record.is_channel_sku_changed = record._check_if_channel_sku_changed()

    def _check_if_channel_sku_changed(self, platform=None):
        self.ensure_one()
        platforms = [platform] if platform else self._get_channel_needs_check_sku_changed()
        pcv = self.product_variant_ids.mapped('product_channel_variant_ids')
        triplets = pcv.mapped(lambda v: (
            v.platform,
            v.default_code,
            v.product_product_id.default_code
        ))
        return any((t[0] in platforms) and t[1] != t[2] for t in triplets)

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

    def action_open_free_qty(self):
        return self.with_context(active_test=False).product_variant_ids\
            .filtered(lambda p: p.active).action_open_free_qty()

    def _get_number_of_variants(self):
        for record in self:
            if not record.attribute_line_ids:
                record.display_number_variants = 0
            else:
                record.display_number_variants = len(record.product_variant_ids)

    @api.depends('attribute_line_ids')
    def _is_show_variants(self):
        for record in self:
            record.is_show_variants = True if record.attribute_line_ids else False

    def _compute_show_warning_merging(self):
        for record in self:
            record.is_needed_to_merge = True if record.product_template_merge_info_ids else False

    def _compute_show_warning_updating(self):
        for record in self:
            product_channels = record.product_channel_ids.with_context(active_test=False)
            product_channels_to_update = product_channels.filtered(
                lambda pc: pc.is_needed_to_update and pc.channel_id.active)
            is_needed_to_update = bool(product_channels_to_update.exists())
            record.is_needed_to_update = is_needed_to_update or record.is_channel_sku_changed

    def _compute_product_channel_stats(self):
        get_ioc = attrgetter('id_on_channel')
        for record in self:
            mapping_templates = record.product_channel_ids
            master_variants = record.with_context(active_test=False).product_variant_ids
            mapping_variants = master_variants.mapped('product_channel_variant_ids')
            listed_channels = mapping_templates.mapped('channel_id') | mapping_variants.mapped('channel_id')

            active_channels = self.env['ecommerce.channel']
            for channel in listed_channels:
                chn_templates = mapping_templates.filtered(lambda p, chn=channel: p.channel_id == chn)
                chn_variants = mapping_variants.filtered(lambda pcv, chn=channel: pcv.channel_id == chn)

                if any(map(get_ioc, chn_variants)) or any(map(get_ioc, chn_templates)):
                    active_channels |= channel
            draft_channels = listed_channels - active_channels

            record.update({
                'product_channel_count': len(listed_channels),
                'draft_channel_ids': [(6, 0, draft_channels.ids)],
                'active_channel_ids': [(6, 0, active_channels.ids)],
            })

    # Override and Overwrite
    def _set_weight(self):
        """
        Set weight in oz for weight unit in system config
        Set base variant weight
        """
        self._set_base_variant_weight()

    def _set_base_variant_weight(self):
        for record in self:
            if not record.attribute_line_ids and record.product_variant_id:
                record.product_variant_id.weight_in_oz = record.weight_in_oz
                record.product_variant_id.weight = record.weight

    @api.depends('weight')
    def _compute_weight_in_oz(self):
        weight_uom_system = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        weight_uom_oz = self.env.ref('uom.product_uom_oz')
        convert = UnitConverter(self).convert_weight
        for record in self:
            record.weight_in_oz = convert(record.weight, from_unit=weight_uom_system, to_unit=weight_uom_oz)

    def _set_weight_in_oz(self):
        """
        Set weight for weight unit in system config
        Set base variant weight
        """
        weight_uom_system = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        weight_uom_oz = self.env.ref('uom.product_uom_oz')
        convert = UnitConverter(self).convert_weight
        for record in self:
            record.weight = convert(record.weight_in_oz, from_unit=weight_uom_oz, to_unit=weight_uom_system)
        self._set_base_variant_weight()

    def change_channel(self):
        self.ensure_one()
        return {
            'name': _("Change Channel"),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'product.change.channel',
            'target': 'new',
            'context': {'default_product_tmpl_id': self.id}
        }

    def open_product_mapping_views(self):
        self.ensure_one()
        mapping_variant_ids = self.product_variant_ids.mapped('product_channel_variant_ids').ids
        action = self.env["ir.actions.actions"]._for_xml_id('multichannel_product.product_channel_variant_action_2')
        action.update({
            'domain': [('id', 'in', mapping_variant_ids)],
        })
        return action

    @api.model
    def _get_weight_uom_id_from_ir_config_parameter(self):
        get_param = self.env['ir.config_parameter'].sudo().get_param
        product_weight_in_lbs_param = get_param('product.weight_in_lbs')
        if product_weight_in_lbs_param == '0':
            return self.env.ref('uom.product_uom_kgm')
        elif product_weight_in_lbs_param == '1':
            return self.env.ref('uom.product_uom_lb')
        else:
            return self.env.ref('uom.product_uom_oz')

    @api.model
    def get_product_channel(self, channel):
        return self.product_channel_ids.filtered(lambda pc: pc.channel_id.id == channel.id)

    def button_export_to_channel(self):
        self.ensure_one()
        return {
            'name': _("Export to Store"),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'export.product.composer',
            'target': 'new',
            'context': {'default_product_tmpl_id': self.id},
        }

    @api.model
    def create(self, vals):
        if 'attribute_line_ids' not in vals:
            vals['attribute_line_ids'] = [(5, 0, 0)]
        template = super(ProductTemplate, self).create(vals)

        for variant in template.product_variant_ids:
            if variant.product_template_attribute_value_ids:
                default_sku = "SKU-%s-%s" % (variant.id, "-".join([e.name for e in variant.product_template_attribute_value_ids]))
            else:
                default_sku = template.default_code

            default_vals = {
                'lst_price': vals.get('lst_price', ''),
                'retail_price': vals.get('retail_price', ''),
                'width': vals.get('width', ''),
                'depth': vals.get('depth'),
                'height': vals.get('height'),
                'weight_in_oz': vals.get('weight_in_oz'),
                'default_code': default_sku
            }

            if len(template.product_variant_ids) == 1:
                default_vals.update({
                    'upc': vals.get('upc', ''),
                    'ean': vals.get('ean', ''),
                    'gtin': vals.get('gtin', ''),
                    'isbn': vals.get('isbn', ''),
                    'mpn': vals.get('mpn', ''),
                    'image_variant_1920': vals.get('image_1920', '')
                })
            variant.sudo().write(default_vals)
        return template

    def _get_mapping_categories(self, channel):
        mapping_categories = self.env['product.channel.category'].search([('internal_category_id', '=', self.categ_id.id),
                                                                          ('channel_id', '=', channel.id)])
        return mapping_categories

    def _prepare_product_channel_data(self, channel, update=True, product_channel_tmpl_id=None, map_variant=None):
        """
        This method is used in preparing data for creating or updating product channel from product.template
        :return:
        """
        self.ensure_one()
        vals = {}
        map_variant = map_variant or {}
        template_fields, variant_fields, ignore_fields = self.get_fields_to_list(channel.platform, update)
        ignore_fields = ignore_fields if self.attribute_line_ids else []
        for field in filter(lambda f: hasattr(self, f) and f not in ignore_fields, template_fields):
            if self._fields[field].type in ['one2many', 'many2many']:
                vals.update(self._prepare_product_channel_data_relational_multi(
                    field,
                    channel,
                    update=update,
                    variant_fields=variant_fields,
                    map_variant=map_variant,
                ))
            elif self._fields[field].type == 'many2one':
                vals.update(self._prepare_product_channel_data_relational(field))
            else:
                vals.update(self._prepare_product_channel_data_basic(field))
        if not update:
            categories = self._get_mapping_categories(channel)
            vals.update({
                'categ_ids': [(6, 0, categories.ids)]
            })
        return vals

    def _prepare_product_channel_data_relational_multi(self, field, channel, **kwargs):
        vals = {}
        if field == 'product_variant_ids':
            self._remove_mapping_of_already_removed_variants(channel)
            variant_vals = []
            for variant in self.product_variant_ids:
                product_channel_variant = variant.get_product_channel_variant(
                    channel, map_variant=kwargs['map_variant'])
                variant_val = variant._prepare_product_channel_variant_data(
                    channel, kwargs['variant_fields'], map_variant=kwargs['map_variant'])
                if product_channel_variant:
                    # Don't need to update these fields
                    del variant_val['product_product_id']
                    del variant_val['purchasing_disabled']
                    # If user only add attribute value after product is created,
                    # Odoo will only add attribute value to that variant instead of creating a new one
                    # So, need to clear id_on_channel.
                    # By doing this, when updating to channel, this will become a new one
                    if variant.product_template_attribute_value_ids \
                            and not product_channel_variant.attribute_value_ids:
                        variant_val['id_on_channel'] = False
                    variant_vals.append((1, product_channel_variant.id, variant_val))
                else:
                    variant_val.update({
                        'product_product_id': variant.id,
                        'purchasable': True,
                    })
                    variant_vals.append((0, 0, variant_val))
            if variant_vals:
                vals[field] = variant_vals
                attribute_line_ids = [(5, 0, 0)]
                for attribute_line in self.attribute_line_ids:
                    attribute_line_ids.append((0, 0, {
                        'attribute_id': attribute_line.attribute_id.id,
                        'value_ids': [(6, 0, attribute_line.value_ids.ids)]
                    }))
                vals['attribute_line_ids'] = attribute_line_ids
                vals['is_show_variants'] = True
        elif field == 'product_channel_image_ids' and (self.has_change_image or not kwargs['update']):
            images = [(5, 0, 0)]
            for image in self.product_channel_image_ids:
                images.append((0, 0, {
                    'name': image.name,
                    'image_description': image.image_description,
                    'is_thumbnail': image.is_thumbnail,
                    'image': image.image,
                    'channel_id': channel.id,
                    'sequence': image.sequence,
                    'product_tmpl_id': False
                }))
                if image.is_thumbnail:
                    vals['image_1920'] = image.image
            vals['product_channel_image_ids'] = images
        return vals

    def _prepare_product_channel_data_relational(self, field):
        return {
            field: self[field].id
        }

    def _prepare_product_channel_data_basic(self, field):
        vals = {}
        if field == 'type':
            vals[field] = 'physical' if self.type in ['consu', 'product'] else 'digital'
            vals['inventory_tracking'] = self.type == 'product'
        else:
            vals[field] = self[field]
        return vals

    def _remove_mapping_of_already_removed_variants(self, channel):
        self.ensure_one()
        product_channel = self.product_channel_ids.filtered(lambda r: r.channel_id == channel)
        product_channel_variants = product_channel.product_variant_ids.with_context(active_test=False)
        to_remove_variants = product_channel_variants.filtered(
            lambda r: not r.product_product_id or not r.product_product_id.active)
        if to_remove_variants:
            to_remove_variants.unlink()

    def _check_sku_and_unlink_master_from_listing(self):
        products = self.filtered(lambda r: r.is_channel_sku_changed)
        successful = self.env['product.channel.variant']
        for product in products.mapped('product_variant_ids'):
            channel_variants = product.product_channel_variant_ids.filtered(lambda r: (
                r.channel_id.platform in self._get_channel_needs_check_sku_changed()
                and r.default_code != product.default_code
            ))
            channel_variants.sudo().with_context(update_from_master=True).write(dict(
                product_product_id=False
            ))
            successful |= channel_variants
        return successful

    # TODO: Should NOT HARD CODE channel names (at least this way) -> Need a more general approach
    @api.model
    def _get_channel_needs_check_sku_changed(self):
        return ['amazon', 'ebay']

    def write(self, vals):
        # Only for updating thumbnail
        if 'update_thumbnail' in self.env.context:
            return super(ProductTemplate, self).write(vals)
        if 'update_status' in self.env.context:
            return super(ProductTemplate, self).write(vals)

        res = super(ProductTemplate, self).write(vals)

        for record in self:
            if 'product_channel_image_ids' in vals:
                thumbnail = record.product_channel_image_ids.filtered(lambda r: r.is_thumbnail)
                if thumbnail:
                    record.sudo().with_context(update_thumbnail=True).write({'image_1920': thumbnail.image})
                else:
                    record.sudo().with_context(update_thumbnail=True).write({'image_1920': False})
            if not record.attribute_line_ids and 'update_base_value' not in self.env.context:
                update_variant_value = {}
                for field in BASE_VALUE:
                    if field in vals:
                        update_variant_value[field] = vals[field]
                # Update thumbnail for base variant
                update_variant_value['image_variant_1920'] = record.image_1920
                if update_variant_value:
                    record.product_variant_ids.sudo().with_context(update_base_value=True).write(update_variant_value)
        return res

    @api.model
    def _get_internal_categories(self, product_channel_vals, channel):
        if 'categ_ids' in product_channel_vals:
            mapping_category = self.env['product.channel.category'].search([('id', 'in', product_channel_vals['categ_ids'][0][2]),
                                                                            ('channel_id', '=', channel.id), ('internal_category_id', '!=', False)], limit=1)
            return mapping_category.internal_category_id
        return False

    @api.model
    def prepare_product_template(self, product_channel_vals, channel):
        """
        Convert data values from mapping data to master data
        mapping data was prepared from store data
        Preparing product.template info for creating/updating
        Preparing images
        """

        thumbnail = product_channel_vals.get('image_1920', False)
        if thumbnail and product_channel_vals.get('product_channel_image_ids', []) \
                and all(i[0] == 0 and not i[2].get('is_thumbnail', False) for i in product_channel_vals['product_channel_image_ids']):
            product_channel_vals['product_channel_image_ids'][0][2]['is_thumbnail'] = True

        product_template_vals = {
            'name': product_channel_vals.get('name'),
            'retail_price': product_channel_vals.get('retail_price'),
            'weight_in_oz': product_channel_vals.get('weight_in_oz'),
            'width': product_channel_vals.get('width'),
            'depth': product_channel_vals.get('depth'),
            'height': product_channel_vals.get('height'),
            'default_code': product_channel_vals.get('default_code'),
            'mpn': product_channel_vals.get('mpn'),
            'image_1920': thumbnail,
            'description': product_channel_vals.get('description'),
            'description_sale': product_channel_vals.get('description_sale'),
            # This attributes will help in creating/updating product.product
            'attribute_line_ids': product_channel_vals.get('attribute_line_ids'),
            'brand_id': False if product_channel_vals.get('brand_id') == 0 else product_channel_vals.get('brand_id'),
            'invoice_policy': 'delivery',
            'upc': product_channel_vals.get('upc'),
            'ean': product_channel_vals.get('ean'),
            'isbn': product_channel_vals.get('isbn'),
            'gtin': product_channel_vals.get('gtin'),
            'product_channel_image_ids': product_channel_vals.get('product_channel_image_ids', [])
        }

        if self.env.user.has_group('multichannel_manage_price.group_manage_variant_price'):
            product_template_vals['lst_price'] = product_channel_vals.get('lst_price')
        category = self._get_internal_categories(product_channel_vals, channel)
        if category:
            product_template_vals.update({
                'categ_id': category.id
            })
        return product_template_vals

    def prepare_product_variant(self, channel, variant_values, base_variant=True):
        self.ensure_one()
        vals = {
            'default_code': variant_values.get('default_code'),
            'image_variant_1920': variant_values.get('image_variant_1920', False),
            'product_tmpl_id': self.id
        }
        if base_variant:
            for field in BASE_VALUE:
                vals[field] = variant_values.get(field)

        if not self.env.user.has_group('multichannel_manage_price.group_manage_variant_price'):
            vals.pop('lst_price', 0)
        return vals

    def get_product_product_by_variant_data(self, channel, variant_values,
                                            new_master=False, auto_merge_variant=False):
        """
        Get product.product by using variant values.
        Because on product_data, we can get attributes information. We will use them in creating/updating template.
        So, product.product will be created automatically when updating attributes on template.
        We only need to use it for searching instead of creating
        """

        self.ensure_one()    
        if 'attribute_value_ids' in variant_values:
            template_attribute_values = self.template_attribute_value_ids.filtered(
                lambda at: at.product_attribute_value_id.id in variant_values['attribute_value_ids'][0][2])
            product_product = self.with_context(active_test=False).product_variant_ids.filtered(
                lambda p: p.product_template_attribute_value_ids == template_attribute_values)
        else:
            product_product = self.product_variant_ids[0] if self.product_variant_ids else self.product_variant_ids

        if new_master or auto_merge_variant:
            if not product_product:
                vals = self.prepare_product_variant(channel, variant_values)
                # Because new variant has other attribute values, we only use default_code to find master variant.
                # Merge request will be created later
                if 'default_code' in vals and vals['default_code']:
                    product_product = self.with_context(active_test=False).product_variant_ids.filtered(
                        lambda p: p.default_code == vals['default_code'])
                if not product_product:
                    if 'attribute_value_ids' in variant_values:
                        vals['product_template_attribute_value_ids'] = [(6, 0, template_attribute_values.ids)]
                    product_product = product_product.with_context(for_synching=True).sudo().create(vals)
            else:
                base_variant = True if product_product.product_template_attribute_value_ids else False
                update_variant_data = self.prepare_product_variant(channel=channel,
                                                                   variant_values=variant_values,
                                                                   base_variant=base_variant)

                # Because in this case, these product variants have just been created, we don't need to care
                # about merging request. So, we will update value for variant as variant listing
                product_product.with_company(channel.company_id.id)\
                    .with_context(for_synching=True).sudo().write(update_variant_data)
        return product_product

    @api.model
    def create_jobs_for_synching(self, vals_list, channel_id,
                                 sync_inventory=False, auto_create_master=None):
        """
        Spit values list to smaller list and add to Queue Job
        auto_create_master: Auto create product even if no matching mapping found
        """
        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)
        auto_override_product = channel.auto_override_product
        auto_create_master_product = channel.get_setting('auto_create_master_product')
        auto_create_master = auto_create_master if auto_create_master is not None else auto_create_master_product
        # For the future when we want to process multiple products at once
        uuids = []
        for vals in vals_list:
            log = self.env['omni.log'].create({
                'datas': vals,
                'channel_id': channel_id,
                'operation_type': 'import_product',
                'res_model': 'product.channel',
                'entity_name': vals['name'],
                'product_sku': vals.get('default_code') or vals.get('sku'),
                'channel_record_id': str(vals['id'])
            })
            job_uuid = self.with_context(log_id=log.id, for_synching=True).with_delay(max_retries=15)._sync_in_queue_job(
                vals,
                channel_id,
                auto_create_master=auto_create_master,
                auto_override_product=auto_override_product,
            ).uuid
            log.update({'job_uuid': job_uuid})
            uuids.append(job_uuid)
            self.env.cr.commit()
        return uuids

    @api.model
    def _search_product_alternate_sku(self, skus, channel_id):
        return self.env['product.alternate.sku'].search([('name', 'in', skus),
                                                         ('channel_id.id', '=', channel_id)])

    @api.model
    def _search_product_variant_by_default_code(self, skus):
        return self.env['product.product'].search([('default_code', 'in', skus), ('default_code', 'not in', [False, ''])])

    @api.model
    def _prepare_mapping_skus(self, product_data, channel_id):
        product_mappings = self.env['product.channel'].search([('channel_id', '=', channel_id),
                                                               ('id_on_channel', '=', str(product_data['id']))])
        variant_skus = [v.get('sku') for v in product_data.get('variants', [])]
        product_variants = self._search_product_variant_by_default_code(variant_skus)
        mapping_sku_vs_product_variants = {p.default_code: p for p in product_variants}

        product_alternate_skus = self._search_product_alternate_sku(variant_skus, channel_id)
        mapping_sku_vs_product_variants.update({p.name: p.product_product_id for p in product_alternate_skus})
        return product_mappings, mapping_sku_vs_product_variants

    @api.model
    def _create_log_for_import_product(self, data, channel_id, channel_record_id, entity_name, message):
        self.env['omni.log'].create({
            'datas': data,
            'channel_id': channel_id,
            'operation_type': 'import_product',
            'res_model': 'product.channel',
            'message': message,
            'entity_name': entity_name,
            'product_sku': data.get('sku') or data.get('default_code'),
            'channel_record_id': channel_record_id,
            'status': 'failed'
        })

    @api.model
    def _check_invalid_mapping(self, product_mapping, channel_id, auto_create_master, product_template_data, mapping_sku_vs_product_variants):
        if not auto_create_master and not any(v.get('sku') in mapping_sku_vs_product_variants.keys() for v in
                                              product_template_data.get('variants', [])):
            if product_mapping:
                product_mapping.unlink()
            raise MissingSKU("Missing SKU")
        return True

    @api.model
    def _create_or_update_product_mapping(self, product_mapping, product_template_data, channel_id):
        vals = product_mapping.prepare_product_channel(product_template_data, channel_id)
        if product_mapping:
            vals.update({
                'attribute_line_ids': vals['attribute_line_ids']
            })
            product_mapping.with_context(for_synching=True).sudo().write(_standardize_vals(env=self.env,
                                                                                           model=self._name,
                                                                                           datas=vals))
        else:
            product_mapping = product_mapping.with_context(for_synching=True).create(
                _standardize_vals(env=self.env,
                                  model=self.env['product.channel']._name,
                                  datas=vals))
        return product_mapping

    @api.model
    def _prepare_data_for_create_using_overridden_fields(self, datas, overridden_fields):
        default_overridden_fields = ['name', 'product_tmpl_id', 'default_code', 'attribute_line_ids',
                                     'product_template_attribute_value_ids']
        vals = {}
        for k, v in datas.items():
            if k in default_overridden_fields + overridden_fields:
                vals.update({
                    k: v
                })
        return vals

    @api.model
    def _prepare_data_for_update_using_overridden_fields(self, datas, overridden_fields):
        vals = {}
        for k, v in datas.items():
            if k in overridden_fields:
                vals.update({
                    k: v
                })
        return vals

    def _update_attribute_values_from_mapping_data(self, attribute_id, value_id):
        update_attribute = []
        updated_lines = self.env['product.template.attribute.line']
        attribute_line = self.attribute_line_ids.filtered(
            lambda l: l.attribute_id.id == attribute_id)
        if attribute_line:
            update_attribute.append((1, attribute_line.id, {'value_ids': [(6, 0, attribute_line.value_ids.ids + [value_id])]}))
            updated_lines += attribute_line
        else:
            update_attribute.append((0, 0, {'attribute_id': attribute_id,
                                            'value_ids': [(6, 0, [value_id])]}))
        if update_attribute:
            self.update({'attribute_line_ids': update_attribute})
        
    @api.model
    def _create_or_update_product_template(self, product_template, product_template_data, channel, auto_override_product):
        product_channel_vals = self.env['product.channel'].prepare_product_channel(product_template_data, channel.id)
        product_template_vals = self.prepare_product_template(product_channel_vals, channel)
        product_template_vals['type'] = product_template_data.get('product_tmpl_type', 'product')

        overridden_fields = channel.get_auto_overridden_fields()

        if product_template and auto_override_product:
            vals = self._prepare_data_for_update_using_overridden_fields(product_template_vals, overridden_fields)
            product_template.with_context(merge_request=True, for_synching=True).sudo().write(vals)
        elif not product_template:
            vals = self._prepare_data_for_create_using_overridden_fields(product_template_vals, overridden_fields)
            product_template = self.env['product.template'].with_context(for_synching=True, mail_create_nosubscribe=True).create(vals)
        return product_template
    
    @api.model
    def _update_product_variant(self, product_variant, product_variant_data, overridden_fields):
        vals = self._prepare_data_for_update_using_overridden_fields(product_variant_data, overridden_fields)
        product_variant.with_context(for_synching=True).write(vals)

    def _prepare_attribute_values_for_variant(self, product_variant_data, mapping_variant_data):
        if 'attribute_value_ids' in mapping_variant_data:
            attribute_values = self.env['product.attribute.value'].browse(mapping_variant_data['attribute_value_ids'][0][2])
            for attribute_value in attribute_values:
                self._update_attribute_values_from_mapping_data(attribute_id=attribute_value.attribute_id.id, 
                                                                value_id=attribute_value.id)
            template_attribute_values = self.template_attribute_value_ids.filtered(
                lambda at: at.product_attribute_value_id.id in mapping_variant_data['attribute_value_ids'][0][2])
            product_variant_data['product_template_attribute_value_ids'] = [(6, 0, template_attribute_values.ids)]
        return product_variant_data
    
    @api.model
    def _prepare_product_variant_data(self, product_template, product_template_data, channel, variant_values):
        if product_template:
            product_variant_data = product_template.prepare_product_variant(channel, variant_values)
        else:
            product_channel_vals = self.env['product.channel'].prepare_product_channel(product_template_data, channel.id)
            product_variant_data = self.prepare_product_template(product_channel_vals, channel)
            product_variant_data.pop('attribute_line_ids')
            product_variant_data['type'] = product_template_data.get('product_tmpl_type', 'product')
        return product_variant_data

    @api.model
    def _create_product_product(self, product_template, product_variant_data, mapping_variant_values, channel, auto_create_master):
        
        ProductProduct = self.env['product.product']
        product_variant_data.update({
            'default_code': mapping_variant_values.get('default_code'),
        })

        overridden_fields = channel.get_auto_overridden_fields()
        product_variant_data = self._prepare_data_for_create_using_overridden_fields(product_variant_data, overridden_fields)
        product_template.with_context(for_synching=True)._prepare_attribute_values_for_variant(product_variant_data, mapping_variant_values)
        
        if 'product_template_attribute_value_ids' in product_variant_data:
            product_attribute_value_ids = self.env['product.template.attribute.value'].browse(product_variant_data['product_template_attribute_value_ids'][0][2]).mapped('product_attribute_value_id').ids
            product_variant = product_template.product_variant_ids.filtered(
                lambda p: set(p.product_template_attribute_value_ids.mapped(
                    'product_attribute_value_id').ids) == set(product_attribute_value_ids))
            if product_variant and product_variant.default_code != product_variant_data.get('default_code'):
                raise SKUMisMatchError(f"SKU Mismatch: {product_variant_data.get('default_code')}")
            elif auto_create_master:
                product_variant = ProductProduct.create(product_variant_data)
        else:
            product_variant = product_template.product_variant_id
            product_variant.update(product_variant_data)

        return product_variant

    @api.model
    def _prepare_product_mapping_variant_data(self, variant_values, product_variant_id):
        variant_values.update({
            'product_product_id': product_variant_id
        })
        standardized_vals = _standardize_vals(
            env=self.env,
            model=self.env['product.channel.variant']._name,
            datas=variant_values,
        )
        return standardized_vals

    @api.model
    def _process_existed_mapping_variant(self, master_record_product, mapping_product_data, mapping_record_product,
                                         master_variant_record_product, master_variant_values, product_mapping_variant,
                                         mapping_variant_data, mapping_variant_values, channel, auto_create_master, auto_override_product):

        if not master_variant_record_product and not auto_create_master:
            self._create_log_for_import_product(mapping_variant_data, channel.id, mapping_record_product.id_on_channel,
                                                mapping_product_data.get('name'), message="Missing SKU")
            product_mapping_variant.unlink()
        else:
            if master_variant_record_product and auto_override_product:
                overridden_fields = channel.get_auto_overridden_fields()
                self._update_product_variant(master_variant_record_product, master_variant_values, overridden_fields)
            elif not master_variant_record_product:
                try:
                    master_variant_record_product = self._create_product_product(master_record_product, master_variant_values,
                                                                                 mapping_variant_values, channel, auto_create_master)
                    if master_variant_record_product:
                        product_mapping_variant_data = self._prepare_product_mapping_variant_data(mapping_variant_values, master_variant_record_product.id)
                        product_mapping_variant.update(product_mapping_variant_data)
                        product_alternates = master_variant_record_product.product_alternate_sku_ids.filtered(
                            lambda l: l.name == product_mapping_variant.default_code and l.channel_id == channel)
                        if product_alternates:
                            product_alternates[0].update({
                                'product_channel_variant_id': product_mapping_variant.id
                            })
                except SKUMisMatchError as e:
                    self._create_log_for_import_product(mapping_variant_data, channel.id,
                                                        mapping_record_product.id_on_channel,
                                                        mapping_product_data.get('name'),
                                                        message=e)
                    if product_mapping_variant:
                        product_mapping_variant.unlink()
                                                                           
    @api.model
    def _process_not_existed_mapping_variant_with_product_variant(self, master_variant_record_product, master_variant_values,
                                                                  mapping_variant_values, channel, auto_override_product):
        if auto_override_product:
            overridden_fields = channel.get_auto_overridden_fields()
            self._update_product_variant(master_variant_record_product, master_variant_values, overridden_fields)
        product_mapping_variant_data = self._prepare_product_mapping_variant_data(mapping_variant_values, master_variant_record_product.id)
        product_channel_variant = self.env['product.channel.variant'].create(product_mapping_variant_data)
        product_alternates = master_variant_record_product.product_alternate_sku_ids.filtered(
            lambda l: l.name == product_channel_variant.default_code and l.channel_id == channel)
        if product_alternates:
            product_alternates[0].update({
                'product_channel_variant_id': product_channel_variant.id
            })
                                    
    @api.model
    def _process_not_existed_mapping_variant_without_product_variant(self, master_record_product, mapping_product_data,
                                                                     mapping_record_product, master_variant_values,
                                                                     mapping_variant_data, mapping_variant_values, channel, auto_create_master):
        try:
            product_variant = self._create_product_product(master_record_product, master_variant_values, mapping_variant_values, channel, auto_create_master)

            if product_variant:
                product_mapping_variant_data = self._prepare_product_mapping_variant_data(mapping_variant_values, product_variant.id)
                product_channel_variant = self.env['product.channel.variant'].create(product_mapping_variant_data)
                product_alternates = product_variant.product_alternate_sku_ids.filtered(
                    lambda l: l.name == product_channel_variant.default_code and l.channel_id == channel)
                if product_alternates:
                    product_alternates[0].update({
                        'product_channel_variant_id': product_channel_variant.id
                    })
            else:
                self._create_log_for_import_product(mapping_variant_data, channel.id,
                                                    mapping_record_product.id_on_channel,
                                                    mapping_product_data.get('name'),
                                                    message=f"Missing SKU: {mapping_variant_values.get('default_code')}")
        except SKUMisMatchError as e:
            self._create_log_for_import_product(mapping_variant_data, channel.id,
                                                mapping_record_product.id_on_channel,
                                                mapping_product_data.get('name'),
                                                message=e)

    @api.model
    def _process_not_existed_mapping_variant(self, master_record_product, mapping_product_data, mapping_record_product,
                                             master_variant_record_product, master_variant_values, mapping_variant_data, mapping_variant_values, 
                                             channel, auto_create_master, auto_override_product):
        if master_variant_record_product:
            self._process_not_existed_mapping_variant_with_product_variant(master_variant_record_product, master_variant_values,
                                                                           mapping_variant_values, channel, auto_override_product)
        else:
            self._process_not_existed_mapping_variant_without_product_variant(master_record_product, mapping_product_data,
                                                                              mapping_record_product, master_variant_values,
                                                                              mapping_variant_data, mapping_variant_values,
                                                                              channel, auto_create_master)

    @api.model
    def _process_mapping_variant(self, master_record_product, mapping_product_data, mapping_variant_data, mapping_record_product,
                                 master_variant_record_product, channel, auto_create_master, auto_override_product):
        mapping_variant_data_clone = copy.deepcopy(mapping_variant_data)
        mapping_variant_values = mapping_record_product.prepare_variant_data(mapping_variant_data_clone)

        master_variant_values = self._prepare_product_variant_data(master_record_product, mapping_product_data, 
                                                                  channel, mapping_variant_values)
        mapping_variant_values.update({
            'product_channel_tmpl_id': mapping_record_product.id,
            'id_on_channel': str(mapping_variant_data['id']),
        })
        product_mapping_variant = mapping_record_product.mapped('product_variant_ids').filtered(
            lambda p: p.id_on_channel == str(mapping_variant_data['id']))

        if product_mapping_variant:
            self._process_existed_mapping_variant(master_record_product=master_record_product, 
                                                  mapping_product_data=mapping_product_data, 
                                                  mapping_record_product=mapping_record_product,
                                                  master_variant_record_product=master_variant_record_product,
                                                  master_variant_values=master_variant_values, 
                                                  product_mapping_variant=product_mapping_variant,
                                                  mapping_variant_data=mapping_variant_data, 
                                                  mapping_variant_values=mapping_variant_values, 
                                                  channel=channel, 
                                                  auto_create_master=auto_create_master, 
                                                  auto_override_product=auto_override_product)
        else:
            self._process_not_existed_mapping_variant(master_record_product, mapping_product_data, mapping_record_product,
                                                      master_variant_record_product, master_variant_values, mapping_variant_data,
                                                      mapping_variant_values, channel, auto_create_master, auto_override_product)

    @api.model
    def _remove_invalid_product_mapping_variant(self, product_mapping, product_template_data):
        current_mapping_variant_ids = list(map(lambda p: str(p['id']), product_template_data.get('variants', [])))
        invalid_prduct_mapping_variants = product_mapping.product_variant_ids.filtered(
            lambda p: p.id_on_channel not in current_mapping_variant_ids)
        invalid_prduct_mapping_variants.unlink()

    @api.model
    def _get_master_product_from_variant_data(self, variant_datas, mapping_sku_vs_product_variants):
        product_template = self.env['product.template'].browse()
        variant_skus = [v['sku'] for v in variant_datas]
        variants = [product for sku, product in mapping_sku_vs_product_variants.items() if sku in variant_skus and sku not in ['', False, None]]
        if variants:
            product_template = variants[0].product_tmpl_id
        return product_template

    @api.model
    def _sync_in_queue_job_with_manage_variants(self, product_data, channel, auto_create_master, auto_override_product):
        product_mappings, mapping_sku_vs_product_variants = self._prepare_mapping_skus(product_data, channel.id)
        product_mapping = product_mappings.filtered(lambda p: p.channel_id.id == channel.id and p.id_on_channel == str(product_data['id']))

        self._check_invalid_mapping(product_mapping, channel.id, auto_create_master, product_data, mapping_sku_vs_product_variants)
    
        variant_datas = product_data.get('variants', [])
        if variant_datas:
            product_template = self._get_master_product_from_variant_data(variant_datas, mapping_sku_vs_product_variants)

        data = copy.deepcopy(product_data)
        product_template = self._create_or_update_product_template(product_template, data, channel, auto_override_product)
        mapping_sku_vs_product_variants.update({v.default_code: v for v in product_template.product_variant_ids.filtered(lambda p: p.default_code)})
        product_mapping = self._create_or_update_product_mapping(product_mapping, product_data, channel.id)
        product_mapping.update({
            'product_tmpl_id': product_template.id
        })

        self._remove_invalid_product_mapping_variant(product_mapping, product_data)
        
        for mapping_variant_data in product_data.get('variants', []):
            product_variant = mapping_sku_vs_product_variants.get(mapping_variant_data['sku'], False)
            if product_variant and product_variant.product_tmpl_id != product_template:
                product_variant = False
            self._process_mapping_variant(master_record_product=product_template, 
                                          mapping_product_data=product_data, 
                                          mapping_variant_data=mapping_variant_data,
                                          mapping_record_product=product_mapping, 
                                          master_variant_record_product=product_variant, 
                                          channel=channel,
                                          auto_create_master=auto_create_master,
                                          auto_override_product=auto_override_product)

    @api.model
    def _sync_in_queue_job_without_manage_variants(self, product_data, channel, auto_create_master, auto_override_product):
        channel_id = channel.id
        product_mappings, mapping_sku_vs_product_variants = self._prepare_mapping_skus(product_data, channel_id)

        product_mapping = product_mappings.filtered(lambda p: p.channel_id.id == channel_id and p.id_on_channel == str(product_data['id']))
        product_template = self.env['product.template'].browse()
        self._check_invalid_mapping(product_mapping, channel_id, auto_create_master,
                                    product_data, mapping_sku_vs_product_variants)

        product_mapping = self._create_or_update_product_mapping(product_mapping, product_data, channel_id)
        product_template = product_mapping.product_tmpl_id

        self._remove_invalid_product_mapping_variant(product_mapping, product_data)
        for mapping_variant_data in product_data.get('variants', []):
            product_variant = mapping_sku_vs_product_variants.get(mapping_variant_data['sku'], False)
            self._process_mapping_variant(master_record_product=product_template,
                                          mapping_product_data=product_data,
                                          mapping_variant_data=mapping_variant_data, 
                                          mapping_record_product=product_mapping,
                                          master_variant_record_product=product_variant, 
                                          channel=channel, 
                                          auto_create_master=auto_create_master, 
                                          auto_override_product=auto_override_product)

    @api.model
    def _sync_in_queue_job(self, product_data, channel_id, auto_create_master=True, auto_override_product=False):
        channel = self.env['ecommerce.channel'].browse(channel_id)
        if self.env.user.has_group('product.group_product_variant'):
            self._sync_in_queue_job_with_manage_variants(product_data, channel, auto_create_master, auto_override_product)
        else:
            self._sync_in_queue_job_without_manage_variants(product_data, channel, auto_create_master, auto_override_product)

    @api.model
    def get_fields_to_list(self, platform, update):
        # Depend on channel we will have listed fields are different
        # Result will contain:
        # If update is false
        # 1. TEMPLATE_FIELDS_LISTED
        # 2. VARIANT_FIELDS_LISTED
        # 3. IGNORE_TEMPLATE_FIELDS
        # else
        # 1. TEMPLATE_FIELDS_UPDATED
        # 2. VARIANT_FIELDS_UPDATED
        # 3. IGNORE_TEMPLATE_FIELDS
        if not update:
            return TEMPLATE_FIELDS_TO_LIST, VARIANT_FIELDS_TO_LIST, []
        else:
            return TEMPLATE_FIELDS_TO_UPDATE, VARIANT_FIELDS_TO_UPDATE, []

    #
    # When synching data or merging from channel, don't create variants by attribute options
    #
    def _create_variant_ids(self):
        if 'for_synching' in self.env.context or 'merge_request' in self.env.context:
            templates = self.filtered(lambda r: r.attribute_line_ids)
            self -= templates
        return super(ProductTemplate, self)._create_variant_ids()

    def unlink(self):
        self.check_and_remove_associated_mapping()
        return super(ProductTemplate, self).unlink()

    def check_and_remove_associated_mapping(self):
        self.ensure_no_active_associated_mapping()
        self.mapped('product_channel_ids').unlink()

    def ensure_no_active_associated_mapping(self):
        unsatisfied = self.mapped('product_variant_ids.product_channel_variant_ids')
        active_channels = self.mapped('product_channel_ids.channel_id').filtered(lambda c: c.active)
        if active_channels or unsatisfied:
            raise UserError(_('There are associated mappings. Please archive instead.'))


