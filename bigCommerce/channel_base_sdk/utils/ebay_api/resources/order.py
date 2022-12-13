# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...restful import request_builder

from ..registry import register_model
from ..request_builder import eBayPaginated
from ...common.resource import delegated
from ...common import PropagatedParam, resource_formatter as common_formatter
from .. import resource_formatter as ebay_formatter
import dateutil
import pytz

class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of eBay order from channel to app
    """

    def __call__(self, order):
        basic_data = self.process_basic_data(order)    
        shipping_address = self.process_shipping_address(order) 
        order_line_data = self.process_order_line_data(order)
        shipping_line_data = self.process_shipping_line_data(order)  
        tax_data = self.process_tax_data(order)
        other_fees = self.process_other_fees_data(order) 
        result = {
            **basic_data,
            **shipping_address,
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
        payments = order.get('paymentSummary', {}).get('payments', [])
        result = {
            'id': str(order['orderId']),
            'date_order': dateutil.parser.parse(order['creationDate']).astimezone(pytz.utc).replace(tzinfo=None),
            'legacy_order_id': str(order['legacyOrderId']),
            'customer_reference': str(order['orderId']),
            'customer_message': order.get('buyerCheckoutNotes', False),
            'customer_id': order.get('buyer', {}).get('username', ''),
            'payment_method': payments[0]['paymentMethod'] if payments else '',
            'status': order['orderFulfillmentStatus']
        }
        return result
    
    @classmethod
    def process_shipping_address(cls, order):
        """
        Process billing and shipping address of the order
        """
        result = {
            'billing_address': {},
            'shipping_address': {},
            'shipping_carrier_code': '',
            'shipping_service_code': ''
        }
        address_data = order['fulfillmentStartInstructions'][0] if order['fulfillmentStartInstructions'] else {}
        shipping_step =  address_data.get('shippingStep', {})
        shipping_address = dict(**shipping_step.get('shipTo', {}).get('contactAddress', {}), 
                                **shipping_step.get('shipTo', {}))
        address_types = ('billing_address', 'shipping_address')
        address_keys = ('billing', 'shipping')
        
        datas = {
            'billing': shipping_address,
            'shipping': shipping_address
        }
        
        # Set billing info as final destination address when order is shipped by eBay
        if address_data.get('ebaySupportedFulfillment', False):
            address = address_data['finalDestinationAddress']
            datas['billing'] = dict(fullName=order['buyer']['username'], **address)
            
        for address_type, address_key in zip(address_types, address_keys):
            address = datas[address_key]
            if address:
                result[address_type] = {
                    'name': address['fullName'],
                    'street': address.get('addressLine1', ''),
                    'street2': address.get('addressLine2', ''),
                    'city': address.get('city', ''),
                    'state_code': address.get('stateOrProvince', ''),
                    'country_code': address.get('countryCode', ''),
                    'email': address.get('email', ''),
                    'phone': address.get('primaryPhone', {}).get('phoneNumber', ''),
                    'zip': address.get('postalCode', ''),
                    'company':  address.get('companyName', ''),
                }
        result.update({
            'shipping_carrier_code': shipping_step.get('shippingCarrierCode', {}),
            'shipping_service_code': shipping_step.get('shippingServiceCode', {})
        })
        return result
    
    @classmethod
    def process_order_line_data(cls, order):
        """
        Process order line data of the order
        """            
        order_line = []
        for line in order['lineItems']:
            order_line.append({
                'id': str(line['lineItemId']),
                'price': round(float(line['lineItemCost'].get('value', 0.0)) / line['quantity'], 2),
                'product': {
                    'id': False if line.get('legacyVariationId', '') else "%s - 0" % line['legacyItemId'],
                    'sku':  str(line.get('sku', '')),
                    'parent_id': str(line['legacyItemId'])
                },
                'quantity': float(line['quantity']),
                'description': line['title']            
            })
        return {'order_line': order_line}
    
    @classmethod
    def process_shipping_line_data(cls, order):
        """
        Process shipping datas of the order
        """
        result = {
            'shipping_cost': order['pricingSummary']['deliveryCost']['value']
        }
        return result
    
    @classmethod
    def process_tax_data(cls, order):
        """
        Process tax data of the order
        """
        tax_amount = 0.0
        for line in order['lineItems']:
            tax_amount += sum(float(tax['amount']['value']) for tax in line['taxes'])
        return {'taxes': [{'name': 'Tax', 'amount': tax_amount}]}
    
    @classmethod
    def process_other_fees_data(cls, order):
        """
        Process other fees such as discount, coupons of the order
        """
        delivery_discount = order['pricingSummary'].get('deliveryDiscount', {}).get('value', 0.0)
        subtotal_discount = order['pricingSummary'].get('priceDiscountSubtotal', {}).get('value', 0.0)
        fee_amount = order['pricingSummary'].get('fee', {}).get('value', 0.0)
        return {'discount_amount': float(delivery_discount) + float(subtotal_discount),
                'other_fees_cost': float(fee_amount)}
        
class DataInTrans(ebay_formatter.DataInTrans):
    """
    Specific data transformer for eBay order from channel to app
    """
    resource_plural_name = 'orders'
    transform_singular = SingularDataInTrans()


@register_model('orders')
class eBayOrderModel(
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulPut,
    request_builder.RestfulDelete,
    request_builder.RestfulList,
    eBayPaginated,
):
    """
    An interface of eBay Order
    """
    path = '/sell/fulfillment/v1/order'
    primary_key = 'id'

    transform_in_data = DataInTrans()
            
    @delegated
    def create_shipment(self, shipment_data, prop: PropagatedParam = None):
        """
        Create shipment for order
        """
        order = prop.self
        shipment = self.env['order_fulfillment'].acknowledge(None, order_id=order.data['id'])
        shipment.data = shipment_data
        return shipment.publish()
