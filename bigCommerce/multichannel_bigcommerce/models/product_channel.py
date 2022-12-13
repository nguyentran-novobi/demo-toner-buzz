# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import operator
import logging
import dateutil.parser

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.addons.omni_manage_channel.utils.common import ImageUtils
from odoo.addons.multichannel_product.models.product_channel import after_commit, validate_exported_fields

from ..utils.bigcommerce_product_helper import BIGCOMMERCE_REQUEST_SPECIAL_FIELDS,\
    ProductMapping2ChannelMapper, ProductMapping2ChannelExporter, ProductExportError
from ..utils.bigcommerce_api_helper import BigCommerceHelper
from .product_template import BIGCOMMERCE_IGNORED_FIELDS, \
    BIGCOMMERCE_UPDATED_VARIANT_FIELDS, BIGCOMMERCE_UPDATED_TEMPLATE_FIELDS, BIGCOMMERCE_VARIANT_FIELDS_LISTED

_logger = logging.getLogger(__name__)

BULK_PRICING_DISCOUNT_TYPES = [
    ('percent', '% Discount'),
    ('fixed', 'Fixed Amount'),
    ('price', 'Off/Unit'),
]


class ProductChannel(models.Model):
    _inherit = "product.channel"

    # Advanced Pricing & Tax
    tax_class_id = fields.Many2one('tax.class', string='Tax Class')
    tax_code = fields.Char('Product Tax Code')

    # Bulk Pricing
    bulk_pricing_discount_type = fields.Selection(
        selection=BULK_PRICING_DISCOUNT_TYPES,
        string='Bulk Pricing Discount Type',
        default='percent',
    )
    bulk_pricing_rule_ids = fields.One2many('product.bulk.pricing.rule', 'product_channel_id')

    # Storefront
    bigcommerce_product_condition = fields.Selection(selection=[
        ('New', 'New'),
        ('Used', 'Used'),
        ('Refurbished', 'Refurbished'),
    ], string='BigCommerce Product Condition', default='New')
    bigcommerce_is_product_condition_shown = fields.Boolean('BigCommerce Product Condition Shown?', default=False)
    custom_field_ids = fields.One2many('product.channel.custom.field.line', 'product_channel_id')
    is_related_product_auto = fields.Boolean('Auto Related Products?', default=False)
    related_product_list = fields.Char('List of IDs of Related Products')
    related_product_ids = fields.Many2many(
        comodel_name='product.channel',
        relation='product_channel_related_product_rel',
        column1='product_channel_id',
        column2='related_id',
        string='Related Products',
        compute='_compute_related_product_ids',
        inverse='_inverse_related_product_ids',
        search='_search_related_product_ids',
        domain="[('channel_id', '=', channel_id), ('id_on_channel', 'not in', [False, '', id_on_channel])]",
    )

    # Fulfillment
    preorder_release_date = fields.Date('Preorder Release Date')
    preorder_message = fields.Char('Preorder Message')
    preorder_auto_disable = fields.Boolean('Preorder Auto Disable', help='Remove pre-order status on release date')

    # SEO
    page_title = fields.Char(
        'Page Title',
        help="Specify a page title, or leave blank to use the product's name as page title",
    )
    open_graph_type = fields.Selection(selection=[
        ('product', 'Product'),
        ('album', 'Album'),
        ('book', 'Book'),
        ('drink', 'Drink'),
        ('food', 'Food'),
        ('game', 'Game'),
        ('movie', 'Movie'),
        ('song', 'Song'),
        ('tv_show', 'TV Show'),
    ], default='product')
    open_graph_title = fields.Char()
    open_graph_description = fields.Text()
    open_graph_use_meta_description = fields.Boolean()
    open_graph_use_product_name = fields.Boolean()
    open_graph_use_image_option = fields.Selection([
        ('yes', "Use thumbnail image"),
        ('no', "Don't use an image"),
    ], default='yes')

    @api.depends('related_product_list')
    def _compute_related_product_ids(self):
        for record in self:
            related_product_ids = (record.related_product_list or '').split(',')
            related_products = self.search([('id_on_channel', 'in', related_product_ids)])
            record.update({
                'related_product_ids': [(6, 0, related_products.ids)]
            })

    def _inverse_related_product_ids(self):
        for record in self:
            ids_on_channel = record.related_product_ids.mapped('id_on_channel')
            list_ids = ','.join(filter(bool, ids_on_channel))
            record.update({
                'related_product_list': list_ids
            })

    def _search_related_product_ids(self):
        """Not allow to search"""

    @api.model
    def prepare_product_channel(self, product_data, channel_id):
        channel = self.env['ecommerce.channel'].browse(channel_id)

        #
        # Some values on variants will be set default by template
        #

        if channel.platform == 'bigcommerce':
            if 'description' in product_data:
                product_data['description_sale'] = product_data['description']
                product_data['description'] = ''
            if product_data.get('url'):
                product_data['slug'] = product_data.get('url')
            for v in product_data.get('variants', []):
                original_price = v['price']
                for key in ['cost_price', 'price', 'sale_price', 'retail_price',
                            'weight', 'width', 'height', 'depth']:
                    if original_price is None and (v.get(key, None) is None or v.get(key, -1) == 0):
                        v[key] = product_data[key]
                    else:
                        v[key] = v.get(key, 0)

            if 'inventory_tracking' in product_data:
                product_data['inventory_tracking'] = False if product_data['inventory_tracking'] == 'none' else True
        product_channel_vals = super(ProductChannel, self).prepare_product_channel(product_data, channel_id)

        def _get_meta_keywords():
            meta_keywords = [{'name': e} for e in product_data.get('meta_keywords', [])]
            meta_keyword_ids = self.env['product.channel.keyword'].with_context(check_duplicated=True).create(
                meta_keywords).mapped('id')

            return meta_keyword_ids

        def _get_categories(product_category_ids, channel_id):
            if not product_category_ids:
                return []

            ProductChannelCategory = self.env['product.channel.category'].sudo()
            product_category_ids = [str(x) for x in product_category_ids]
            categories = ProductChannelCategory.search([('channel_id.id', '=', channel_id),
                                                        ('id_on_channel', 'in', product_category_ids)])
            if len(categories) != len(product_category_ids):
                ProductChannelCategory.bigcommerce_get_data(channel_id)
                categories = ProductChannelCategory.search([('channel_id.id', '=', channel_id),
                                                            ('id_on_channel', 'in', product_category_ids)])

            ids = categories.mapped('id')
            return ids

        def _get_brand(brand_id, channel_id):
            if not brand_id:
                return False
            BrandChannel = self.env['brand.channel'].sudo()
            record = BrandChannel.search([
                ('channel_id.id', '=', channel_id),
                ('id_on_channel', '=', str(brand_id)),
            ], limit=1)

            if not record:
                record = BrandChannel.bigcommerce_get_data(channel_id, brand_id)

            id = record.brand_id.id
            return id

        def _get_tax_class(tax_class_id, channel_id):
            if tax_class_id is None or tax_class_id is False or tax_class_id == '':
                return False

            TaxClass = self.env['tax.class'].sudo()
            tax_class = TaxClass.search([
                ('channel_id', '=', channel_id),
                ('id_on_channel', '=', str(tax_class_id))
            ], limit=1)

            if not tax_class:
                tax_class = TaxClass.bigcommerce_get_data(channel_id, tax_class_id)

            return tax_class.id

        if channel.platform == 'bigcommerce':
            product_channel_category_ids = _get_categories(product_data.get('categories'), channel_id)
            if product_data.get('preorder_release_date'):
                preorder_release_date = dateutil.parser.parse(product_data['preorder_release_date']).date()
            else:
                preorder_release_date = False
            related_products = product_data.get('related_products', [])
            is_related_product_auto = related_products == [-1]
            related_product_list = ','.join(map(str, related_products)) if not is_related_product_auto else ''
            custom_field_vals = [(5, 0, dict())] + [
                (0, 0, {
                    'id_on_channel': cf['id'],
                    'key': cf['name'],
                    'value': cf['value'],
                })
                for cf in product_data.get('custom_fields', [])
            ]
            bulk_pricing_rules = product_data.get('bulk_pricing_rules', [])
            bulk_pricing_discount_type = next(iter(bulk_pricing_rules), {}).get('type', 'percent')
            bulk_pricing_rule_vals = [(5, 0, dict())] + [
                (0, 0, {
                    'id_on_channel': pr['id'],
                    'quantity_min': pr['quantity_min'],
                    'quantity_max': pr['quantity_max'],
                    'discount_amount': pr['amount'],
                })
                for pr in bulk_pricing_rules
            ]
            product_channel_vals.update({
                'categ_ids': [(6, 0, product_channel_category_ids)],
                'brand_id': _get_brand(product_data.get('brand_id'), channel_id),
                'tax_class_id': _get_tax_class(product_data.get('tax_class_id'), channel_id),
                'keyword_ids': [(6, 0, _get_meta_keywords())],
                'tax_code': product_data.get('product_tax_code', False),
                'is_featured': bool(product_data.get('is_featured', False)),
                'warning_quantity': product_data.get('inventory_warning_level'),
                'is_related_product_auto': is_related_product_auto,
                'related_product_list': related_product_list,
                'warranty': product_data.get('warranty'),
                'search_keywords': product_data.get('search_keywords'),
                'availability_description': product_data.get('availability_description'),
                'bigcommerce_product_condition': product_data.get('condition'),
                'bigcommerce_is_product_condition_shown': product_data.get('is_condition_shown'),
                'page_title': product_data.get('page_title'),
                'preorder_release_date': preorder_release_date,
                'preorder_message': product_data.get('preorder_message'),
                'preorder_auto_disable': product_data.get('is_preorder_only'),
                'open_graph_type': product_data.get('open_graph_type'),
                'open_graph_title': product_data.get('open_graph_title'),
                'open_graph_description': product_data.get('open_graph_description'),
                'open_graph_use_meta_description': product_data.get('open_graph_use_meta_description'),
                'open_graph_use_product_name': product_data.get('open_graph_use_product_name'),
                'open_graph_use_image_option': 'yes' if product_data.get('open_graph_use_image') else 'no',
                'custom_field_ids': custom_field_vals,
                'bulk_pricing_discount_type': bulk_pricing_discount_type,
                'bulk_pricing_rule_ids': bulk_pricing_rule_vals,
            })

            if product_data.get('attribute_line_ids', False):
                for field in BIGCOMMERCE_IGNORED_FIELDS:
                    product_channel_vals[field] = self[field]

        return product_channel_vals

    @api.model
    def _bigcommerce_get_variants_and_attributes(self, product_data, check=False):
        """
        Get variants, and attributes of product
        :param product_id:
        :return:
        """
        try:
            variants = product_data.get('variants')
            attributes = {}
            valid_variants = []
            invalid_variants = []
            for v in variants:
                v['inventory_quantity'] = float(v.get('inventory_level', 0.0)) if v.get('inventory_level') else 0
                for option_value in v['option_values']:
                    values = attributes.get(option_value['option_display_name'], [])
                    values.append(option_value['label'])
                    attributes[option_value['option_display_name']] = list(set(values))
                if self and check:
                    if len(self.attribute_line_ids) == len(v['option_values']):
                        valid_variants.append(v)
                    else:
                        invalid_variants.append(v)
                else:
                    valid_variants.append(v)
            return valid_variants, invalid_variants, attributes
        except Exception as e:
            _logger.exception(str(e))
        return [], {}

    @api.model
    def _bigcommerce_create_attribute_lines(self, attributes):
        attribute_line_ids = []
        for key in attributes:
            attribute_line_ids.append(
                self.env['product.attribute'].sudo().create_attribute_line(key, attributes[key]))
        return attribute_line_ids

    def bigcommerce_get_data(self):
        """
        Get data of product on channel
        :return: a dict was standardized by prepare_product_channel function
        """
        self.ensure_one()
        api = BigCommerceHelper.connect_with_channel(channel=self.channel_id)
        product = api.products.acknowledge(self.id_on_channel)
        res = product.get_by_id(include=BIGCOMMERCE_REQUEST_SPECIAL_FIELDS)
        if res.ok():
            product_data = res.data
            variants, invalid_variants, attributes = self._bigcommerce_get_variants_and_attributes(product_data)
            if invalid_variants:
                for invalid_variant in invalid_variants:
                    variant = api.product_variants.acknowledge(invalid_variant['id'], self.id_on_channel)
                    variant.delete_one()
            product_data['variants'] = variants
            product_data['attribute_line_ids'] = self._bigcommerce_create_attribute_lines(attributes)
            product_data['inventory_quantity'] = product_data['inventory_level']
            product_data['url'] = product_data['custom_url']['url']
            vals = self.prepare_product_channel(product_data, self.channel_id.id)
            vals['variants'] = variants
            return vals
        else:
            self._bigcommerce_write_errors(res.last_response)
        return {}

    def _bigcommerce_prepare_data(self, update=False, exported_fields=None):
        self.ensure_one()
        exported_fields = exported_fields or {}
        data = ProductMapping2ChannelMapper.map(self, update)
        exported_template_fields = exported_fields.get('template', [])
        data = validate_exported_fields(data, exported_template_fields)

        # Only for creating
        if not update:
            if 'categories' not in data:
                if not self.categ_ids and not self.channel_id.default_categ_id:
                    raise ValidationError(_('Please set default category in Store Settings!'))
                elif self.categ_ids:
                    data['categories'] = [int(c.id_on_channel) for c in self.categ_ids]
                else:
                    data['categories'] = [int(self.channel_id.default_categ_id.id_on_channel)]
                    self.update({'categ_ids': [(4, self.channel_id.default_categ_id.id)]})
            if 'price' not in data:
                data['price'] = 0.0
            if 'weight' not in data:
                data['weight'] = 0.0
            # No visible on storefront when creating from Odoo
            data['is_visible'] = False

            exported_variant_fields = exported_fields.get('variant', [])
            variants = []
            for variant in self.product_variant_ids:
                if variant.attribute_value_ids:
                    variant_data = variant._bigcommerce_prepare_data(update=update,
                                                                     exported_fields=exported_variant_fields)
                    variants.append(variant_data)
            data['variants'] = variants
        return data

    def bigcommerce_get_variant(self, id_on_channel=None):
        self.ensure_one()
        id_on_channel = id_on_channel or self.id_on_channel
        api = BigCommerceHelper.connect_with_channel(channel=self.channel_id)
        variants = api.product_variants.acknowledge(None, product_id=id_on_channel)
        res = variants.all()
        if res.ok():
            return res.data['data']
        return []

    def bigcommerce_delete_record(self, id_on_channel=None):
        self.ensure_one()
        api = BigCommerceHelper.connect_with_channel(channel=self.channel_id)
        product = api.products.acknowledge(id_on_channel or self.id_on_channel)
        res = product.delete_one()
        if not res.ok():
            self._bigcommerce_write_errors(res.last_response)
            return False
        return True

    def _bigcommerce_write_errors(self, response):
        self.ensure_one()
        try:
            if response.status_code == 404:
                message = 'This product is no longer available on online store.'
                self.with_context(update_status=True).sudo().write({
                    'state': 'error',
                    'error_message': message,
                })
            elif response.status_code in [400, 401, 403, 405, 406, 413, 415, 429]:

                message = "HTTP %s: %s. " \
                          "You can reach out to our support team " \
                          "by email at support@novobi.com." % (response.status_code, response.reason)

                self.with_context(update_status=True).sudo().write({'state': 'error',
                                                                    'error_message': message})

                if response.status_code == 401 and self.channel_id:
                    self.channel_id.sudo().disconnect()
            else:
                _logger.error("Can't update products on BigCommerce")
                _logger.error("Code %s: %s" % (response.status_code, response.content))
                content = response.json()
                errors = list(content.get('errors', {}).values())
                if 'errors' not in content:
                    self.with_context(update_status=True).sudo().write({
                        'state': 'error',
                        'error_message': content['title'],
                    })
                elif len(errors) == 1:
                    if content['title'] == errors[0]:
                        message = content['title']
                    else:
                        message = '%s - %s' % (content['title'], errors[0])
                    self.with_context(update_status=True).sudo().write({
                        'state': 'error',
                        'error_message': message,
                    })
                else:
                    error_message = '\n- '.join(errors)
                    self.with_context(update_status=True).sudo().write({
                        'state': 'error',
                        'error_message': '%s\n- %s' % (content['title'], error_message)
                    })
        except Exception as e:
            _logger.exception(str(e))
            self.with_context(update_status=True).sudo().write({
                'state': 'error',
                'error_message': "HTTP %s: %s" % (response.status_code, response.reason)
            })

    def _bigcommerce_export_other_data(self):
        for category in self.categ_ids:
            category.bigcommerce_export_category()

    def bigcommerce_post_record(self, exported_fields=None):
        """
        Create product on BigCommerce when it created from Odoo
        exported_fields is a dict containing template and variant fields should be pushed to channel
        For example:
        {
            'template':['name', 'sku'],
            'variant':['name', 'sku']
        }
        :return:
        """
        self.ensure_one()
        self._bigcommerce_export_other_data()

        exported_fields = exported_fields or {}
        data = self._bigcommerce_prepare_data(exported_fields=exported_fields)
        api = BigCommerceHelper.connect_with_channel(channel=self.channel_id)
        product = api.products.create_new_with(data)
        res = product.publish()

        # Prepare data in record
        if res.ok():
            product_data = res.data
            variants, invalid_variants, attributes = self._bigcommerce_get_variants_and_attributes(product_data, True)
            url = product_data.get('custom_url', {}).get('url') or ''
            vals = {
                'id_on_channel': str(product_data['id']),
                'variants': variants,
                'url': url,
                'slug': url,
            }
            try:
                self.with_context(request_from_app=True)._update_data(vals)
            except Exception as e:
                _logger.exception(str(e))
                self.bigcommerce_delete_record(product_data['id'])
                self.with_context(update_status=True).sudo().write({
                    'state': 'error',
                    'id_on_channel': False,
                    'error_message': '%s' % e
                })
        else:
            self._bigcommerce_write_errors(res.last_response)
        return res.last_response.request.json

    def bigcommerce_put_record(self, exported_fields=None):
        """
        Update product on BigCommerce
        :return:
        """
        res = ProductMapping2ChannelExporter.export(self, exported_fields, update=True)
        return res.log_data

    @after_commit
    def bigcommerce_update_images(self, update=False):
        self.ensure_one()
        result = []
        ids = []
        api = BigCommerceHelper.connect_with_channel(channel=self.channel_id)
        product_images = api.product_images.acknowledge(None, product_id=self.id_on_channel)
        if update:
            # Check current images on store
            res = product_images.all()
            if res.ok():
                images = res.data['data']
                ids = [str(i['id']) for i in images]

        for index, image in enumerate(self.product_channel_image_ids.sorted(lambda i: i.sequence)):
            data = {
                'is_thumbnail': image.is_thumbnail,
                'description': image.image_description if image.image_description else '',
                'image_url': image.image_url,
                'sort_order': index + 1
            }
            result.append(data)
            if image.id_on_channel and image.id_on_channel in ids:
                product_image = api.product_images.acknowledge(image.id_on_channel, product_id=self.id_on_channel)
                product_image.data = data
                product_image.put_one()
            else:
                product_image = api.product_images.acknowledge(None, product_id=self.id_on_channel)
                product_image.data = data
                res = product_image.publish()
                if res.ok():
                    json_response = res.data['data']
                    image.sudo().with_context(for_synching=True).write({'id_on_channel': str(json_response['id']),
                                                                        'sequence': int(json_response['sort_order'])})

        if ids:
            current_ids = self.product_channel_image_ids.mapped('id_on_channel')
            deleted_ids = list(filter(lambda i: i not in current_ids, ids))
            for deleted_id in deleted_ids:
                product_image = api.product_images.acknowledge(deleted_id, product_id=self.id_on_channel)
                product_image.delete_one()
        return result

    @api.model
    def bigcommerce_prepare_image_data(self, image_data, channel):
        thumbnail = list(filter(lambda i: i['is_thumbnail'], image_data))
        if thumbnail:
            thumbnail = thumbnail[0]
        elif image_data:
            thumbnail = image_data[0]
        else:
            thumbnail = {}

        thumbnail_decode = ImageUtils.get_safe_image_b64(thumbnail['url_standard']) if thumbnail else False

        product_channel_image_ids = []
        for image in image_data:
            image_name = image.get('image_file')
            try:
                img_base64 = ImageUtils.get_safe_image_b64(image.get('url_standard'))
                product_channel_image_ids.append((0, 0, {
                    'name': image_name,
                    'is_thumbnail': image.get('is_thumbnail'),
                    'id_on_channel': str(image.get('id')),
                    'image': img_base64,
                    'image_description': image.get('description', ''),
                    'channel_id': channel.id,
                    'product_tmpl_id': False,
                    'sequence': int(image.get('sort_order', 0))
                }))
            except Exception as e:
                _logger.exception("Error when getting product Images: %s", str(e))

        return thumbnail_decode, product_channel_image_ids

    def get_updated_fields(self):
        res = super(ProductChannel, self).get_updated_fields()
        if self.platform == 'bigcommerce':
            res = [BIGCOMMERCE_UPDATED_TEMPLATE_FIELDS, BIGCOMMERCE_UPDATED_VARIANT_FIELDS, BIGCOMMERCE_IGNORED_FIELDS]
        return res

    def get_merged_template_fields(self):
        # Depend on channel we will have merged fields are different
        fields = super(ProductChannel, self).get_merged_template_fields()
        if self.platform == 'bigcommerce':
            fields = BIGCOMMERCE_UPDATED_TEMPLATE_FIELDS.copy()
            if self.attribute_line_ids:
                for key in BIGCOMMERCE_IGNORED_FIELDS:
                    if key in fields:
                        fields.remove(key)
        return fields

    def get_merged_variant_fields(self):
        # Depend on channel we will have merged fields are different
        created_fields, updated_fields = super(ProductChannel, self).get_merged_variant_fields()
        if self.platform == 'bigcommerce':
            created_fields, updated_fields = BIGCOMMERCE_VARIANT_FIELDS_LISTED, BIGCOMMERCE_UPDATED_VARIANT_FIELDS
        return created_fields, updated_fields

    def get_formview_id(self, access_uid=None):
        res = super().get_formview_id(access_uid)
        if self.channel_id.platform == 'bigcommerce' and not res:
            res = self.env.ref('multichannel_bigcommerce.view_bigcommerce_product_channel_form').id
        return res
