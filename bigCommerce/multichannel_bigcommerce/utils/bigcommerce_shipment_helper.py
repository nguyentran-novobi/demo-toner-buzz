# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from typing import Any
from odoo.addons.channel_base_sdk.utils.common import resource_formatter as common_formatter
from .bigcommerce_api_helper import BigCommerceHelper
import dateutil
import pytz
from odoo import fields

_logger = logging.getLogger(__name__)


class BigCommerceShipmentHelper:
    def __init__(self, channel):
        self._api = BigCommerceHelper.connect_with_channel(channel)
    
    def create(self, order_id, data):
        ack = self._api.order_shipment.acknowledge(None, order_id=order_id)
        ack.data = data
        return ack.publish()
    
    def update(self, id_on_channel, order_id, data):
        ack = self._api.order_shipment.recognize(id=id_on_channel, order_id=order_id)
        ack.data = data
        return ack.put_one()

    def cancel(self, id_on_channel, order_id):
        ack = self._api.order_shipment.acknowledge(id_on_channel, order_id=order_id)
        return ack.delete_one()


class SingularShipmentDataInTrans(common_formatter.DataTrans):
    
    def __call__(self, shipment):
        basic_data = self.process_basic_data(shipment)
        item_data = self.process_item_data(shipment)
        result = {
            **basic_data,
            **item_data
        }
        return result
    
    @classmethod
    def process_basic_data(cls, shipment):
        shipment.update({
            'id_on_channel': str(shipment['id']),
            'carrier_tracking_ref': shipment['tracking_number'],
            'merchant_shipping_cost': float(shipment['merchant_shipping_cost']),
            'merchant_shipping_carrier': shipment.get('shipping_provider', 'Other'),
            'tracking_url': shipment['tracking_link'],
            'note': shipment['comments'],
            'shipping_date': fields.Datetime.to_string(dateutil.parser.parse(shipment['date_created']).astimezone(
                pytz.utc).replace(tzinfo=None)),
            
        })
        return shipment
    
    @classmethod
    def process_item_data(cls, shipment):
        items = []
        for item in shipment['items']:
            items.append({
                'order_line_id_on_channel': str(item['order_product_id']),
                'quantity': item['quantity']
            })
            
        shipment.update({
            'items': items       
        })
        return shipment

    
class BigCommerceShipmentImportBuilder:
    transform_shipment = SingularShipmentDataInTrans()
    shipments: Any
    
    def prepare(self):
        for shipment in self.shipments:
            shipment = self.transform_shipment(shipment)
            yield shipment


class BigCommerceShipmentImporter:
    channel: Any
    order_id: str
    shipment_id: None
    
    def do_import(self):
        api = BigCommerceHelper.connect_with_channel(self.channel)
        ack = api.order_shipment.acknowledge(self.shipment_id, order_id=self.order_id)
        if self.shipment_id:
            res = ack.get_by_id()
        else:
            res = ack.all()
        return res
