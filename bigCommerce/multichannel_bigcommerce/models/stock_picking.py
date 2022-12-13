# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
import pytz
import requests
import dateutil.parser

from odoo import models, api

from odoo.addons.omni_manage_channel.models.customer_channel import compare_address

from ..utils.bigcommerce_shipment_helper import BigCommerceShipmentHelper

_logger = logging.getLogger(__name__)

SHIPPING_PROVIDERS = ['auspost', 'canadapost', 'endicia', 'usps', 'fedex', 'royalmail', 'ups', 'upsready', 'upsonline', 'shipperhq']


class Picking(models.Model):
    _inherit = 'stock.picking'

    def _bigcommerce_get_shipping_address(self):
        self.ensure_one()
        bc_store_hash, headers = self.sale_id.channel_id.bigcommerce_generate_url_header()
        end_point = 'https://api.bigcommerce.com/stores/%s/v2/orders/%s/shipping_addresses' % (bc_store_hash,
                                                                                      self.sale_id.id_on_channel)

        response = requests.get(url=end_point, headers=headers)
        if response.status_code == 200:
            shipping_addresses = response.json()

            for shipping_address in shipping_addresses:
                name = '%s %s' % (shipping_address['first_name'], shipping_address['last_name'])
                country = self.env['res.country'].sudo().search(
                    [('code', '=ilike', shipping_address['country_iso2'])],
                    limit=1)
                country_id = country.id
                state_id = self.env['res.country.state'].sudo().search(
                    [('country_id.code', '=ilike', shipping_address['country_iso2']),
                     ('name', '=', shipping_address['state'])], limit=1).id

                shipping_address = {k: v if v else False for k, v in shipping_address.items()}

                if compare_address(self.partner_id, {**shipping_address, **dict(name=name,
                                                                                country_id=country_id,
                                                                                state_id=state_id)}, country.code):
                    return shipping_address
        return {}

    @api.model
    def _bigcommerce_prepare_shipment_lines(self, shipment_items):
        res = []
        for shipment_item in shipment_items:
            res.append({
                'order_product_id': shipment_item['order_item_id'],
                'quantity': shipment_item['quantity']
            })
        return res
    
    def _bigcommerce_prepare_data(self, shipment_items):
        self.ensure_one()
        shipping_address = self._bigcommerce_get_shipping_address()
        title = 'Cannot create/update shipment on BigCommerce'
        if not shipping_address:
            exceptions = [{'title': 'Shipping Address is invalid',
                           'reason': 'The address specified does not belong to the order.'}]
            self._log_exceptions_on_picking(title, exceptions)
            return {}

        data_lines = self._bigcommerce_prepare_shipment_lines(shipment_items)

        shipping_provider = self.carrier_name or self.get_shipping_provider()
        shipping_provider = shipping_provider if shipping_provider in SHIPPING_PROVIDERS else ''

        data = {
            "order_address_id": shipping_address['id'],
            "items": data_lines,
            "tracking_number": self.carrier_tracking_ref or '',
            "shipping_provider": shipping_provider,
            "tracking_carrier": shipping_provider,
        }

        return data

    def bigcommerce_post_record(self, shipment_items):
        """
        Create shipment on BigCommerce when it created from Odoo
        :return:
        """
        data = self._bigcommerce_prepare_data(shipment_items)

        helper = BigCommerceShipmentHelper(self.sale_id.channel_id)
        res = helper.create(self.sale_id.id_on_channel, data)
        if res.ok():
            json_data = res.data
            id_on_channel = str(json_data['id'])
            shipping_date = dateutil.parser.parse(json_data['date_created'])
            self.sudo().write({
                'id_on_channel': id_on_channel,
                'shipping_date': shipping_date.astimezone(pytz.utc).replace(tzinfo=None)
            })
            self.mark_synced_with_channel()
        else:
            title = 'Cannot create/update shipment on BigCommerce'
            exceptions = self._bigcommerce_parse_error_messages(res.last_response.json())
            self._log_exceptions_on_picking(title, exceptions)

    def _bigcommerce_parse_error_messages(self, errors):
        self.ensure_one()
        exceptions = []
        for error in errors:
            if 'quantity' in error['message']:
                if 'details' in error:
                    order_line_id = str(error['details']['order_product_id'])
                    available_quantity = error['details'].get('available_quantity', 0)
                    order_line = self.sale_id.order_line
                    order_line = order_line.filtered(lambda ln: ln.id_on_channel == order_line_id)
                    product_name = order_line.product_id.name
                    reason = f'The quantity specified for {product_name} is greater than' \
                             f' the quantity of the product that is available {available_quantity} to ship.'
                else:
                    reason = f"The quantity specified is invalid and cannot be processed. {error['message']}"
                exceptions.append({
                    'title': 'Quantity is invalid',
                    'reason': reason
                })
            elif 'order_product_id' in error['message']:
                exceptions.append({
                    'title': 'Order Product is invalid',
                    'reason': 'The order product specified does not belong to'
                              ' the order associated with the shipment.'
                })
            elif 'order_address_id' in error['message']:
                exceptions.append({
                    'title': 'Shipping Address is invalid',
                    'reason': 'The address specified does not belong to the order.'
                })
        return exceptions

    def bigcommerce_put_record(self, shipment_items, update_items=False):
        """
        Update the shipment on BigCommerce when it is updated in Odoo
        When need to update items, have to delete shipment and replace by a new one
        :return:
        """
        helper = BigCommerceShipmentHelper(self.sale_id.channel_id)
        if update_items:
            helper.cancel(self.id_on_channel, self.sale_id.id_on_channel)
            self.bigcommerce_post_record()
        else:
            data = self._bigcommerce_prepare_data(shipment_items)

            if 'items' in data:
                data.pop('items')

            res = helper.update(self.id_on_channel, self.sale_id.id_on_channel, data)
            if not res.ok():
                title = 'Cannot update shipment on BigCommerce'
                self._log_exceptions_on_picking(title, [{
                    'title': 'Something went wrong',
                    'reason': error['message']
                } for error in res.last_response.json()])
            else:
                self.mark_synced_with_channel()
