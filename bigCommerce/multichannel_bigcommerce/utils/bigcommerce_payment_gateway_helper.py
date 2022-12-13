# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from typing import Any

from .bigcommerce_api_helper import BigCommerceHelper, RateLimit, ExportError
from odoo.addons.channel_base_sdk.utils.common.exceptions import EmptyDataError
from odoo.addons.channel_base_sdk.utils.common import resource_formatter as common_formatter


_logger = logging.getLogger(__name__)


class BigcommercePaymentGatewayHelper:
    _api: BigCommerceHelper

    def __init__(self, channel):
        self._api = BigCommerceHelper.connect_with_channel(channel)


class BigCommercePaymentGatewayImporter:
    channel: Any
    ids: list
    all_records = False

    def do_import(self):
        params = self.prepare_common_params()
        yield from self.get_data(params)

    def prepare_common_params(self):
        res = dict(limit='100')
        return res

    def get_data(self, kw):
        try:
            res = self.get_first_data(kw)
            yield res
        except Exception as ex:
            _logger.exception("Error while getting payment gateway: %s", str(ex))
            raise

    def get_first_data(self, kw):
        api = BigCommerceHelper.connect_with_channel(self.channel)
        return api.payment_gateway.all(**kw)


class BigcommercePaymentGatewayImportBuilder:
    channel_id: Any
    payment_gateways: Any

    def prepare(self):
        if isinstance(self.payment_gateways, dict):
            self.payment_gateways = [self.payment_gateways]
        for payment_gateway in self.payment_gateways:
            yield payment_gateway
