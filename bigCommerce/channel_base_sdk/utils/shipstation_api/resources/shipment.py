# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import dateutil
import pytz

from ...common.resource import delegated
from ...restful.request_builder import make_request_builder
from ...common import PropagatedParam
from ...restful.request_builder import RequestBuilder
from ..resource import ShipStationResourceModel
from ..registry import register_model
from ...restful.request_builder import RestfulGet, RestfulList
from .. import resource_formatter as shipstation_formatter
from ...common import resource_formatter as common_formatter


class SingularDataInTrans(common_formatter.DataTrans):
    """
    Transform only 1 single data of ShipStation shipment from channel to app
    """

    def __call__(self, shipment):
        basic_data = self.process_basic_data(shipment)
        shipment_address_data = self.process_shipment_address_data(shipment)
        shipment_line_data = self.process_shipment_line_data(shipment)

        result = {
            **basic_data,
            **shipment_address_data,
            **shipment_line_data,
        }
        return result

    @classmethod
    def process_basic_data(cls, shipment):
        return {
            'id_on_shipstation': shipment['shipmentId'],
            'carrier_tracking_ref': shipment['trackingNumber'],
            'ss_carrier_code': shipment['carrierCode'],
            'ss_service_code': shipment['serviceCode'],
            'merchant_shipping_cost': 0.0,
            'shipping_cost': shipment['shipmentCost'],
            'insurance_cost': shipment['insuranceCost'],
            'requested_carrier': '',
            'tracking_url': '',
            'note': '',
            'shipping_date': dateutil.parser.parse(shipment['shipDate']).astimezone(pytz.utc).replace(tzinfo=None),
            'voided': shipment['voided'],
        }

    @classmethod
    def process_shipment_address_data(cls, shipment):
        address = shipment['shipTo'] or {}
        shipping_address = {
            'name': address.get('name'),
            'street_1': address.get('street1', ''),
            'street_2': address.get('street2', ''),
            'city': address.get('city', ''),
            'state': address.get('state', ''),
            'country_iso2': address.get('country', '').strip(),
            'email': address.get('email', ''),
            'phone': address.get('phone', ''),
            'zip': address.get('postalCode', ''),
            'company': address.get('company', ''),
        }
        return {'shipping_address': shipping_address}

    @classmethod
    def process_shipment_line_data(cls, shipment):
        shipment_items = shipment['shipmentItems'] or []
        items = []
        for item in shipment_items:
            items.append({
                'id_on_shipstation': item['orderItemId'],
                'quantity': item['quantity']
            })
        return {'items': items}


class DataInTrans(shipstation_formatter.DataInTrans):
    """
    Specific data transformer for ShipStation shipment from channel to app
    """
    transform_singular = SingularDataInTrans()
    resource_plural_name = 'shipments'


@register_model('shipments')
class ShipStationShipmentModel(
    ShipStationResourceModel,
    RestfulGet,
    RestfulList,
):
    """
    An interface of ShipStation Shipments
    """

    transform_in_data = DataInTrans()

    path = 'shipments'
    primary_key = 'id'
