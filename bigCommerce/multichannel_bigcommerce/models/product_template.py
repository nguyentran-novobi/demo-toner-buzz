# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models

from ..utils.bigcommerce_product_helper import ProductImporter, ProductImportBuilder, BIGCOMMERCE_REQUEST_SPECIAL_FIELDS

_logger = logging.getLogger(__name__)

# For List to Channel
BIGCOMMERCE_TEMPLATE_FIELDS_LISTED = [
    'name', 'sku', 'weight_in_oz', 'depth', 'height', 'width', 'mpn', 'lst_price',
    'upc', 'gtin', 'retail_price', 'type', 'description', 'description_sale', 'image_1920',
    'brand_id', 'product_variant_ids', 'product_channel_image_ids'
]

BIGCOMMERCE_VARIANT_FIELDS_LISTED = [
    'default_code', 'lst_price', 'weight_in_oz', 'depth', 'height', 'width', 'mpn',
    'upc', 'retail_price', 'image_variant_1920'
]

BIGCOMMERCE_UPDATED_TEMPLATE_FIELDS = BIGCOMMERCE_TEMPLATE_FIELDS_LISTED

BIGCOMMERCE_UPDATED_VARIANT_FIELDS = BIGCOMMERCE_VARIANT_FIELDS_LISTED


# This is the list of fields will be ignored if having variants
BIGCOMMERCE_IGNORED_FIELDS = [
    'weight_in_oz', 'depth', 'height', 'width', 'mpn', 'upc', 'gtin', 'bin_picking_number',
    'lst_price', 'retail_price'
]


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def bigcommerce_get_data(self, channel_id, sync_inventory=False, **options):
        """
        Get products from BigCommerce
        *****Note: Synching will be run in Queue Job. Therefore, we need to concern about "concurrence update" issues
        :return:
        1. Data products
        2. UUIDs of jobs for synching
        """

        # Get brand
        self.env['brand.channel'].with_context(for_synching=True).bigcommerce_get_data(channel_id)

        # Get Tax
        self.env['tax.class'].with_context(for_synching=True).bigcommerce_get_data(channel_id)

        # Get categories on BigCommerce
        self.env['product.channel.category'].with_context(for_synching=True).bigcommerce_get_data(channel_id)

        return self.bigcommerce_import_products(channel_id, sync_inventory=sync_inventory, **options)

    @api.model
    def bigcommerce_import_products(self, channel_id, sync_inventory=False, auto_create_master=True, **options):
        """
        Default values for options:
        id_on_channel=None,
        ids_csv=None,
        limit=250,
        date_modified=None,
        to_date=None,
        is_visible=None,
        all_records=False,
        """

        def prepare_importer(chn):
            res = ProductImporter()
            res.channel = chn
            res.set_options(**options)
            return res

        def prepare_builder(products):
            res = ProductImportBuilder()
            res.products = products
            return res

        def fetch_product(cor):
            try:
                while True:
                    attributes = cor.send(None)
                    attribute_line_values = _create_attribute_lines(attributes)
                    yield cor.send(attribute_line_values)
            except StopIteration:
                pass

        def _create_attribute_lines(attributes):
            attribute_line_values = [
                self.env['product.attribute'].sudo().create_attribute_line(key, attributes[key])
                for key in attributes
            ]
            return attribute_line_values

        number_of_products, uuids = 0, []
        channel = self.env['ecommerce.channel'].browse(channel_id)
        importer = prepare_importer(channel)
        for pulled in importer.do_import():
            if pulled:
                number_of_products += len(pulled)
                builder = prepare_builder(pulled.data)
                vals_list = list(fetch_product(builder.prepare()))
                uuids.extend(self.create_jobs_for_synching(
                    vals_list,
                    channel_id,
                    sync_inventory=sync_inventory,
                    auto_create_master=auto_create_master,
                ))
        return number_of_products, uuids

    @api.model
    def get_fields_to_list(self, platform, update):
        res = super(ProductTemplate, self).get_fields_to_list(platform, update)
        if platform == 'bigcommerce':
            if not update:
                res = [BIGCOMMERCE_TEMPLATE_FIELDS_LISTED, BIGCOMMERCE_VARIANT_FIELDS_LISTED, BIGCOMMERCE_IGNORED_FIELDS]
            else:
                res = [BIGCOMMERCE_UPDATED_TEMPLATE_FIELDS, BIGCOMMERCE_UPDATED_VARIANT_FIELDS, BIGCOMMERCE_IGNORED_FIELDS]
        return res
