# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from .. import resource
from ..registry import register_model
from ..request_builder import BigCommercePaginated
from ...common.resource import delegated
from ...common import PropagatedParam, resource_formatter as common_formatter
from .. import resource_formatter as bigcommerce_formatter
import pytz
from ...common.exceptions import EmptyDataError
from dateutil import parser

class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of BigCommerce order from channel to app
    """

    def __call__(self, order):
        basic_data = self.process_basic_data(order)
        billing_address_data = self.process_billing_address_data(order)
        fees_data = self.process_fees_data(order)
        discount_amount = self.compute_discount_amount(order)
        result = {
            **basic_data,
            **billing_address_data,
            **fees_data,
            **discount_amount
        }       
        return result

    @classmethod
    def process_basic_data(cls, order):
        """
        Process basic data of the order
        """
        result = {
            'id': str(order['id']),
            'customer_id': order.get('customer_id', 0),
            'date_order': parser.parse(order['date_created']).astimezone(pytz.utc).replace(tzinfo=None),
            'customer_reference': str(order['id']),
            'customer_message': order.get('customer_message', ''),
            'staff_notes': order.get('staff_notes', ''),
            'tax_amount': float(order['total_tax']),
            'discount_amount': float(order['discount_amount']),
            'status_id': order['status_id'],
            'payment_method': order['payment_method'],
            'currency_code': order['default_currency_code'].upper()
        }
        return result

    @classmethod
    def process_billing_address_data(cls, order):
        """
        Process billing address of the order
        """
        address = order['billing_address']
        return {
            'billing_address': {
                'name': "{first_name} {last_name}".format(first_name=address['first_name'], 
                                                            last_name=address['last_name']),
                'street': address.get('street_1', ''),
                'street2': address.get('street_2', ''),
                'city': address.get('city', ''),
                'state_code': '',
                'state_name': address.get('state', ''),
                'country_code': address.get('country_iso2', '').strip(),
                'email': address.get('email', ''),
                'phone': address.get('phone', ''),
                'zip': address.get('zip', ''),
                'company':  address.get('company', ''),
            }
        }
    
    @classmethod
    def process_fees_data(cls, order):
        return {
            'shipping_cost': float(order['shipping_cost_ex_tax']) or float(order['base_shipping_cost']),
            'shipping_cost_tax': float(order.get('shipping_cost_tax', 0.0)),
            'wrapping_cost': float(order.get('wrapping_cost_ex_tax', 0.0)),
            'wrapping_cost_tax': float(order.get('wrapping_cost_tax', 0.0)),
            'handling_cost': float(order.get('handling_cost_ex_tax', 0.0)),
            'handling_cost_tax': float(order.get('handling_cost_tax', 0.0)),
        }

    @classmethod
    def compute_discount_amount(cls, order):
        discount_amount = 0
        if float(order['discount_amount']) > 0 or float(order['coupon_discount']) > 0:
            costs = cls.process_fees_data(order)
            total_costs = costs['shipping_cost'] + costs['wrapping_cost'] + costs['handling_cost']
            discount_amount = float(order['subtotal_ex_tax']) + total_costs - float(order['total_ex_tax'])
        return {
            'discount_amount': discount_amount
        }
        
class DataInTrans(bigcommerce_formatter.DataInTrans):
    """
    Specific data transformer for BigCommerce order from channel to app
    """
    transform_singular = SingularDataInTrans()
    
@register_model('orders')
class BigCommerceOrderModel(
    resource.BigCommerceResourceModelV2,
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulPut,
    request_builder.RestfulDelete,
    request_builder.RestfulList,
    BigCommercePaginated,
):
    """
    An interface of BigCommerce Order
    """
    path = 'orders'
    primary_key = 'id'

    transform_in_data = DataInTrans()
            
    @delegated
    def get_order_products(self, prop: PropagatedParam = None):
        """
        Get Order Products
        """
        orders = prop.resource
        for order in filter(lambda o: o.data, orders):
            order_products = self.env['order_products'].acknowledge(None, order_id=order.data['id'])
            try:
                order.data.update({'products_data': order_products.all().data})
            except EmptyDataError:
                continue
        return self.pass_result_to_handler(resource=orders)
    
    @delegated
    def get_order_coupons(self, prop: PropagatedParam = None):
        """
        Get Order Coupons
        """
        orders = prop.resource
        for order in filter(lambda o: o.data, orders):
            order.data.update({'coupons_data': []})
            # order_coupons = self.env['order_coupons'].acknowledge(None, order_id=order.data['id'])
            # try:
            #     order.data.update({'coupons_data': order_coupons.all().data})
            # except EmptyDataError:
            #     continue
        return self.pass_result_to_handler(resource=orders)
    
    @delegated
    def get_order_shipping_address(self, prop: PropagatedParam = None):
        """
        Get Order Shipping Addresses
        """
        orders = prop.resource
        for order in filter(lambda o: o.data, orders):
            order_shipping_addresses = self.env['order_shipping_addresses'].acknowledge(None, order_id=order.data['id'])
            try:
                order.data.update({'shipping_addresses_data': order_shipping_addresses.all().data})
            except EmptyDataError:
                continue
        return self.pass_result_to_handler(resource=orders)

    @delegated
    def create_shipment(self, shipment_data, prop: PropagatedParam = None):
        """
        Create shipment for order
        """
        order = prop.self
        shipment = self.env['order_shipment'].acknowledge(None, order_id=order.data['id'])
        shipment.data = shipment_data
        return shipment.publish()
