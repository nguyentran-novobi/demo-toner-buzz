# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
import traceback

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

from odoo.addons.omni_manage_channel.utils.common import ImageUtils

from .product_channel import VARIANT_EQUIVALENT_FIELDS, has_differ


_logger = logging.getLogger(__name__)


class ProductChannelVariant(models.Model):
    _name = "product.channel.variant"
    _inherits = {'product.channel': 'product_channel_tmpl_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _description = "Listing Variant"

    display_name = fields.Char(string='Display Name', invisible=True, compute="_get_display_name")
    product_channel_tmpl_id = fields.Many2one('product.channel', string='Product Channel', required=True,
                                              auto_join=True, ondelete='cascade')
    channel_id = fields.Many2one('ecommerce.channel', related='product_channel_tmpl_id.channel_id', store=True)
    product_product_id = fields.Many2one('product.product', string='Product',
                                         ondelete='set null', inverse='_set_product_product')

    state = fields.Selection([('draft', 'Draft'),
                              ('in_progress', 'In Progress'),
                              ('updated', 'Updated'),
                              ('published', 'Published'),
                              ('error', 'Error')], default='draft')
    is_needed_to_export = fields.Boolean(
        'Need to Export',
        compute='_compute_is_needed_to_export',
        search='_search_is_needed_to_export',
    )

    image_platform_url = fields.Char(string='Image of platform of channel', compute='_get_image_platform')
    id_on_channel = fields.Char(string='Product Channel ID',
                                index=True, copy=False, readonly=True,
                                help='ID of product on Channel')
    default_code = fields.Char(string='SKU', copy=False, help='SKU of product', index=True)

    weight_in_oz = fields.Float(string='Weight', copy=False, readonly=True,
                                digits='Stock Weight')

    depth = fields.Float(string='Depth', copy=False)
    height = fields.Float(string='Height', copy=False)
    width = fields.Float(string='Width', copy=False)

    weight_display = fields.Float(copy=False, compute="_compute_weight_display", store=True,
                                  digits='Stock Weight')
    depth_display = fields.Float(copy=False, compute="_compute_dimension_display", store=False)
    height_display = fields.Float(copy=False, compute="_compute_dimension_display", store=False)
    width_display = fields.Float(copy=False, compute="_compute_dimension_display", store=False)

    lst_price = fields.Float(string='Base Price', copy=False, digits='Product Price')
    standard_price = fields.Float(related='product_product_id.standard_price', store=True)
    retail_price = fields.Float(string='MSRP', copy=False, readonly=True, digits='Product Price')
    sale_price = fields.Float(string='Sale Price', copy=False, digits='Product Price')

    quantity = fields.Float(string='Quantity')
    warning_quantity = fields.Float(string='Warning Quantity',
                                    help='When the variant hits this inventory level, it is considered low stock.')
    # ------------------ Shipping ------------------#
    fixed_cost_shipping_price = fields.Float(string='Fixed Shipping Cost')
    is_free_shipping = fields.Boolean(string='Is free shipping')

    warranty = fields.Text(string='Warranty')
    bin_picking_number = fields.Char(string='BIN picking number',
                                     help='Identifies where in a warehouse the variant is located')

    barcode = fields.Char(string='Barcode', help="barcode, UPC, or ISBN number ")
    gtin = fields.Char(string='Global Trade Item Number', readonly=False)
    upc = fields.Char(string='UPC', readonly=True)
    ean = fields.Char(string='EAN', readonly=True)
    isbn = fields.Char(string='ISBN', readonly=True)
    mpn = fields.Char(string='MPN', readonly=True)

    search_keywords = fields.Char(string='Search Keywords')
    attribute_value_ids = fields.Many2many('product.attribute.value', string='Attribute Values', readonly=True)
    variant_option_ids = fields.Many2many('product.attribute', string='Attributes', compute='_compute_option_ids',)
    purchasing_disabled = fields.Boolean(string='Is purchasing disabled?',
                                         help="If True, this variant will not be purchasable on the storefront.")
    purchasable = fields.Boolean(compute='_get_purchasable', inverse='_set_purchasable', string='Purchasable')
    purchasing_disabled_message = fields.Char(
        string='Message when purchasing is disabled',
        help='If purchasing_disabled is True, this message should show on the storefront when the variant is selected.',
    )

    inventory_quantity = fields.Float(string='Inventory Quantity', readonly=True)
    inventory_item_id = fields.Char(string='Inventory Item ID', help='ID for the inventory item')
    inventory_management = fields.Char(string="Inventory Management")
    fulfillment_service = fields.Char(string='Fulfillment Service')

    # all image_variant fields are technical and should not be displayed to the user
    image_variant_1920 = fields.Image("Variant Image", max_width=1920, max_height=1920)

    # resized fields stored (as attachment) for performance
    image_variant_1024 = fields.Image("Variant Image 1204", related="image_variant_1920", max_width=1024,
                                      max_height=1024, store=True)
    image_variant_512 = fields.Image("Variant Image 512", related="image_variant_1920", max_width=512, max_height=512,
                                     store=True)
    image_variant_256 = fields.Image("Variant Image 256", related="image_variant_1920", max_width=256, max_height=256,
                                     store=True)
    image_variant_128 = fields.Image("Variant Image 128", related="image_variant_1920", max_width=128, max_height=128,
                                     store=True)

    image_variant_url = fields.Char(compute='_compute_image_url')
    has_change_image_variant = fields.Boolean(readonly=True)
    description = fields.Text('Description', default='')
    description_sale = fields.Text('Description for the website', default='')
    variant_title = fields.Char(string='Variant Title')
    name = fields.Char(string='Name', compute='_get_name', inverse="_set_name", store=True)

    product_channel_image_id = fields.Many2one('product.channel.image',
                                               domain="[('product_channel_id', '=', product_channel_tmpl_id)]",
                                               inverse='_set_image_variant')

    mapping_quantity = fields.Float(string='Quantity', digits='Product Unit of Measure', default=1)
    
    @api.depends('name', 'default_code')
    def _get_display_name(self):
        for record in self:
            sku = record.default_code
            name = record.name
            attrs = ', '.join(record.attribute_value_ids.mapped('name'))
            sku_comp = f'[{sku}]' if sku else ''
            attrs_comp = f'({attrs})' if attrs else ''
            record.display_name = ' '.join(filter(None, [sku_comp, name, attrs_comp]))

    def remove_publish_message(self):
        self.ensure_one()
        self.with_context(update_status=True).write({'is_publish_message_removed': True})

    def _set_product_product(self):
        return True

    def _set_image_variant(self):
        for record in self:
            record.image_variant_1920 = record.product_channel_image_id.image if record.product_channel_image_id else False

    @api.depends('product_channel_tmpl_id', 'product_channel_tmpl_id.name', 'variant_title')
    def _get_name(self):
        for record in self:
            record.name = record.product_channel_tmpl_id.name

    def _set_name(self):
        for record in self:
            record.variant_title = record.name

    @api.constrains('upc', 'ean', 'gtin')
    def check_upc_ean(self):
        if 'for_synching' not in self.env.context:
            for record in self:
                if record.upc and record.upc != '' and (not record.upc.isdigit() or len(record.upc) not in [6, 8, 12, 13]):
                    raise ValidationError(_('UPC or EAN must be numeric and have a length of 6, 8, 12 or 13 numbers.'))
                if record.ean and record.ean != '' and (not record.ean.isdigit() or len(record.ean) not in [6, 8, 12, 13]):
                    raise ValidationError(_('UPC or EAN must be numeric and have a length of 6, 8, 12, or 13 numbers.'))
                if record.gtin and record.gtin != '' and (not record.gtin.isdigit() or len(record.gtin) not in [8, 12, 13, 14]):
                    raise ValidationError(
                        _('Global Trade Number must be numeric and have a length of 8, 12, 13 or 14 numbers.'))

    def _compute_image_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            model = record.product_product_id._name if record.product_product_id else record._name
            id = record.product_product_id.id if record.product_product_id else record.id
            record.image_variant_url = f"{base_url}/channel/image?model={model}&id={id}&field=image_variant_1920"

    def _get_purchasable(self):
        for record in self:
            record.purchasable = not record.purchasing_disabled

    def _set_purchasable(self):
        for record in self:
            record.purchasing_disabled = not record.purchasable

    def _compute_option_ids(self):
        for record in self:
            record.variant_option_ids = record.attribute_value_ids.mapped('attribute_id')

    def _get_image_platform(self):
        for record in self:
            record.image_platform_url = '/omni_manage_channel/static/src/img/%s.png' % record.channel_id.platform

    def _get_weight_uom_id(self):
        for record in self:
            record.weight_unit_id = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()

    @api.depends('weight_in_oz')
    def _compute_weight_display(self):
        for record in self:
            record.weight_display = record.channel_id._convert_channel_weight(record.weight_in_oz, unit='oz')

    @api.depends('width')
    def _compute_dimension_display(self):
        for record in self:
            convert = record.channel_id._convert_channel_dimension
            record.update({
                'width_display': convert(record.width),
                'height_display': convert(record.height),
                'depth_display': convert(record.depth),
            })

    @api.depends('state')
    def _compute_is_needed_to_export(self):
        updated = self.filtered(lambda r: r.state in ('updated', 'error'))
        updated.is_needed_to_export = True
        (self - updated).is_needed_to_export = False

    @api.model
    def _search_is_needed_to_export(self, operator, value):
        if operator in ('!=', '<>'):
            value = not value
        op = 'in' if value else 'not in'
        return [('state', op, ('updated', 'error'))]

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        # Remove the sum of 'price','standard_price' and quantity in groupby menu
        if 'lst_price' in fields:
            fields.remove('lst_price')
        if 'standard_price' in fields:
            fields.remove('standard_price')
        if 'quantity' in fields:
            fields.remove('quantity')

        return super(ProductChannelVariant, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                             orderby=orderby, lazy=lazy)

    def publish_new_product(self, force_delay=False):

        self[0].with_context(active_test=False).channel_id.ensure_operating()

        if len(self.ids) == 1 and not force_delay:
            if self.state == 'draft' or (not self.id_on_channel and self.state == 'error'):
                try:
                    self._post_product_variant_to_channel()
                except Exception:
                    err_msg = traceback.format_exc()
                    _logger.error('\n' + err_msg)
                    raise ValidationError(_("An error occurred, please try again."))
            elif self.state == 'updated' or (self.id_on_channel and self.state == 'error'):
                try:
                    self.put_to_channel()
                except Exception:
                    err_msg = traceback.format_exc()
                    _logger.error('\n' + err_msg)
                    raise ValidationError(_("An error occurred, please try again."))
            else:
                raise ValidationError(_("Please make sure that the "
                                        "selected product are in 'Draft', 'Updated' or 'Error' status"))
            if self.state == 'error':
                return False
        else:
            if any([record.state not in ['draft', 'updated', 'error'] for record in self]):
                raise ValidationError(
                    _("Please make sure that the selected "
                      "products are in 'Draft', 'Updated' and 'Error' status"))
            for record in self:
                if record.state == 'draft' or (not record.id_on_channel and record.state == 'error'):
                    record.with_delay(channel='root.synching', max_retries=15)._post_product_variant_to_channel()
                elif record.state == 'updated' or (record.id_on_channel and record.state == 'error'):
                    record.with_delay(channel='root.synching', max_retries=15).put_to_channel()
                else:
                    continue
            self.with_context(update_status=True).sudo().write({'state': 'in_progress'})
        return True

    def export_mappings_to_channel(self):
        """
        Export mappings to channel.
        Only export mappings in status "updated". Ignore all other statuses.
        In case of many mappings, process in background
        """
        self[0].with_context(active_test=False).channel_id.ensure_operating()

        rec_to_be_processed = self.filtered(lambda r: r.is_needed_to_export)
        if len(rec_to_be_processed) == 1:
            try:
                rec_to_be_processed.put_to_channel()
            except Exception as e:
                _logger.exception(f'Error while exporting product to channel')
                raise ValidationError(_(f"An error occurred, please try again.\n{str(e)}"))
            if rec_to_be_processed.state == 'error':
                return dict(success=False, msg=rec_to_be_processed.error_message)
        else:
            for record in rec_to_be_processed:
                record.with_delay(channel='root.synching', max_retries=15).put_to_channel()
        return dict(success=True)

    def put_to_channel(self):
        self.ensure_one()
        if not self.with_context(active_test=False).channel_id.active:
            raise ValidationError(_('Your channel has been disconnected. Please contact your administrator.'))
        try:
            self._put_product_variant_to_channel()

            # Update images
            cust_method_name = '%s_update_images' % self.channel_id.platform
            if hasattr(self, cust_method_name):
                getattr(self, cust_method_name)(update=True)

            if self.state == 'published':
                self.with_context(update_status=True).sudo().write({'is_publish_message_removed': False})
            return True
        except Exception as e:
            err_msg = traceback.format_exc()
            _logger.error('\n' + err_msg)
            raise ValidationError(e)

    def delete_record_on_channel(self):
        self.ensure_one()
        if not self.id_on_channel:
            return False
        if not self.with_context(active_test=False).channel_id.active:
            raise ValidationError(_('Your channel has been disconnected. Please contact your administrator.'))

        cust_method_name = '%s_delete_record' % self.channel_id.platform
        if hasattr(self, cust_method_name):
            getattr(self, cust_method_name)()
        else:
            raise UserError(_('This channel does not support deletion method.'))

    def _update_inventory(self, quantity):
        for record in self:
            cust_method_name = '%s_update_quantity' % record.channel_id.platform
            if hasattr(self, cust_method_name):
                getattr(record, cust_method_name)(quantity)

    def _post_product_variant_to_channel(self):
        for record in self:
            cust_method_name = '%s_post_record' % record.channel_id.platform
            if hasattr(self, cust_method_name):
                getattr(record, cust_method_name)()

            if record.id_on_channel:
                # Update images
                cust_method_name = '%s_update_images' % record.channel_id.platform
                if hasattr(self, cust_method_name):
                    getattr(record, cust_method_name)()

    def _put_product_variant_to_channel(self):
        for record in self:
            cust_method_name = '%s_put_record' % record.channel_id.platform
            if hasattr(self, cust_method_name):
                getattr(record, cust_method_name)()

    def sync_data_to_channel(self):
        for record in self:
            if record.id_on_channel:
                record._put_product_variant_to_channel()
            else:
                record._post_product_variant_to_channel()

    @api.model
    def _get_image(self, image_url):
        try:
            if image_url:
                img_base64 = ImageUtils.get_safe_image_b64(image_url)
                return img_base64
        except Exception as e:
            _logger.exception("Cannot get image from %s: %s", image_url, e)
            return None

    def _get_info_from_master(self):
        for record in self.filtered(lambda r: r.product_product_id):
            product = record.product_product_id
            record.write({
                'weight_in_oz': product.weight_in_oz,
                'depth': product.depth,
                'height': product.height,
                'width': product.width,
            })

    def has_changes_from_master(self, vals):
        """
        The purpose is to check whether or not having changes from master data for updating status
        """
        self.ensure_one()
        differs = []
        fields = self.env['product.template'].get_fields_to_list(platform=self.platform, update=True)
        for field in fields[1]:
            if '_ids' in field:
                ids = self[field].mapped('id')
                new_ids = []
                for e in vals.get(field, []):
                    if e[0] == 0 or e[0] == 1:
                        differs.append(True)
                        break
                    elif e[0] == 4 and e[1] not in ids:
                        new_ids.append(e[1])
                    elif e[0] == 6 and ids != e[2]:
                        new_ids.extend(e[2])
                    # TODO: Need to add more cases for other keys (1,2,3)
                new_ids = list(set(new_ids))
                if any(id not in ids for id in new_ids):
                    differs.append(True)
                else:
                    if ids:
                        if field in vals:
                            if vals[field]:
                                if len(vals[field]) == 1 and vals[field][0][5]:
                                    differs.append(True)
                            else:
                                differs.append(True)
            elif '_id' in field:
                differs.append(has_differ(self[field].id, vals.get(field, self[field].id)))
            else:
                differs.append(has_differ(self[field], vals.get(field, self[field])))
        return any(differs)

    def get_dynamic_form_view(self):
        self.ensure_one()
        res_id = self.id
        if self.channel_id.managed_listing_level == 'template':
            res_id = self.product_channel_tmpl_id.id
        return self.channel_id.get_listing_form_view_action(res_id)

    @api.model
    def create(self, vals):
        if 'for_synching' not in self.env.context:
            # For update image to Channel
            vals['has_change_image_variant'] = True
        if 'image_variant_1920' not in vals:
            vals['image_variant_1920'] = self._get_image(vals.get('image_url'))
        record = super(ProductChannelVariant, self).create(vals)
        return record

    def write(self, vals):
        if self.env.context.get('update_status', False):
            return super(ProductChannelVariant, self).write(vals)

        if self.env.context.get('update_thumbnail', False):
            return super(ProductChannelVariant, self).write(vals)

        if len(self.ids) == 1:
            if 'description' in vals:
                value = self._fields['description'].convert_to_cache(vals['description'], self)
                if self.description == value:
                    del vals['description']

            if 'description_sale' in vals:
                value = self._fields['description_sale'].convert_to_cache(vals['description_sale'], self)
                if self.description_sale == value:
                    del vals['description_sale']

        if 'id_on_channel' in vals:
            if vals['id_on_channel']:
                vals['state'] = 'published'
            else:
                vals['state'] = 'draft'

        if 'image_variant_1920' in vals and 'for_synching' not in self.env.context:
            vals['has_change_image_variant'] = True
        # Don't need to update weight if changes is smaller than 0.1
        if 'for_synching' in self.env.context and len(self.ids) == 1 and 'weight_in_oz' in vals:
            if abs(self.weight_in_oz - vals['weight_in_oz']) <= 1e-5:
                del vals['weight_in_oz']

        if 'state' not in vals and 'update_from_master' not in self.env.context:
            if 'for_synching' not in self.env.context and vals:
                if self.state == 'published':
                    vals['state'] = 'updated'
                elif self.state == 'error':
                    if not self.id_on_channel:
                        vals['state'] = 'draft'
                    else:
                        vals['state'] = 'updated'

        res = super(ProductChannelVariant, self).write(vals)

        if not self.env.context.get('set_base_variant', False):
            for record in self.filtered(lambda r: (
                    r.product_channel_tmpl_id
                    and not r.product_channel_tmpl_id.attribute_line_ids
                    and len(r.product_channel_tmpl_id.product_variant_ids) == 1
                    and r.product_channel_tmpl_id.product_variant_id == r)):
                record.product_channel_tmpl_id.with_context(set_base_template=True).update({
                    f[0]: record[f[1]]
                    for f in VARIANT_EQUIVALENT_FIELDS
                    if f[1] in vals
                       and not (f[0] == 'id_on_channel' and record.product_channel_tmpl_id.id_on_channel)
                })

        return res

    def unlink(self):
        templates = self.mapped('product_channel_tmpl_id')
        res = super().unlink()
        if not self.env.context.get('export_from_master'):
            templates.unlink_if_no_variants()
        return res
