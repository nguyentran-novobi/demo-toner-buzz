# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import dateutil
import pytz

from ...common.resource import delegated
from ..resource import ShipStationResourceModel
from ..registry import register_model
from ..request_builder import ShipStationPaginated
from ...common import PropagatedParam
from ...restful.request_builder import RequestBuilder
from ...restful.request_builder import RestfulGet, RestfulPost, RestfulList
from ...restful.request_builder import make_request_builder
from .. import resource_formatter as shipstation_formatter
from ...common import resource_formatter as common_formatter


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of ShipStation order from channel to app
    """

    def __call__(self, order):
        basic_data = self.process_basic_data(order)
        order_line_data = self.process_order_line_data(order)
        other_lines = self.process_other_lines(order)
        addresses = self.process_addresses(order)

        result = {
            **basic_data,
            **order_line_data,
            **addresses,
            **other_lines
        }
        return result

    @classmethod
    def process_basic_data(cls, order):
        return {
            'id': order['orderId'],
            'name': order['orderNumber'],
            'channel_order_ref': order['orderNumber'],
            'order_key': order['orderKey'],
            'channel_id': order['advancedOptions']['storeId'],
            'channel_date_created': dateutil.parser.parse(order['orderDate']),
            'status_id': order['orderStatus'],
            'payment_gateway_code': order['paymentMethod'],
            'requested_shipping_method': order['requestedShippingService'],
            'staff_notes': order['internalNotes'],
            'customer_message': order['customerNotes'],
            'source': order.get('advancedOptions', {}).get('source', ''),
            'shipstation_parent_id': int(order.get('advancedOptions', {}).get('parentId') if order.get('advancedOptions', {}).get('parentId') else 0),
            'platform': 'shipstation',
            'shipping_cost': float(order['shippingAmount']),
        }

    @classmethod
    def process_order_line_data(cls, order):
        lines = []
        for line in order['items']:
            lines.append({
                'id_on_channel': line['orderItemId'],
                'order_line_key': line['lineItemKey'],
                'name': line['name'],
                'sku': line['sku'],
                'price': float(line['unitPrice']),
                'quantity': float(line['quantity']),
                'upc': line['upc'],
                'image_url': line['imageUrl'],
                'weight': line['weight'],
                'options': line['options']
            })
        return {'lines': lines}

    @classmethod
    def process_addresses(cls, order):
        return {
            'billing_address': cls.parse_address(order['billTo']),
            'shipping_address': cls.parse_address(order['shipTo']),
        }

    @classmethod
    def parse_address(cls, address):
        return {
            'name': address['name'],
            'street': address.get('street1', ''),
            'street2': address.get('street2', ''),
            'city': address.get('city', ''),
            'state_code': address.get('state', ''),
            'state_name': '',
            'country_code': address.get('country', ''),
            'email': '',
            'phone': address.get('phone', ''),
            'zip': address.get('postalCode', ''),
            'company': address.get('company', ''),
        }

    @classmethod
    def process_other_lines(cls, order):
        tax_amount = float(order['taxAmount'])
        return {
            'taxes': [{'name': 'Tax', 'amount': tax_amount}],
        }


class DataInTrans(shipstation_formatter.DataInTrans):
    """
    Specific data transformer for ShipStation order from channel to app
    """
    transform_singular = SingularDataInTrans()
    resource_plural_name = 'orders'


class SingularDataOutTrans(common_formatter.DataTrans):
    def __call__(self, order):
        basic_data = self.process_basic_data(order)
        order_line_data = self.process_order_line_data(order)
        addresses = self.process_addresses(order)
        advance_options = self.process_advance_options(order)

        result = {
            **basic_data,
            **order_line_data,
            **addresses,
            **advance_options,
        }
        return result

    @classmethod
    def process_basic_data(cls, order):
        return {
            'orderId': order['id_on_shipstation'] if order.get('id_on_shipstation') else 0,
            'orderNumber': order['name'],
            'orderKey': order['id_on_channel'],
            'orderDate': order['date_order'],
            'orderStatus': order['order_status'],
            'customerUsername': order['customer']['name'],
            'customerEmail': order['customer']['email'],
            'customerNotes': order['customer']['notes'],
            'internalNotes': order['internal_notes'],
            'requestedShippingService': order['requested_shipping_method'],
            'taxAmount': order['tax_amount'] or 0.0,
        }

    @classmethod
    def process_order_line_data(cls, order):
        lines = []
        for line in order['items']:
            lines.append({
                'orderItemId': line['id_on_shipstation'] if line.get('id_on_shipstation') else 0,
                'lineItemKey': line['id_on_channel'],
                'name': line['product_name'],
                'sku': line['sku'],
                'weight': {
                    'value': line['weight']['value'],
                    'units': line['weight']['units'],
                },
                'unitPrice': line['unit_price'],
                'quantity': int(line['quantity']),
                'taxAmount': line['tax_amount'] or 0.0,
            })
        return {'items': lines}

    @classmethod
    def process_addresses(cls, order):
        return {
            'billTo': cls.parse_address(order['bill_to']),
            'shipTo': cls.parse_address(order['ship_to']),
        }

    @classmethod
    def parse_address(cls, address):
        return {
            'name': address['name'],
            'street1': address.get('street1', ''),
            'street2': address.get('street2', ''),
            'city': address.get('city', ''),
            'state': address.get('state_code', ''),
            'country': address.get('country_code', ''),
            'phone': address.get('phone', ''),
            'postalCode': address.get('zip', ''),
            'company': address.get('company', ''),
        }

    @classmethod
    def process_advance_options(cls, order):
        advance_options = order['advance_options']
        vals = {
            'storeId': int(advance_options['store_id']),
        }
        if 'source' in advance_options:
            vals['source'] = advance_options['source']

        return {
            'advancedOptions': vals
        }

class DataOutTrans(shipstation_formatter.DataOutTrans):
    """
    Specific data transformer for ShipStation order from app to channel
    """
    transform_singular = SingularDataOutTrans()


@register_model('orders')
class ShipStationOrderModel(
    ShipStationResourceModel,
    RestfulGet,
    RestfulList,
    ShipStationPaginated,
    RestfulPost,
):
    """
    An interface of ShipStation Order
    """

    transform_in_data = DataInTrans()
    transform_out_data = DataOutTrans()

    path = 'orders'
    primary_key = 'id'

    @delegated
    @make_request_builder(
        method='POST',
        uri='/createorder',
    )
    def create_or_update_single_order(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )

    @delegated
    @make_request_builder(
        method='POST',
        uri='/createorders',
    )
    def create_or_update_multi_orders(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )
