# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytz

from dateutil import parser

from ...common import PropagatedParam, resource_formatter as common_formatter
from ...common.resource import delegated

from ...restful.request_builder import RequestBuilder
from ...restful.request_builder import RestfulGet, RestfulPost, RestfulPut, RestfulDelete, RestfulList, make_request_builder

from ..registry import register_model
from ..resource import ShopifyResourceModel
from ..request_builder import ShopifyPaginated
from .. import resource_formatter as shopify_formatter

class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify order from channel to app
    """

    def __call__(self, order):
        basic_data = self.process_basic_data(order)
        shipping_line_data = self.process_shipping_line_data(order)
        addresses_data = self.process_addresses_data(order)
        order_line_data = self.process_order_line_data(order)
        tax_data = self.process_tax_data(order)
        other_fees = self.process_other_fees_data(order)

        result = {
            **basic_data,
            **shipping_line_data,
            **addresses_data,
            **order_line_data,
            **tax_data,
            **other_fees
        }        
        return result

    @classmethod
    def process_basic_data(cls, order):
        """
        Process basic data of the order
        """
        result = {
            'id': str(order['id']),
            'date_order': parser.parse(order['created_at']).astimezone(pytz.utc).replace(tzinfo=None),
            'customer_reference': str(order['order_number']),
            'customer_message': order.get('note', ''),
            'financial_status': order.get('financial_status', ''),
            'fulfillment_status': order.get('fulfillment_status', ''),
            'customer_id': order.get('customer', {}).get('id', 0),
            'gateway': order.get('gateway', ''),
            'name': order['name'],
            'currency_code': order['currency'].upper(),
        }
        return result

    @classmethod
    def process_shipping_line_data(cls, order):
        """
        Process shipping datas of the order
        """
        shipping_cost = 0
        tmp_shipping_method = []
        for shipping_line in order.get('shipping_lines', []):
            name = '%s: %s' % (shipping_line['source'].replace('_', ' ').title(), shipping_line['title']) if shipping_line['source'] else shipping_line['title']
            shipping_cost += float(shipping_line['price'])
            tmp_shipping_method.append(name)

        requested_shipping_method = ', '.join(tmp_shipping_method) or 'None'
        result = {
            'requested_shipping_method': requested_shipping_method,
            'shipping_cost': shipping_cost
        }
        return result

    @classmethod
    def process_addresses_data(cls, order):
        """
        Process billing and shipping address of the order
        """
        result = {
            'billing_address': {},
            'shipping_address': {}
        }
        address_types = ('billing_address', 'shipping_address')
        for address_type in address_types:
            address = order.get(address_type)
            if address:
                result[address_type] = {
                    'name': address.get('name', ''),
                    'street': address.get('address1', ''),
                    'street2': address.get('address2', ''),
                    'city': address.get('city', ''),
                    'state_code': address.get('province_code', ''),
                    'country_code': address.get('country_code', ''),
                    'email': address.get('email', ''),
                    'phone': address.get('phone', ''),
                    'zip': address.get('zip', ''),
                    'company': address.get('company', ''),
                }
        return result

    @classmethod
    def process_order_line_data(cls, order):
        """
        Process order line data of the order
        """
        order_line = []
        for line in order.get('line_items', []):
            order_line.append({
                'id': str(line['id']),
                'price': float(line['price']),
                'product': {
                    'id': str(line['variant_id']),
                    'sku': str(line['sku']),
                    'parent_id': str(line['product_id'])
                },
                'quantity': float(line['quantity']),
                'description': line['name'],
                'requires_shipping': line.get('requires_shipping', False)
            })
        return {'order_line': order_line}

    @classmethod
    def process_tax_data(cls, order):
        """
        Process tax data of the order
        """
        amount = sum(map(lambda l: float(l['price']), order.get('tax_lines', [])))
        return {'tax_amount': amount}

    @classmethod
    def process_other_fees_data(cls, order):
        """
        Process other fees such as discount, coupons of the order
        """
        disount_amount = 0.0
        coupons = {}
        discount_applications = order['discount_applications']
        for line in order.get('line_items', []):
            if line['discount_allocations']:
                for applied_discount in line['discount_allocations']:
                    discount_application = discount_applications[applied_discount['discount_application_index']]
                    if discount_application['type'] == 'manual' or discount_application['type'] == 'automatic':
                        disount_amount += float(applied_discount['amount'])
                    elif discount_application['type'] == 'discount_code':
                        code = 'Coupon: %s' % discount_application['code']
                        coupons[code] = coupons.get(code, 0.0) + float(applied_discount['amount'])
        return {'discount_amount': disount_amount, 'coupons': coupons}


class DataInTrans(shopify_formatter.DataInTrans):
    """
    Specific data transformer for Shopify order from channel to app
    """
    transform_singular = SingularDataInTrans()
    resource_singular_name = 'order'
    resource_plural_name = 'orders'


@register_model('orders')
class ShopifyOrderModel(
    ShopifyResourceModel,
    RestfulGet,
    RestfulPost,
    RestfulPut,
    RestfulDelete,
    RestfulList,
    ShopifyPaginated,
):
    """
    An interface of Shopify Order
    """
    path = 'orders'
    postfix = '.json'
    primary_key = 'id'

    transform_in_data = DataInTrans()

    @delegated
    @make_request_builder(
        method='POST',
        uri='/{id}/cancel',
    )
    def cancel(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Cancel order
        :param prop: The data propagated from the handler
        :param request_builder: Request builder from the handler
        :param kwargs: Optional options
        """
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs,
        )

    @delegated
    def create_shipment(self, shipment_data, prop: PropagatedParam = None):
        """
        Create shipment for order
        """
        order = prop.self
        shipment = self.env['order_fulfillment'].acknowledge(None, order_id=order.data['id'])
        shipment.data = shipment_data
        return shipment.publish()
