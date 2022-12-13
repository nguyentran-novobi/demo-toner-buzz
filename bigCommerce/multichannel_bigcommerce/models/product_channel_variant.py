# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, _

from odoo.addons.multichannel_product.models.product_channel import validate_exported_fields

from ..utils.bigcommerce_api_helper import BigCommerceHelper

_logger = logging.getLogger(__name__)


class ProductChannelVariant(models.Model):
    _inherit = "product.channel.variant"

    def bigcommerce_update_quantity(self, quantity):
        for record in self:
            product_id = record.product_channel_tmpl_id.id_on_channel
            api = BigCommerceHelper.connect_with_channel(channel=record.channel_id)
            variant = api.product_variants.acknowledge(record.id_on_channel, product_id=product_id)
            variant.data = {'inventory_level': quantity}
            variant.put_one()

    def _bigcommerce_prepare_data(self, update=False, attributes={}, exported_fields=[]):
        self.ensure_one()
        vals = {
            'price': self.lst_price if self.lst_price else 0.0,
            'sale_price': self.sale_price if self.sale_price else 0.0,
            'retail_price': self.retail_price if self.retail_price else 0.0,
            'weight': self.weight_in_oz if self.weight_in_oz else 0.0,
            'width': self.width if self.width else 0.0,
            'height': self.height if self.height else 0.0,
            'depth': self.depth if self.depth else 0.0,
            'is_free_shipping': bool(self.is_free_shipping),
            'fixed_cost_shipping_price': self.fixed_cost_shipping_price,
            'purchasing_disabled': bool(self.purchasing_disabled),
            'upc': self.upc if self.upc else '',
            'bin_picking_number': self.bin_picking_number if self.bin_picking_number else '',
            'sku': self.default_code if self.default_code else '',
            'mpn': self.mpn if self.mpn else '',
            'option_values': [{
                'option_display_name': o.attribute_id.name,
                'label': o.name
            } for o in self.attribute_value_ids],
            'inventory_warning_level': int(self.warning_quantity),
        }

        if not vals['sku'] and not update:
            del vals['sku']
        if self.image_variant_1920 and self.has_change_image_variant:
            vals['image_url'] = self.image_variant_url
        if update and self.id_on_channel:
            vals['id'] = int(self.id_on_channel)
        if update and self.product_channel_tmpl_id.id_on_channel:
            vals['product_id'] = int(self.product_channel_tmpl_id.id_on_channel)
        if attributes:
            option_values = []
            for o in self.attribute_value_ids:
                option_values.append({
                    'option_id': attributes[o.attribute_id.name]['id'],
                    'id': attributes[o.attribute_id.name][o.name]
                })
            vals['option_values'] = option_values
            
        # Remove keys not in exported fields
        vals = validate_exported_fields(vals, exported_fields)
        
        return vals

    def bigcommerce_post_record(self, attributes, product_id=None, exported_fields=[]):
        self.ensure_one()
        product_id = product_id or self.product_channel_tmpl_id.id_on_channel
        data = self._bigcommerce_prepare_data(attributes=attributes, exported_fields=exported_fields)
        api = BigCommerceHelper.connect_with_channel(channel=self.channel_id)
        variant = api.product_variants.acknowledge(None, product_id=product_id)
        variant.data = data
        res = variant.publish()
        if res.ok():
            data = res.data['data']
            self.sudo().write({'id_on_channel': str(data['id'])})
        return res.last_response

    def bigcommerce_put_record(self, attributes={}, exported_fields=[]):
        self.ensure_one()
        product_id = self.product_channel_tmpl_id.id_on_channel
        data = self._bigcommerce_prepare_data(update=True, attributes=attributes, exported_fields=exported_fields)
        api = BigCommerceHelper.connect_with_channel(channel=self.channel_id)
        variant = api.product_variants.acknowledge(self.id_on_channel, product_id=product_id)
        variant.data = data
        res = variant.put_one()
        return res.last_response
