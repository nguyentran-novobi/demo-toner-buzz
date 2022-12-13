# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common.resource import delegated
from ...restful.request_builder import make_request_builder
from ...common import PropagatedParam
from ...restful.request_builder import RequestBuilder
from ..resource import ShipStationResourceModel
from ..registry import register_model
from ...restful.request_builder import RestfulGet, RestfulList


@register_model('carriers')
class ShipStationCarrierModel(
    ShipStationResourceModel,
    RestfulGet,
    RestfulList,
):
    """
    An interface of ShipStation Carrier and Services
    """

    path = 'carriers'
    primary_key = 'id'

    @delegated
    @make_request_builder(
        method='GET',
        uri='/listservices',
    )
    def get_list_services(self, carrier_code, prop: PropagatedParam = None, request_builder: RequestBuilder = None, **kwargs):
        return self.build_json_send_handle_json(
            request_builder,
            prop=prop,
            params={**{'carrierCode': carrier_code}, **kwargs},
        )
