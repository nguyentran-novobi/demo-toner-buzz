# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import dateutil.parser
import pytz
import uuid

from ...restful import request_builder
from .. import resource_formatter as ebay_formatter
from ..registry import register_model


class SingularDataInTrans(ebay_formatter.DataTrans):
    """
    Transform only 1 single data of eBay shipment from channel to app
    """

    def __call__(self, shipment):
        basic_data = self.process_basic_data(shipment)
        shipment_line_data = self.process_shipment_line_data(shipment)

        result = {
            **basic_data,
            **shipment_line_data,
        }

        return result

    @classmethod
    def process_basic_data(cls, shipment):
        return {
            'id': shipment.get('fulfillmentId', f'N/A-{uuid.uuid4()}'),
            'tracking_ref': shipment.get('shipmentTrackingNumber', ''),
            'carrier': shipment.get('shippingCarrierCode', ''),
            'shipping_date': dateutil.parser.parse(shipment['shippedDate']).astimezone(pytz.utc).replace(tzinfo=None) if shipment.get('shippedDate', False) else False,
        }

    @classmethod
    def process_shipment_line_data(cls, shipment):
        lines = []
        for item in shipment.get('lineItems', []):
            line_values = {'order_line_id': str(item['lineItemId'])}
            if 'quantity' in item:
                line_values['quantity'] = float(item['quantity'])
            lines.append(line_values)
        return {
            'lines': lines,
        }


class DataInTrans(ebay_formatter.DataInTrans):
    """
    Specific data transformer for Shopify shipment from channel to app
    """
    resource_plural_name = 'fulfillments'
    transform_singular = SingularDataInTrans()


class SingularDataOutTrans(ebay_formatter.DataTrans):
    """
    Specific data transformer for Shopify shipment from app to channel
    """
    def __call__(self, data):
        basic_data = self.process_basic_data(data)
        line_data = self.process_line_data(data)

        result = {
            **basic_data,
            **line_data
        }
        return result

    @classmethod
    def process_basic_data(cls, data):
        """
        Process data to prepare basic info for shipment
        """
        res = {
            "shippedDate": data.get('shipped_date'),
            "shippingCarrierCode": data['carrier_code'],
            "trackingNumber": data['tracking_number']
        }
        res = {k: v for k, v in res.items() if v}
        return res

    @classmethod
    def process_line_data(cls, data):
        """
        Process data to prepare item lines for shipment
        """
        line_items = []
        for line in data['line_items']:
            line_items.append({
                'lineItemId': str(line['id']),
                'quantity': int(line['quantity'])
            })
        return {'lineItems': line_items}


class DataOutTrans(ebay_formatter.DataOutTrans):
    """
    Specific data transformer for eBay shipment from app to channel
    """
    transform_singular = SingularDataOutTrans()


@register_model('order_fulfillment')
class eBayOrderFulfillmentModel(
    request_builder.RestfulGet,
    request_builder.RestfulPost,
    request_builder.RestfulList,
):
    """
    An interface of eBay Order Fulfillment
    """
    prefix = '/sell/fulfillment/v1/order/{order_id}/'
    path = 'shipping_fulfillment'
    primary_key = 'id'
    secondary_keys = ('order_id',)

    transform_in_data = DataInTrans()
    transform_out_data = DataOutTrans()
