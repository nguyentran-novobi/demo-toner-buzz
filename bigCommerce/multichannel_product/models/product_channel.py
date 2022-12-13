# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import re
import traceback
import logging

from operator import attrgetter, or_
from functools import reduce, wraps
from itertools import groupby

from odoo import api, fields, models, registry, _
from odoo.exceptions import ValidationError, UserError

from odoo.addons.http_routing.models.ir_http import slugify

from odoo.addons.omni_base.base_method import _standardize_vals


_logger = logging.getLogger(__name__)


# (fields from model "product.channel", fields from model "product.channel.variant")
# Only simple fields are allowed in this list. Other types may not be supported
VARIANT_EQUIVALENT_FIELDS = [
    ('weight_in_oz', 'weight_in_oz'),
    ('depth', 'depth'),
    ('height', 'height'),
    ('width', 'width'),
    ('lst_price', 'lst_price'),
    ('retail_price', 'retail_price'),
    ('sale_price', 'sale_price'),
    ('default_code', 'default_code'),
    ('barcode', 'barcode'),
]


def has_differ(new, current):
    if isinstance(new, models.Model):
        new = new.id if len(new) == 1 else new.ids
    if isinstance(current, models.Model):
        current = current.id if len(current) == 1 else current.ids
    new = False if new == '' or new == 0.0 or new == 0 or new == ' ' else new
    current = False if current == '' or current == 0.0 or current == 0 or current == ' ' else current
    if type(new) == float:
        new = round(new, 2)
    if type(current) == float:
        current = round(current, 2)
    return True if new != current else False


def validate_exported_fields(vals, exported_fields):
    removed_fields = [field for field in vals.keys() if field not in exported_fields]
    for field in removed_fields:
        del vals[field]
    return vals


def after_commit(func):
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        dbname = self.env.cr.dbname
        context = self.env.context
        uid = self.env.uid

        @self.env.cr.postcommit.add
        def called_after():
            db_registry = registry(dbname)
            with db_registry.cursor() as cr:
                env = api.Environment(cr, uid, context)
                try:
                    func(self.with_env(env), *args, **kwargs)
                except Exception as e:
                    _logger.warning("Could not sync record now: %s" % self)
                    _logger.exception(e)

    return wrapped


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    @api.model
    def set_price_in_queue(self, item_ids):
        self.sudo().write({'item_ids': item_ids})
        return True


class ProductChannelCommonAttributeLine(models.Model):
    _name = 'product.channel.common.attribute.line'
    _description = 'Product Channel Common Attributes'

    attribute_id = fields.Many2one('product.attribute', required=True)
    value_ids = fields.Many2many('product.attribute.value', relation='common_attribute_value_ref')
    product_channel_id = fields.Many2one('product.channel', string='Product Mapping',
                                         required=False, ondelete='cascade')
    is_visible = fields.Boolean(string='Visible', default=True)


class ProductChannelAttributeLine(models.Model):
    _name = "product.channel.attribute.line"
    _description = "Product Channel Attribute Line"

    attribute_id = fields.Many2one('product.attribute', required=True)
    value_ids = fields.Many2many('product.attribute.value')
    product_channel_id = fields.Many2one('product.channel', string='Product Mapping',
                                         required=False, ondelete='cascade')
    is_visible = fields.Boolean(string='Visible', default=True)


