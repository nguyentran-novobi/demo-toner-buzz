# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import pytz

from dateutil import parser

from ...common import PropagatedParam, resource_formatter as common_formatter
from ...common.resource import delegated
from ...restful.request_builder import RestfulGet, RestfulPost, RestfulPut, RestfulDelete, RestfulList
from ...restful.request_builder import RequestBuilder, make_request_builder

from .. import resource_formatter as shopify_formatter
from ..registry import register_model
from ..resource import ShopifyResourceModel
from ..request_builder import ShopifyPaginated


class DataCommonTrans(shopify_formatter.DataCommonTrans):
    resource_singular_name = 'fulfillment'
    resource_plural_name = 'fulfillments'


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of Shopify shipment from channel to app
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
            'id': shipment['id'],
            'tracking_ref': ','.join(shipment['tracking_numbers']) if shipment.get('tracking_numbers', []) else '',
            'carrier': shipment.get('tracking_company', ''),
            'tracking_url': ','.join(shipment.get('tracking_urls', [])),
            'shipping_date': parser.parse(shipment['created_at']).astimezone(pytz.utc).replace(tzinfo=None),
            'name': shipment['name'],
            'status': shipment['status']
        }

    @classmethod
    def process_shipment_line_data(cls, shipment):
        lines = []
        is_physical_shipment = False
        for item in shipment.get('line_items', []):
            lines.append({
                'order_line_id': str(item['id']),
                'quantity': item['quantity']
            })
            is_physical_shipment = item['requires_shipping']
        return {
            'lines': lines,
            'is_physical_shipment': is_physical_shipment
        }


class DataInTrans(DataCommonTrans, shopify_formatter.DataInTrans):
    """
    Specific data transformer for Shopify shipment from channel to app
    """
    transform_singular = SingularDataInTrans()


class SingularDataOutTrans(common_formatter.DataTrans):
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
        return {
            "location_id": data['location_id'],
            "status": "success",
            "tracking_company": data['tracking_company'],
            "tracking_numbers": data['tracking_numbers']
        }

    @classmethod
    def process_line_data(cls, data):
        """
        Process data to prepare item lines for shipment
        """
        line_items = []
        for line in data['line_items']:
            line_items.append({
                'id': int(line['id']),
                'quantity': line['quantity']
            })
        return {'line_items': line_items}


class DataOutTrans(DataCommonTrans, shopify_formatter.DataOutTrans):
    """
    Specific data transformer for Shopify shipment from app to channel
    """
    transform_singular = SingularDataOutTrans()


@register_model('order_fulfillment')
class ShopifyOrderFulfillmentModel(
    ShopifyResourceModel,
    RestfulGet,
    RestfulPost,
    RestfulPut,
    RestfulDelete,
    RestfulList,
    ShopifyPaginated,
):
    """
    An interface of Shopify Order Fulfillment
    """
    prefix = 'orders/{order_id}/'
    path = 'fulfillments'
    postfix = '.json'
    primary_key = 'id'
    secondary_keys = ('order_id',)

    transform_in_data = DataInTrans()
    transform_out_data = DataOutTrans()

    @delegated
    @make_request_builder(
        method='POST',
        uri='/{id}/cancel',
    )
    def cancel(self, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        """
        Cancel shipment
        :param prop: The data propagated from the handler
        :param request_builder: Request builder from the handler
        :param kwargs: Optional options
        """
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params=kwargs)
