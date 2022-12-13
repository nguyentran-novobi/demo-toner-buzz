# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ..request_builder import WooCommercePaginated
from ...common.resource import delegated
from ...common import PropagatedParam, resource_formatter as common_formatter
from ...restful.request_builder import make_request_builder
from .. import resource_formatter as woocommerce_formatter
from datetime import datetime
from odoo.tools import float_round

class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of WooCommerce order from channel to app
    """

    def __call__(self, order):
        basic_data = self.process_basic_data(order)    
        addresses_data = self.process_addresses_data(order) 
        order_line_data = self.process_order_line_data(order)
        shipping_line_data = self.process_shipping_line_data(order)  
        tax_data = self.process_tax_data(order)
        other_fees = self.process_other_fees_data(order) 
        result = {
            **basic_data,
            **addresses_data,
            **order_line_data,
            **shipping_line_data,
            **tax_data,
            **other_fees
        }       
        return result

    @classmethod
    def process_basic_data(cls, order):
        """
        Process basic data of the order
        """
        order.update({
            'id': str(order['id']),
            'date_order': datetime.strptime(order['date_created'], '%Y-%m-%dT%H:%M:%S'),
            'customer_reference': str(order['number']),
            'customer_message': order.get('customer_note', ''),
            'customer_id': order.get('customer_id', 0),
            'payment_method': order.get('payment_method_title', ''),
            'status': order['status']
        })
        return order
    
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
        address_keys = ('billing', 'shipping')
        for address_type, address_key in zip(address_types, address_keys):
            address = order.get(address_key, {})
            if address:
                name = f"{address.get('first_name', '')}"
                if address.get('last_name', ''):
                    name += f" {address.get('last_name', '')}"
                result[address_type] = {
                    'name': name,
                    'street': address.get('address_1', ''),
                    'street2': address.get('address_2', ''),
                    'city': address.get('city', ''),
                    'state_code': address.get('state', ''),
                    'country_code': address.get('country', ''),
                    'email': address.get('email', ''),
                    'phone': address.get('phone', ''),
                    'zip': address.get('postalCode', ''),
                    'company':  address.get('company', ''),
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
                'price': (float_round(float(line['subtotal']) / float(line['quantity']), precision_digits=2)) if float(
                line['quantity']) > 0 else 0,
                'product': {
                    'id': str(line['variation_id']) if line['variation_id'] else "%s - 0" % line['product_id'],
                    'sku':  str(line['sku']),
                    'parent_id': str(line['product_id'])
                },
                'quantity': float(line['quantity']),
                'description': line['name']            
            })
        return {'order_line': order_line}
    
    @classmethod
    def process_shipping_line_data(cls, order):
        """
        Process shipping datas of the order
        """
        result = {
            'requested_shipping_method': ','.join(l['method_title'] for l in order.get('shipping_lines', [])),
            'shipping_cost': order.get('shipping_total', 0.0)
        }
        return result
    
    @classmethod
    def process_tax_data(cls, order):
        """
        Process tax data of the order
        """
        return {'tax_amount': order.get('total_tax', 0.0)}
    
    @classmethod
    def process_other_fees_data(cls, order):
        """
        Process other fees such as discount, coupons of the order
        """
        coupons = {}
        coupon_lines = order.get('coupon_lines', [])
        total_coupon_discounts = 0
        for line in coupon_lines:
            code = 'Coupon: %s' % line['code']
            coupons[code] = coupons.get(code, 0.0) + float(line['discount'])
            total_coupon_discounts += float(line['discount'])
        other_fees_cost = sum(float(line['total']) for line in order['fee_lines']) if order.get('fee_lines', []) else 0.0
        return {'discount_amount': float(order.get('discount_total', 0.0)) - total_coupon_discounts, 
                'coupons': coupons,
                'other_fees_cost': other_fees_cost}
        
class DataInTrans(woocommerce_formatter.DataInTrans):
    """
    Specific data transformer for WooCommerce order from channel to app
    """
    transform_singular = SingularDataInTrans()


@register_model('orders')
class WooCommerceOrderModel(
    resource.WooCommerceResourceModel,
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulPut,
    request_builder.RestfulDelete,
    request_builder.RestfulList,
    WooCommercePaginated,
):
    """
    An interface of WooCommerce Order
    """
    path = 'orders'
    primary_key = 'id'

    transform_in_data = DataInTrans()
            
    @delegated
    def create_shipment(self, shipment_data, prop: PropagatedParam = None):
        """
        Create shipment for order
        """
        return None

    @delegated
    @make_request_builder(
        set_to='builder',
        method='PUT',
        uri='/{id}',
    )
    def cancel(self, prop: PropagatedParam=None, builder=None, **kwargs):
        """
        Cancel order
        """
        prop.resource.data.update(dict(status='cancelled'))
        return self.build_json_send_handle_json(
            builder,
            prop=prop,
            params=kwargs,
        )