class ProductChannel(models.Model):
    _name = "product.channel"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Listing Template"
    _order = "id desc"
    _rec_name = 'display_name'

    display_name = fields.Char(string='Display Name', invisible=True, compute="_get_display_name")
    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True, readonly=True)
    platform = fields.Selection(related='channel_id.platform', string="Platform")
    product_tmpl_id = fields.Many2one('product.template', string='Product Template',
                                      required=False, copy=False, ondelete='restrict')
    product_variant_count = fields.Integer('# Product Variants', compute='_get_number_of_variants')
    product_variant_ids = fields.One2many('product.channel.variant', 'product_channel_tmpl_id', string='Variants')
    product_channel_image_ids = fields.One2many('product.channel.image', 'product_channel_id', string='Images')
    name = fields.Char(string='Name', readonly=False, copy=False)
    id_on_channel = fields.Char(string='Product Channel ID', copy=False, help='ID of product on Channel',
                                readonly=True)

    default_code = fields.Char(string='SKU', copy=False, help='SKU of product', compute='_compute_default_code', 
                               inverse='_set_default_code', store=True)

    weight_in_oz = fields.Float(string='Weight', copy=False, readonly=False,
                                inverse='_set_base_variant', digits='Stock Weight')

    depth = fields.Float(string='Depth', copy=False, readonly=False, inverse='_set_base_variant')
    height = fields.Float(string='Height', copy=False, readonly=False, inverse='_set_base_variant')
    width = fields.Float(string='Width', copy=False, readonly=False, inverse='_set_base_variant')

    weight_display = fields.Float(copy=False, compute="_compute_weight_display", digits='Stock Weight')
    depth_display = fields.Float(copy=False, compute="_compute_dimension_display")
    height_display = fields.Float(copy=False, compute="_compute_dimension_display")
    width_display = fields.Float(copy=False, compute="_compute_dimension_display")

    currency_id = fields.Many2one('res.currency', related="channel_id.currency_id")

    lst_price = fields.Float(string='Base Price', readonly=False,
                             inverse='_set_base_variant', digits='Product Price')
    standard_price = fields.Float(string='Cost', related='product_tmpl_id.standard_price', store=True)
    retail_price = fields.Float(string='MSRP', copy=False,
                                readonly=False, inverse='_set_base_variant', digits='Product Price')
    sale_price = fields.Float(string='Sale Price', copy=False,
                              readonly=False, inverse='_set_base_variant', digits='Product Price')

    categ_ids = fields.Many2many('product.channel.category', string='Categories')
    brand_id = fields.Many2one('product.brand', string='Brand', readonly=True)
    vendor_id = fields.Many2one('product.channel.vendor', string='Vendor')
    inventory_quantity = fields.Float(string='Inventory Quantity', readonly=True)
    warning_quantity = fields.Float(string='Warning Quantity')
    fixed_cost_shipping_price = fields.Float(string='Fixed Shipping Price')
    is_free_shipping = fields.Boolean(string='Free Shipping')
    is_visible = fields.Boolean(string='Visible on Website')
    is_featured = fields.Boolean(string='Featured Product')
    warranty = fields.Text(string='Warranty')
    bin_picking_number = fields.Char(string='BIN picking number')

    search_keywords = fields.Char(string='Search Keywords')
    min_order_qty = fields.Float(string='Minimum Order Qty', default=0.0)
    max_order_qty = fields.Float(string='Maximum Order Qty', default=0.0)
    sort_order = fields.Integer(string='Sort Order')

    barcode = fields.Char(string='Barcode', inverse='_set_base_variant')

    gtin = fields.Char(string='GTIN', readonly=True)
    upc = fields.Char(string='UPC', readonly=True)
    ean = fields.Char(string='EAN', readonly=True)
    isbn = fields.Char(string='ISBN', readonly=True)

    keyword_ids = fields.Many2many('product.channel.keyword', string='Keywords')
    mpn = fields.Char(string='Manufacturer Part Number', readonly=True)
    type = fields.Selection([('physical', 'Physical'),
                             ('digital', 'Digital')], string="Product Type", default='physical',
                            help="Product Type on BigCommerce", readonly=True)

    inventory_tracking = fields.Boolean(string='Track Inventory', readonly=True, default=False)

    attribute_line_ids = fields.One2many('product.channel.attribute.line', 'product_channel_id', 'Product Attributes')
    common_attribute_line_ids = fields.One2many('product.channel.common.attribute.line',
                                                'product_channel_id', 'Common Attributes')

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

    availability = fields.Selection([
        ('available', 'This product can be purchased in my online store'),
        ('preorder', 'This product is coming soon but I want to take pre-orders'),
        ('disabled', 'This product cannot be purchased in my online store'),
    ], string="Availability", default='available')
    availability_description = fields.Char(string='Availability Description')
    meta_description = fields.Text('Meta Description', translate=True)
    description = fields.Text('Description', default='')
    description_sale = fields.Text('Description for the website', default='')
    active = fields.Boolean('Active', default=True,
                            help="If unchecked, it will allow you to hide the product in channel without removing it.")

    has_options = fields.Boolean(compute='_get_options')
    slug = fields.Char()
    url = fields.Char(string='Storefront URL')

    product_variant_id = fields.Many2one('product.channel.variant',
                                         string='Base Variant',
                                         compute='_get_base_product_variant',
                                         store=True)
    product_product_id = fields.Many2one('product.product',
                                         string='Master Base Variant',
                                         related='product_variant_id.product_product_id')
    is_show_variants = fields.Boolean(compute='_is_show_variants', store=True)

    # For message
    is_publish_message_removed = fields.Boolean(default=False, readonly=True)
    error_message = fields.Text(readonly=True)

    # For updating images
    has_change_image = fields.Boolean(readonly=True)

    image_1920 = fields.Image(readonly=True)

    weight_unit = fields.Selection(related='channel_id.weight_unit', string='Weight Unit')
    dimension_unit = fields.Selection(related='channel_id.dimension_unit', string='Dimension Unit')
    weight_unit_symbol = fields.Char(
        compute='_compute_weight_dimension_unit_symbol',
        string='Weight Unit Symbol',
    )
    dimension_unit_symbol = fields.Char(
        compute='_compute_weight_dimension_unit_symbol',
        string='Dimension Unit Symbol',
    )

    _sql_constraints = [
        ('uniq_channel', 'unique (id_on_channel,channel_id)',
         'This product already exists !')
    ]

    @api.depends('product_variant_ids', 'product_variant_ids.default_code')
    def _compute_default_code(self):
        products_w_def_variant = self.filtered(
            lambda tmpl: len(tmpl.product_variant_ids) == 1 and not tmpl.attribute_line_ids)
        for template in products_w_def_variant:
            template.default_code = template.product_variant_ids.default_code
        (self - products_w_def_variant).update({'default_code': False})

    def _set_default_code(self):
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.product_variant_ids.default_code = template.default_code

    @api.depends('name', 'default_code', 'product_variant_id.default_code')
    def _get_display_name(self):
        for record in self:
            record.display_name = f"[{record.default_code}] {record.name}" if len(record.product_variant_ids) == 1 and record.default_code else f"{record.name}"

    def _get_number_of_variants(self):
        for record in self:
            if not record.attribute_line_ids and record.platform != 'amazon':
                record.product_variant_count = 0
            else:
                record.product_variant_count = len(record.product_variant_ids)

    @api.constrains('upc', 'ean', 'gtin')
    def check_upc_ean(self):
        if 'for_synching' not in self.env.context:
            for record in self:
                if record.upc and (not record.upc.isdigit() or len(record.upc) not in [6, 8, 12, 13]):
                    raise ValidationError(_('UPC or EAN must be numeric and have a length of 6, 8, 12 or 13 numbers.'))
                if record.ean and (not record.ean.isdigit() or len(record.ean) not in [6, 8, 12, 13]):
                    raise ValidationError(_('UPC or EAN must be numeric and have a length of 6, 8, 12, or 13 numbers.'))
                if record.gtin and (not record.gtin.isdigit() or len(record.gtin) not in [8, 12, 13, 14]):
                    raise ValidationError(_('Global Trade Number must be numeric and have a length of 8, 12, 13 or 14 numbers.'))

    @api.constrains('attribute_line_ids', 'common_attribute_line_ids')
    def check_attributes(self):
        if 'for_synching' in self.env.context:
            return True
        for record in self:
            variant_attrs = record.attribute_line_ids.mapped('attribute_id')
            common_attrs = record.common_attribute_line_ids.mapped('attribute_id')
            intersection = set(variant_attrs.ids).intersection(set(common_attrs.ids))
            if intersection:
                attrs = common_attrs.filtered(lambda a: a.id in intersection)
                if len(attrs) == 1:
                    raise ValidationError(_('This attribute must not be a common attribute: %s'
                                            % ', '.join(attrs.mapped('name'))))
                else:
                    raise ValidationError(_('These attributes must not be common attributes: %s'
                                            % ', '.join(attrs.mapped('name'))))

    @api.constrains('min_order_qty', 'max_order_qty')
    def check_min_max_order_quantity(self):
        if 'for_synching' not in self.env.context:
            for record in self:
                if record.min_order_qty < 0 or record.max_order_qty < 0:
                    raise ValidationError(_('Minimum Purchase Qty, Maximum Purchase Qty must be positive integer'))

    @api.depends('product_variant_ids')
    def _get_base_product_variant(self):
        for p in self:
            p.product_variant_id = p.product_variant_ids[:1].id

    def _set_base_variant(self):
        if not self.env.context.get('set_base_template', False):
            for record in self:
                if len(record.product_variant_ids) == 1 and not record.attribute_line_ids:
                    record.product_variant_id.with_context(set_base_variant=True).update({
                        f[1]: record[f[0]]
                        for f in VARIANT_EQUIVALENT_FIELDS
                    })

    @api.depends('attribute_line_ids')
    def _is_show_variants(self):
        for record in self:
            record.is_show_variants = True if record.attribute_line_ids else False

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

    @api.depends('channel_id', 'channel_id.weight_unit', 'channel_id.dimension_unit')
    def _compute_weight_dimension_unit_symbol(self):
        records = self.sorted('channel_id')
        for channel, channel_group in groupby(records, key=attrgetter('channel_id')):
            channel_records = reduce(or_, channel_group)
            channel_records.update({
                'weight_unit_symbol': channel.weight_unit,
                'dimension_unit_symbol': channel.dimension_unit,
            })

    def remove_publish_message(self):
        self.ensure_one()
        self.with_context(update_status=True).write({'is_publish_message_removed': True})

    @api.constrains('attribute_line_ids')
    def _check_attribute_line(self):
        if any(len(template.attribute_line_ids) != len(template.attribute_line_ids.mapped('attribute_id')) for template
               in self):
            raise ValidationError(_('You cannot define two attribute lines for the same attribute.'))
        return True

    @api.constrains('product_channel_image_ids')
    def _check_invalid_multiple_thumbnail(self):
        for record in self:
            if 'for_synching' not in self.env.context:
                images = self.env['product.channel.image'].sudo().search(
                    [('product_channel_id.id', '=', record.id), ('is_thumbnail', '=', True)])
                if len(images) > 1:
                    raise ValidationError(
                        _('Please make sure that you choose only one image as the product thumbnail.'))
        return True

    @api.constrains('slug')
    def _check_slug(self):
        pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
        for record in self.filtered(attrgetter('slug')):
            adj_slug = record.slug
            adj_slug = adj_slug[1:] if adj_slug.startswith('/') else adj_slug
            adj_slug = adj_slug[:-1] if adj_slug.endswith('/') else adj_slug
            if not all(map(lambda s: re.match(pattern, s), adj_slug.split('/'))):
                raise ValidationError(_('"%s" is an invalid Product URL', record.slug))
        return True

    def _update_data(self, vals, mapping_by_attribute=True, no_update_image=False):
        self.ensure_one()
        vals['product_variant_ids'] = []
        remain_variant_ids = []
        for variant in vals.get('variants', []):
            variant_data = self.prepare_variant_data(variant)

            if no_update_image and 'product_channel_image_id' in variant_data:
                del variant_data['product_channel_image_id']

            #
            # Using id_on_channel to search product channel variant
            # For product channel variant don't have id_on_channel, use attribute to match
            #
            product_channel_variant = self.env['product.channel.variant']
            attribute_value_ids = variant_data['attribute_value_ids'][0][
                2] if 'attribute_value_ids' in variant_data else []
            for e in self.product_variant_ids:
                if e.id_on_channel and e.id_on_channel == str(variant['id']):
                    product_channel_variant = e
                elif e.default_code and e.default_code == variant['sku']:
                    product_channel_variant = e
                elif attribute_value_ids and set(e.attribute_value_ids.ids) == set(attribute_value_ids):
                    product_channel_variant = e

                if not product_channel_variant and mapping_by_attribute \
                        and set(e.attribute_value_ids.ids) == set(attribute_value_ids):
                    product_channel_variant = e

            if not product_channel_variant.product_product_id \
                    and 'auto_merge_variant' in self.env.context and self.env.context['auto_merge_variant']:

                product_product = self.product_tmpl_id.get_product_product_by_variant_data(channel=self.channel_id,
                                                                                           variant_values=variant_data,
                                                                                           new_master=True,
                                                                                           auto_merge_variant=True)
                if product_product:
                    variant_data['product_product_id'] = product_product.id
            if product_channel_variant:
                remain_variant_ids.append(product_channel_variant.id)
                update_vals = variant_data
                if 'request_from_app' in self.env.context:
                    # If create from app, we just need to update id_on_channel
                    update_vals = {'id_on_channel': variant_data['id_on_channel'],
                                   'inventory_item_id': variant_data.get('inventory_item_id', False)}
                vals['product_variant_ids'].append(
                    (1, product_channel_variant.id, _standardize_vals(env=self.env,
                                                                      model=product_channel_variant._name,
                                                                      datas=update_vals)))
            else:
                variant_data.update({
                    'product_channel_tmpl_id': self.id,
                    'id_on_channel': str(variant['id']),
                    'state': 'published'
                })

                vals['product_variant_ids'].append(
                    (0, 0, _standardize_vals(env=self.env,
                                             model=product_channel_variant._name,
                                             datas=variant_data)))
        if 'variants' in vals:
            # Delete variants that didn't exist on channel
            removed_variants = self.product_variant_ids.filtered(lambda p: p.id not in remain_variant_ids)
            if removed_variants:
                removed_variants.unlink()

        if 'request_from_app' in self.env.context:
            # Only update id_on_channel for mapping when put or post request from Odoo
            vals = {
                'product_variant_ids': vals['product_variant_ids'],
                'id_on_channel': vals['id_on_channel'],
                'state': 'published',
                'url': vals.get('url', ''),
                'slug': vals.get('slug', ''),
            }
            # No update for state when exporting from master
            if 'export_from_master' in self.env.context:
                del vals['state']

        self.with_context(for_synching=True).sudo().write(_standardize_vals(env=self.env,
                                                                            model=self._name,
                                                                            datas=vals))

    @api.model
    def prepare_product_channel(self, product_data, channel_id):
        """
        Prepare product mapping data from data from store
        """

        remove_keys = []
        for key in product_data:
            if product_data[key] == '' or product_data[key] is False or product_data[key] is None:
                remove_keys.append(key)
        for key in remove_keys:
            del product_data[key]

        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)

        # product_data['image'], product_data['images'] = self.env['product.channel.image'].get_product_images(
        #     product_data.get('images', []), channel)

        product_channel_vals = {
            'name': str(product_data.get('name', '')),
            'lst_price': float(product_data.get('price', 0.0)),
            'retail_price': float(product_data.get('retail_price', 0.0)),
            'sale_price': float(product_data.get('sale_price', 0.0)),
            'default_code': str(product_data.get('sku', '')),
            'id_on_channel': str(product_data.get('id')),
            'channel_id': channel_id,
            'vendor_id': self.env['product.channel.vendor'].get_vendor(product_data.get('vendor')).id,
            'attribute_line_ids': product_data.get('attribute_line_ids', False),
            'common_attribute_line_ids': [(5, 0, 0)] + product_data.get('common_attribute_line_ids', []),
            'availability': product_data.get('availability'),
            'is_visible': bool(product_data.get('is_visible', False)),
            'condition': product_data.get('condition'),
            'min_order_qty': float(product_data.get('order_quantity_minimum', 0.0)),
            'max_order_qty': float(product_data.get('order_quantity_maximum', 0.0)),
            'sort_order': int(product_data.get('sort_order', 0)),
            'description': str(product_data.get('description', '')),
            'description_sale': str(product_data.get('description_sale', '')),
            'meta_description': str(product_data.get('meta_description', '')),
            'type': product_data.get('type', 'physical'),
            'inventory_quantity': product_data.get('inventory_quantity', 0.0),
            'inventory_tracking': product_data.get('inventory_tracking', False),
            'is_free_shipping': bool(product_data.get('is_free_shipping', False)),
            'fixed_cost_shipping_price': float(product_data.get('fixed_cost_shipping_price', 0.0)),
            'bin_picking_number': str(product_data.get('bin_picking_number', '')),
            'barcode': str(product_data.get('barcode', '')),
            'published_scope': product_data.get('published_scope', False),
            'state': 'published',
            'mpn': str(product_data.get('mpn', '')),
            'width': channel._convert_channel_dimension(product_data.get('width', 0.0), inverse=True),
            'height': channel._convert_channel_dimension(product_data.get('height', 0.0), inverse=True),
            'depth': channel._convert_channel_dimension(product_data.get('depth', 0.0), inverse=True),
            'weight_in_oz': channel._convert_channel_weight(product_data.get('weight', 0.0), unit='oz', inverse=True),
            'url': str(product_data.get('url', '')),
            'slug': str(product_data.get('slug', '')),
            'platform': channel.platform
        }

        if 'export_from_master' not in self.env.context:
            cust_method_name = '%s_prepare_image_data' % channel.platform
            if hasattr(self, cust_method_name) and product_data.get('images', []):
                thumbnail, product_channel_image_ids = getattr(self, cust_method_name)(product_data['images'], channel)
                product_channel_vals.update({
                    'image_1920': thumbnail,
                })
                if product_channel_image_ids:
                    product_channel_vals.update({'product_channel_image_ids': [(5, 0, 0)] + product_channel_image_ids})

        # For some channels, we don't have all these fields
        for field in ['upc', 'ean', 'isbn', 'gtin']:
            if field in product_data:
                product_channel_vals[field] = product_data[field]

        # For updating cases:
        if self:
            # 'attribute_line_ids' in product_data is always is a list value for creating new line.
            # Need to check if line existed
            attribute_line_ids = product_data.get('attribute_line_ids', False)
            line_values = attribute_line_ids
            updated_lines = []
            if attribute_line_ids and self.attribute_line_ids:
                line_values = []
                for e in attribute_line_ids:
                    if e[0] == 0:
                        attribute_id = e[2]['attribute_id']
                        value_ids = e[2]['value_ids']
                        line = self.attribute_line_ids.filtered(lambda l: l.attribute_id.id == attribute_id)
                        if line:
                            updated_lines.append(line.id)
                            line_values.append((1, line.id, {'value_ids': value_ids}))
                        else:
                            line_values.append(e)

            removed_lines = self.attribute_line_ids.filtered(lambda l: l.id not in updated_lines)
            removed_lines.unlink()

            product_channel_vals['attribute_line_ids'] = line_values
        return product_channel_vals

    def prepare_variant_data(self, variant_data):
        def _float(v):
            try:
                return float(v)
            except ValueError:
                return 0.0

        self.ensure_one()
        channel = self.channel_id

        remove_keys = []
        for key in variant_data:
            if not variant_data[key]:
                remove_keys.append(key)
        for key in remove_keys:
            del variant_data[key]

        variant_values = {
            'id_on_channel': str(variant_data.get('id')),
            # Price
            'lst_price': _float(variant_data.get('price', 0.0)),
            'retail_price': _float(variant_data.get('retail_price', 0.0)),
            'sale_price': _float(variant_data.get('sale_price', 0.0)),
            # Measurement
            'weight_in_oz': channel._convert_channel_weight(
                _float(variant_data.get('weight', 0.0)), unit='oz', inverse=True),
            'weight_unit_id': variant_data.get('weight_unit_id'),
            'width': channel._convert_channel_dimension(_float(variant_data.get('width', 0.0)), inverse=True),
            'height': channel._convert_channel_dimension(_float(variant_data.get('height', 0.0)), inverse=True),
            'depth': channel._convert_channel_dimension(_float(variant_data.get('depth', 0.0)), inverse=True),
            # Inventory
            'inventory_quantity': _float(variant_data.get('inventory_quantity', 0.0)),
            'warning_quantity': _float(variant_data.get('inventory_warning_level', 0.0)),
            'inventory_item_id': str(variant_data.get('inventory_item_id', '')),
            'inventory_management': str(variant_data.get('inventory_management', '')),
            'bin_picking_number': str(variant_data.get('bin_picking_number', '')),
            # Shipping and fulfillment
            'is_free_shipping': bool(variant_data.get('is_free_shipping', False)),
            'fulfillment_service': str(variant_data.get('fulfillment_service', '')),
            'barcode': str(variant_data.get('barcode', '')),
            # Basic Information
            'purchasing_disabled': bool(variant_data.get('purchasing_disabled', False)),
            'default_code': str(variant_data.get('sku', '')),
            'mpn': str(variant_data.get('mpn', '')),
            'description': variant_data.get('description', ''),
            'description_sale': variant_data.get('description_sale', ''),
            'variant_title': variant_data.get('variant_title', '')
        }

        # For some channels, we don't have all these fields
        for field in ['upc', 'ean', 'isbn', 'gtin']:
            if field in variant_data:
                variant_values[field] = variant_data[field]

        if 'image_url' in variant_data:
            variant_values['image_variant_1920'] = self.env['product.channel.variant']._get_image(variant_data['image_url'])
        else:
            variant_values['image_variant_1920'] = False

        option_values = variant_data.get('option_values')
        if option_values:
            attribute_values = self.env['product.attribute.value']
            attributes = []
            values = []
            for option_value in option_values:
                attributes.append(option_value['option_display_name'])
                values.append(option_value['label'])

            attribute_values = attribute_values.sudo().search([('attribute_id.name', 'in', attributes), ('name', 'in', values)])
            if attribute_values:
                attribute_values_ids = attribute_values.mapped('id')
                if len(option_values) != len(attribute_values):
                    attribute_values_ids = []
                    for option_value in option_values:
                        attribute_values_ids.append(attribute_values.filtered(lambda v: v.attribute_id.name == option_value['option_display_name'] 
                                                                              and v.name == option_value['label']).id)

                variant_values['attribute_value_ids'] = [(6, 0, attribute_values_ids)]
        return variant_values

    def get_data_from_channel(self):
        self.ensure_one()
        context = self.env.context.copy()

        self.with_context(active_test=False).channel_id.ensure_operating()

        cust_method_name = '%s_get_data' % self.channel_id.platform
        if hasattr(self, cust_method_name):
            method = getattr(self, cust_method_name)
            # Result from this method must be standardized by "prepare_product_channel"
            vals = method()
            if vals:
                # if 'product_channel_image_ids' in vals:
                #     # Images will be updated before
                #     self.sudo().write({'product_channel_image_ids': vals['product_channel_image_ids']})
                #     del vals['product_channel_image_ids']
                #     self.env.cr.commit()
                vals['is_publish_message_removed'] = True
                self.with_context(dict(context, request_from_app=True))._update_data(vals)
        return {}

    def delete_record_on_channel(self):
        self.ensure_one()
        self[0].with_context(active_test=False).channel_id.ensure_operating()

        cust_method_name = '%s_delete_record' % self.channel_id.platform
        if hasattr(self, cust_method_name):
            method = getattr(self, cust_method_name)
            if self.id_on_channel:
                return method(self.id_on_channel)
        else:
            raise UserError(_('This channel does not support deletion method.'))

    def set_to_draft(self):
        published_records = self.filtered(lambda r: r.id_on_channel and r.state not in ('draft', 'in_progress'))
        successful = self.browse()
        for record in published_records:
            record.write({'state': 'in_progress'})
            result = record.delete_record_on_channel()
            if result is True:
                successful |= record

        successful.with_context(update_status=True).write({
            'state': 'draft',
            'id_on_channel': False,
        })
        successful.mapped('product_channel_image_ids').write({'id_on_channel': False})
        successful.mapped('product_variant_ids').with_context(update_status=True).write({
            'id_on_channel': False,
        })
        return successful

    def remove_online_and_mapping(self):
        self.set_to_draft()
        action_values = self.channel_id.menu_listing_id.action.sudo().read()[0]
        action_values['target'] = 'main'
        self.unlink()
        return action_values

    def check_new_options(self, vals):
        self.ensure_one()
        new_options = {}
        options = {}
        for e in vals['attribute_line_ids']:
            options[e[2]['attribute_id']] = e[2]['value_ids'][0][2]
        for key in options:
            attribute_line = self.attribute_line_ids.filtered(lambda l: l.attribute_id.id == key)
            if attribute_line:
                current_value_ids = attribute_line.value_ids.mapped('id')
                differ = [i for i, j in zip(current_value_ids, options[key]) if i != j]
                if differ:
                    new_options[key] = differ
            else:
                new_options[key] = options[key]
        return new_options

    @api.depends('attribute_line_ids')
    def _get_options(self):
        for record in self:
            record.has_options = True if record.attribute_line_ids else False

    @api.depends('weight_in_oz')
    def _compute_weight_display(self):
        for record in self:
            record.weight_display = record.channel_id._convert_channel_weight(record.weight_in_oz, unit='oz')

    @api.depends('width', 'height', 'depth')
    def _compute_dimension_display(self):
        for record in self:
            convert = record.channel_id._convert_channel_dimension
            record.update({
                'width_display': convert(record.width),
                'height_display': convert(record.height),
                'depth_display': convert(record.depth),
            })

    def name_get(self):
        result = []
        for record in self:
            if record.default_code:
                result.append((record.id, '[%s] %s' % (record.default_code, record.name)))
            else:
                result.append((record.id, '%s' % record.name))
        return result

    def _post_extra_info_to_channel(self):
        pass

    def _put_extra_info_to_channel(self):
        pass

    def _push_to_channel(self, exported_fields: dict = None):
        # if not self.channel_id.can_export_product_from_mapping:
        #     raise ValidationError(_("You cannot export mapping to store. Please check your settings in store settings and try again."))
        datas = {}
        cust_method_name = '%s_post_record' % self.channel_id.platform
        if hasattr(self, cust_method_name):
            product_data = getattr(self, cust_method_name)(exported_fields=exported_fields or {})
            datas.update({'product': product_data})
        if self.id_on_channel:
            if self.channel_id.get_setting('manage_images'):
                # Update images
                cust_method_name = '%s_update_images' % self.channel_id.platform
                if hasattr(self, cust_method_name):
                    # Send image in background
                    image_data = getattr(self, cust_method_name)()
                    datas.update({'image': image_data})

            # Channel specific post method
            cust_method_name = '%s_post_extra_info' % self.channel_id.platform
            if hasattr(self, cust_method_name):
                extra_data = getattr(self, cust_method_name)()
                datas.update({'extra': extra_data})

            if self.channel_id.is_enable_inventory_sync:
                self.env['stock.move'].with_context(normal_inventory_update=True).inventory_sync(channel_id=self.channel_id.id,
                                                                                                 product_product_ids=self.product_tmpl_id.product_variant_ids.ids)

            self.with_context(update_status=True).sudo().write({'is_publish_message_removed': False, 'state': 'published'})
        elif self.state == 'error':
            message = self.error_message
            self.unlink()
            self.env.cr.commit()
            raise ValidationError(_(message))
        return datas

    def _put_to_channel(self, exported_fields: dict = None):
        if not self.channel_id.can_export_product_from_mapping and 'export_from_master' not in self.env.context:
            raise ValidationError(_("You cannot export mapping to store. Please check your settings in store settings and try again."))
        cust_method_name = '%s_put_record' % self.channel_id.platform
        datas = {}
        if hasattr(self, cust_method_name):
            product_data = getattr(self, cust_method_name)(exported_fields=exported_fields or {})
            datas.update({'product_data': product_data})

        # Channel specific put method
        cust_method_name = '%s_put_extra_info' % self.channel_id.platform
        if hasattr(self, cust_method_name):
            extra_data = getattr(self, cust_method_name)()
            datas.update({'extra': extra_data})

        if self.state != 'error' or 'export_from_master' in self.env.context:
            self.get_data_from_channel()
            self.with_context(update_status=True).sudo().write({'is_publish_message_removed': False})

        if self.channel_id.get_setting('manage_images'):
            # Update images
            cust_method_name = '%s_update_images' % self.channel_id.platform
            if hasattr(self, cust_method_name):
                image_data = getattr(self, cust_method_name)(update=True)
                datas.update({'image': image_data})

        # # Channel specific put method for inventory item
        # cust_method_name = '%s_update_inventory_item' % self.channel_id.platform
        # if hasattr(self.env['product.channel.variant'], cust_method_name):
        #     getattr(self.product_variant_ids, cust_method_name)()
        return datas

    def publish_new_product(self, force_delay=False):

        self[0].with_context(active_test=False).channel_id.ensure_operating()

        if len(self.ids) == 1 and not force_delay:
            if self.state == 'draft' or (not self.id_on_channel and self.state == 'error'):
                try:
                    self._push_to_channel()
                except Exception as e:
                    err_msg = traceback.format_exc()
                    _logger.error('Error while posting product to channel\n' + err_msg)
                    raise ValidationError(_(f"An error occurred, please try again.\n{str(e)}"))
            elif self.state == 'updated' or (self.id_on_channel and self.state == 'error'):
                try:
                    self.put_to_channel()
                except Exception as e:
                    err_msg = traceback.format_exc()
                    _logger.error('Error while updating product to channel\n' + err_msg)
                    raise ValidationError(_(f"An error occurred, please try again.\n{str(e)}"))
            else:
                raise ValidationError(_("Please make sure that the selected product are in 'Draft', 'Updated' or 'Error' status"))
            if self.state == 'error':
                return False
        else:
            if any([record.state not in ['draft', 'updated', 'error'] for record in self]):
                raise ValidationError(
                    _("Please make sure that the selected products are in 'Draft', 'Updated' and 'Error' status"))
            for record in self:
                if record.state == 'draft' or (not record.id_on_channel and record.state == 'error'):
                    record.with_delay(channel='root.synching', max_retries=15)._push_to_channel()
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
                rec_to_be_processed.export_from_mapping()
            except ValidationError as e:
                raise e
            except Exception as e:
                _logger.exception('Error while exporting product to channel')
                raise ValidationError(_(f"An error occurred, please try again.\n{str(e)}"))
        else:
            context = self.env.context.copy()
            for record in rec_to_be_processed:
                record.with_context(dict(context, delay_exec=True))\
                    .with_delay(channel='root.synching', max_retries=15).export_from_mapping()
        return dict(success=True)

    def export_from_mapping(self):
        self.ensure_one()
        self.with_context(active_test=False).channel_id.ensure_operating()
        fields = self.channel_id.get_setting('product_exported_fields')
        exported_fields = {
            'template': fields['mapping_template'],
            'variant': fields['mapping_variant']
        }
        try:
            datas = self._put_to_channel(exported_fields)
        except ValidationError as e:
            raise e
        except Exception as e:
            _logger.exception('Error while exporting product to channel')
            raise ValidationError(_(f"An error occurred, please try again.\n{str(e)}"))

        if 'job_uuid' in self.env.context:
            vals = {'datas': datas,
                    'channel_id': self.channel_id.id,
                    'operation_type': 'export_mapping',
                    'res_model': self._name,
                    'entity_name': self.display_name,
                    'job_uuid': self.env.context['job_uuid'],
                    }
            log = self.env['omni.log'].create(vals)
            status = 'done'
            message = None
            if self.state == 'error':
                status = 'failed'
                message = ','.join(self.mapped('error_message'))
            log.update_status(status, message)

    def open_on_store(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': "%s%s" % (self.channel_id.secure_url, self.url),
            'target': 'new',
        }

    def write(self, vals):
        if 'update_status' in self.env.context:
            return super(ProductChannel, self).write(vals)

        if 'update_thumbnail' in self.env.context:
            return super(ProductChannel, self).write(vals)

        if len(self.ids) == 1:
            # Don't need to update weight if changes is inconsiderable
            if 'weight_in_oz' in vals and 'for_synching' in self.env.context:
                if abs(self.weight_in_oz - vals['weight_in_oz']) <= 1e-5:
                    del vals['weight_in_oz']

            if 'description' in vals:
                value = self._fields['description'].convert_to_cache(vals['description'], self)
                if self.description == value:
                    del vals['description']

            if 'description_sale' in vals:
                value = self._fields['description_sale'].convert_to_cache(vals['description_sale'], self)
                if self.description_sale == value:
                    del vals['description_sale']

            if vals.get('product_channel_image_ids', []):
                for i in vals['product_channel_image_ids']:
                    if i[0] == 0 and i[2].get('is_thumbnail', False):
                        vals['image_1920'] = i[2]['image']
                    elif i[0] == 1 and 'image' in i[2] and self.env['product.channel.image'].browse(i[1]).is_thumbnail:
                        vals['image_1920'] = i[2]['image']

        if 'product_channel_image_ids' in vals and 'has_change_image' not in vals:
            vals['has_change_image'] = True
        if 'for_synching' not in self.env.context:
            for record in self:
                if record.state == 'in_progress':
                    raise ValidationError(_('Updating product is in progress. Please try again later!'))
        #
        #
        # Updating from master is only run on each records.
        # "Published" will be "Updated".
        # "Error" will be "Draft" if that product isn't published
        #
        #

        if 'state' not in vals and 'export_from_master' not in self.env.context:
            for record in self:
                if 'for_synching' not in self.env.context and vals:
                    if record.state == 'published':
                        vals['state'] = 'updated'
                    elif record.state == 'error':
                        if not record.id_on_channel:
                            vals['state'] = 'draft'
                        else:
                            vals['state'] = 'updated'

        res = super(ProductChannel, self).write(vals)

        if 'product_channel_image_ids' in vals:
            for record in self:
                thumbnail = record.product_channel_image_ids.filtered(lambda r: r.is_thumbnail)
                if thumbnail:
                    record.sudo().with_context(update_thumbnail=True).write({'image_1920': thumbnail.image})
                else:
                    record.sudo().with_context(update_thumbnail=True).write({'image_1920': False})
        return res

    @api.model
    def has_merge_request_for_variant(self):
        return False

    @api.model
    def has_merge_request(self):
        return False

    def has_changes_from_master(self, vals):
        return False

    @api.model
    def check_need_to_update_images(self, vals):
        custom_method_name = '%s_check_need_to_update_images' % self.platform
        if hasattr(self, custom_method_name):
            return getattr(self, custom_method_name)(vals)
        return True

    def check_need_to_merge(self):
        return None

    def check_need_to_update(self, vals_ids_field={}):
        return None

    def get_updated_fields(self):
        # Depend on channel we will have updated fields are different
        # Result will contain:
        # 1. UPDATED_TEMPLATE_FIELDS
        # 2. UPDATED_VARIANT_FIELDS
        # 3. IGNORE_TEMPLATE_FIELDS
        return [], [], []

    def get_merged_template_fields(self):
        # Depend on channel we will have merged fields are different
        return []

    def get_merged_variant_fields(self):
        # Depend on channel we will have merged fields are different
        return [], []

    @api.model
    def get_product_channel_for_synching(self, ids, channel_id):
        existed_records = self.sudo().search([('id_on_channel', 'in', ids),
                                              ('channel_id.id', '=', channel_id)])
        return existed_records

    @api.model
    def create(self, vals):
        if vals.get('product_channel_image_ids', []):
            for i in vals['product_channel_image_ids']:
                if i[0] == 0 and i[2].get('is_thumbnail', False):
                    vals['image_1920'] = i[2]['image']
        return super(ProductChannel, self).create(vals)

    def _log_debugging_msg(self, msg):
        self.ensure_one()
        if self.channel_id.debug_logging:
            self.message_post(body=msg)

    def button_manually_sync_inventory(self):
        self.ensure_one()
        self.env['stock.move'].sudo().with_context(no_delay=True).inventory_sync(
            channel_id=self.channel_id.id,
            all_records=True,
            nightly_update=False,
            product_product_ids=self.product_variant_ids.mapped('product_product_id').ids,
        )

    @api.model
    def export_from_master_data(self, ids, channel_id, vals, is_created=False):
        channel = self.env['ecommerce.channel'].browse(channel_id)
        fields = channel.get_setting('product_exported_fields')
        exported_fields = {
            'template': fields['master_template'],
            'variant': fields['master_variant']
        }
        context = self.env.context.copy()
        if not is_created:
            product_channels = self.sudo().browse(ids)
            product_channels.with_context(dict(context, export_from_master=True)).write(vals)
            for product_channel in product_channels:
                if 'delay_exec' in self.env.context:
                    product_channel = product_channel.with_delay()
                product_channel.update_from_master_data(exported_fields)
        else:
            record = self.with_context(dict(context, export_from_master=True)).create(vals)
            if 'delay_exec' in self.env.context:
                record = record.with_delay()
            product_channels = record.create_from_master_data(exported_fields)
        return product_channels

    def check_sku_require_for_export(self):
        if any(not v.default_code for v in self.product_variant_ids):
            self.with_context(update_status=True).update({
                'state': 'error',
                'error_message': 'SKU must be required!'
            })
            return False
        return True

    def get_default_data_for_log(self):
        return {
            'name': self.display_name,
            'sku': self.default_code,
            'variants': [{
                'name': v.display_name,
                'sku': v.default_code or '',
            } for v in self.product_variant_ids]
        }

    def do_export_from_master_data(self, channel):
        ex_fields = channel.get_setting('product_exported_fields')
        exported_fields = {
            'template': ex_fields['master_template'],
            'variant': ex_fields['master_variant'],
        }
        for product_channel in self:
            is_to_update = bool(product_channel.id_on_channel)
            if 'delay_exec' in self.env.context:
                product_channel = product_channel.with_delay()
            if is_to_update:
                product_channel.update_from_master_data(exported_fields)
            else:
                product_channel.create_from_master_data(exported_fields)

    def update_from_master_data(self, exported_fields):
        if self.check_sku_require_for_export():
            datas = self.with_context(export_from_master=True)._put_to_channel(exported_fields)
        else:
            datas = self.get_default_data_for_log()
        if 'job_uuid' in self.env.context:
            vals = {'datas': datas,
                    'channel_id': self.channel_id.id,
                    'operation_type': 'export_master',
                    'res_model': 'product.template',
                    'res_id': self.product_tmpl_id.id,
                    'entity_name': self.display_name,
                    'job_uuid': self.env.context['job_uuid'],
                    }
            log = self.env['omni.log'].create(vals)
            status = 'done'
            message = None
            if self.state == 'error':
                status = 'failed'
                message = ','.join(self.mapped('error_message'))
            log.update_status(status, message)

    def create_from_master_data(self, exported_fields):
        if self.check_sku_require_for_export():
            datas = self._push_to_channel(exported_fields)
        else:
            datas = self.get_default_data_for_log()
        if 'job_uuid' in self.env.context:
            vals = {'datas': datas,
                    'channel_id': self.channel_id.id,
                    'operation_type': 'export_master',
                    'res_model': 'product.template',
                    'res_id': self.product_tmpl_id.id,
                    'entity_name': self.display_name,
                    'job_uuid': self.env.context['job_uuid'],
                    }
            log = self.env['omni.log'].create(vals)
            status = 'done'
            message = None
            if self.state == 'error':
                status = 'failed'
                message = ','.join(self.mapped('error_message'))
            log.update_status(status, message)
        if self.state == 'error' and 'job_uuid' in self.env.context:
            # Just for creating in queue job
            self.unlink()
        return self

    def generate_new_slug(self):
        self.ensure_one()
        to_slugify = self.name or ''
        self.slug = f'/{slugify(to_slugify)}'

    def unlink_if_no_variants(self):
        not_existed_variants = self.filtered(lambda r: not r.product_variant_ids)
        not_existed_variants.with_context(for_synching=True).unlink()
