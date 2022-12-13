# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _
import requests
from odoo.exceptions import ValidationError
import json

_logger = logging.getLogger(__name__)

class BrandChannel(models.Model):
    _inherit = 'brand.channel'

    @api.model
    def bigcommerce_get_data(self, channel_id, id_on_channel=None):
        """
        :param vals:
        [tree-form categories from api]
        :return:
        """
        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)
        bc_store_hash, headers = channel.bigcommerce_generate_url_header()

        url = "https://api.bigcommerce.com/stores/%s/v3/catalog/brands" % bc_store_hash

        if id_on_channel:
            url += '/%s' % id_on_channel

        try:
            response = requests.get(url=url, headers=headers)
            if response.status_code == 200:
                vals = response.json()['data']
                if isinstance(vals, dict):
                    vals = [vals]

                brand_ids = [str(x['id']) for x in vals]
                synced_brands = self.sudo().search([('id_on_channel', 'in', brand_ids),
                                                      ('channel_id.id', '=', channel_id)]).mapped('id_on_channel')

                new_options = list(filter(lambda x: str(x['id']) not in synced_brands, vals))

                brand_names = [e['name'] for e in new_options]

                ProductBrand = self.env['product.brand'].sudo()
                product_brands = ProductBrand.search([('name', 'in', brand_names)])

                result = []
                for val in new_options:
                    product_brand = product_brands.filtered(lambda b: b.name == val['name'])
                    if not product_brand:
                        product_brand = ProductBrand.create({'name': val['name']})
                    result.append({
                        'id_on_channel': str(val['id']),
                        'brand_id': product_brand.id,
                        'channel_id': channel_id
                    })
                self.env.cr.commit()
                records = self.with_context(for_synching=True).sudo().create(result)
                self.env.cr.commit()
                return records
        except Exception as e:
            _logger.exception('Error in syncing BigCommerce brand: %s', str(e))
            return self

    def bigcommerce_post_record(self):
        """
        Create brand on BigCommerce
        :return:
        """
        for record in self:
            bc_store_hash, headers = record.channel_id.bigcommerce_generate_url_header()
            end_point = 'https://api.bigcommerce.com/stores/%s/v3/catalog/brands' % bc_store_hash
            data = {
                'name': record.name
            }
            response = requests.post(url=end_point, headers=headers, data=json.dumps(data))
            if response.status_code == 200:
                id_on_channel = str(response.json()['data']['id'])
                record.sudo().write({'id_on_channel': str(id_on_channel)})
            else:
                _logger.error("Can't create brand on BigCommerce")
                _logger.error(response.status_code)
                raise ValidationError(_("Can't create brand on BigCommerce: %s" % json.dumps(response.json())))

    def bigcommerce_put_record(self):
        """
        Update brand on BigCommerce
        :return:
        """
        for record in self:
            bc_store_hash, headers = record.channel_id.bigcommerce_generate_url_header()
            end_point = 'https://api.bigcommerce.com/stores/%s/v3/catalog/brands/%s' % (
            bc_store_hash, record.id_on_channel)
            data = {
                'name': record.name
            }
            response = requests.put(url=end_point, headers=headers, data=json.dumps(data))

    def bigcommerce_delete_record(self):
        """
        Update brand on BigCommerce
        :return:
        """
        for record in self:
            bc_store_hash, headers = record.channel_id.bigcommerce_generate_url_header()
            end_point = 'https://api.bigcommerce.com/stores/%s/v3/catalog/brands/%s' % (
                bc_store_hash, record.id_on_channel)
            requests.delete(url=end_point, headers=headers)

