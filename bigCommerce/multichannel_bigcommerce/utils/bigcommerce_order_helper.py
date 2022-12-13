# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from typing import Any
from datetime import datetime

from odoo.addons.channel_base_sdk.utils.common import resource_formatter as common_formatter

from .bigcommerce_api_helper import BigCommerceHelper

_logger = logging.getLogger(__name__)


class BigCommerceOrderHelper:
    def __init__(self, channel):
        self._api = BigCommerceHelper.connect_with_channel(channel)
    
    def cancel(self, id_on_channel):
        ack = self._api.orders.acknowledge(id_on_channel)
        ack._data._data = {'status_id': 5}
        return ack.put_one()


class BigCommerceOrderImporter:
    channel: Any
    ids: list
    created_from_date: datetime = None
    created_to_date: datetime = None
    modified_from_date: datetime = None
    modified_to_date: datetime = None
    all_records = False

    def do_import(self):
        params = self.prepare_common_params()
        yield from self.get_data(params)

    def prepare_common_params(self):                
        res = dict(sort='id:asc')
        if self.created_from_date:
            res['min_date_created'] = self.format_datetime(self.created_from_date)
        elif self.modified_from_date:
            res['min_date_modified'] = self.format_datetime(self.modified_from_date)
        else:
            res.update({
                'sort': 'id:desc'
            })
        
        if self.all_records:
            res['is_deleted'] = 'false'
        return res

    @classmethod
    def format_datetime(cls, value):
        return value.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    def get_data(self, kw):
        try:
            res = self.get_first_data(kw)
            yield res
            yield from self.get_next_data(res)
        except Exception as ex:
            _logger.exception("Error while getting order: %s", str(ex))
            raise

    def get_first_data(self, kw):
        api = BigCommerceHelper.connect_with_channel(self.channel)
        if self.ids:
            min_id, max_id = min(self.ids), max(self.ids)
            kw.update(min_id=min_id, max_id=max_id)
        if self.created_to_date:
            kw.update(max_date_created=self.format_datetime(self.created_to_date))
        elif self.modified_to_date:
            kw.update(max_date_modified=self.format_datetime(self.modified_to_date))
        res = api.orders.all(**kw)
        res = res.get_order_products()
        res = res.get_order_coupons()
        res = res.get_order_shipping_address()
        return res

    @classmethod
    def get_next_data(cls, res):
        while res:
            res = res.get_next_page()
            res = res.get_order_products()
            res = res.get_order_coupons()
            res = res.get_order_shipping_address()
            yield res


class SingularOrderDataInTrans(common_formatter.DataTrans):

    def __call__(self, order):
        basic_data = self.process_basic_data(order)
        order_lines = self.process_order_line(order)
        addresses = self.process_addresses(order)
        other_lines = self.process_other_lines(order)
        
        result = {
            **basic_data,
            **order_lines,
            **addresses,
            **other_lines
        }
        return result

    @classmethod
    def process_basic_data(cls, order):
        return {
            'name': order['id'],
            'customer_id': order.get('customer_id', 0),
            'id': order['id'],
            'channel_date_created': order['date_order'],
            'channel_order_ref': order['customer_reference'],
            'payment_gateway_code': order['payment_method'],
            'staff_notes': '',
            'status_id': order['status_id'],
            'currency_code': order['currency_code'],
        }
        
    @classmethod
    def process_order_line(cls, order):
        lines = []
        products_data = order['products_data'] if isinstance(order['products_data'], list) else [order['products_data']]
        for line in products_data:
            lines.append({
                'id_on_channel': str(line['id']),
                'name': line['name'],
                'variant_id': str(line['variant_id']),
                'product_id': str(line['product_id']),
                'sku': line['sku'],
                'price': float(line['price_ex_tax']),
                'quantity': float(line['quantity']),
                'tax_amount': float(line['total_tax'])/float(line['quantity'])
            })
        return {'lines': lines}
    
    @classmethod
    def process_addresses(cls, order):
        address = {}
        if 'shipping_addresses_data' in order:
            ship_add_data = order['shipping_addresses_data']
            address = ship_add_data[0] if isinstance(ship_add_data, list) else ship_add_data
        shipping_address, requested_shipping_method = {}, None
        if address:
            shipping_address = {
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
            requested_shipping_method = address['shipping_method']
            
        return {
            'billing_address': order['billing_address'],
            'shipping_address': shipping_address,
            'requested_shipping_method': requested_shipping_method
        }
    
    @classmethod
    def process_other_lines(cls, order):
        return {
            'taxes': [{'name': 'Tax', 'amount': order['tax_amount']}],
            'discount_amount': order['discount_amount'],
            'coupons': cls.process_coupon_data(order),
            'shipping_cost': order['shipping_cost'],
            'shipping_cost_tax': order['shipping_cost_tax'],
            'wrapping_cost': order['wrapping_cost'],
            'wrapping_cost_tax': order['wrapping_cost_tax'],
            'handling_cost': order['handling_cost'],
            'handling_cost_tax': order['handling_cost_tax'],
        }
        
    @classmethod
    def process_coupon_data(cls, order):
        coupons = {}
        if 'coupons_data' in order and order['coupons_data']:
            coupons_data = order['coupons_data'] if isinstance(order['coupons_data'], list) else [order['coupons_data']]
            for coupon in coupons_data:
                coupons['Coupon: %s' % coupon['code']] = float(coupon['discount'])
        return coupons


class BigCommerceOrderImportBuilder:
    transform_order = SingularOrderDataInTrans()
    orders: Any
    
    def prepare(self):
        for order in self.orders:
            order = self.transform_order(order)
            yield order
