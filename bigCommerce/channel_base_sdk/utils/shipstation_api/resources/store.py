# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ...common.resource import delegated
from ...restful.request_builder import make_request_builder
from ..resource import ShipStationResourceModel
from ..registry import register_model
from ...restful.request_builder import RestfulGet, RestfulList


@register_model('stores')
class ShipStationStoreModel(
    ShipStationResourceModel,
    RestfulGet,
    RestfulList,
):
    """
    An interface of ShipStation Stores
    """

    path = 'stores'
    primary_key = 'id'
