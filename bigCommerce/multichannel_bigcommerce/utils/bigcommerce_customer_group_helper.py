# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from typing import Any

from .bigcommerce_api_helper import BigCommerceHelper, RateLimit, ExportError, NotFoundError
from odoo.addons.channel_base_sdk.utils.common.exceptions import EmptyDataError
from odoo.addons.channel_base_sdk.utils.common import resource_formatter as common_formatter


_logger = logging.getLogger(__name__)


class BigcommerceCustomerGroupHelper:
    _api: BigCommerceHelper

    def __init__(self, channel):
        self._api = BigCommerceHelper.connect_with_channel(channel)

    @classmethod
    def prepare_data(cls, customer_group):
        return {
            'name': customer_group.name,
            'category_access': 'all' if customer_group.has_all_categories_access else 'specific',
            'categories': customer_group.categ_ids.mapped('id_on_channel'),
        }

    def create(self, customer_group):
        data = self.prepare_data(customer_group)
        ack = self._api.customer_group.acknowledge(None)
        ack.data = data
        res = ack.publish()
        if res.ok():
            return res
        elif res.get_status_code() == 429:
            raise RateLimit("Rate limit while exporting customer group to Bigcommerce")
        else:
            raise ExportError(res.get_error_message())

    def update(self, customer_group):
        data = self.prepare_data(customer_group)
        ack = self._api.customer_group.acknowledge(customer_group.id_on_channel)
        ack.data = data
        res = ack.put_one()
        if res.ok():
            return res
        elif res.get_status_code() == 429:
            raise RateLimit("Rate limit while exporting customer group to Bigcommerce")
        elif res.get_status_code() == 404:
            raise NotFoundError("Not Found")
        else:
            raise ExportError(res.get_error_message())

    def delete(self, id_on_channel):
        ack = self._api.customer_group.acknowledge(id_on_channel)
        res = ack.delete_one()
        if res.ok():
            return res
        elif res.get_status_code() == 429:
            raise RateLimit("Rate limit while deleting customer group to Bigcommerce")
        else:
            raise ExportError(res.get_error_message().get('title'))


class BigCommerceCustomerGroupImporter:
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
            yield from self.get_next_data(res)
        except Exception as ex:
            _logger.exception("Error while getting customer group: %s", str(ex))
            raise

    def get_first_data(self, kw):
        api = BigCommerceHelper.connect_with_channel(self.channel)
        if self.ids:
            vals = []
            for id in self.ids:
                ack = api.customer_group.acknowledge(id.strip())
                try:
                    vals.append(ack.get_by_id().data)
                except EmptyDataError:
                    pass
            res = api.customer_group.create_collection_with(vals)
        else:
            res = api.customer_group.all(**kw)
        return res

    def get_next_data(self, res):
        try:
            while res.data:
                res = res.get_next_page()
                yield res
        except EmptyDataError:
            pass


class SingularCustomerGroupDataInTrans(common_formatter.DataTrans):

    def __call__(self, customer_group):
        basic_data = self.process_basic_data(customer_group)
        result = {
            **basic_data,
        }
        return result

    @classmethod
    def process_basic_data(cls, customer_group):
        return {
            'id_on_channel': str(customer_group['id']),
            'name': customer_group['name'],
            'has_all_categories_access': customer_group['category_access'],
        }


class BigcommerceCustomerGroupImportBuilder:
    channel_id: Any
    customer_groups: Any
    transform_singular = SingularCustomerGroupDataInTrans()

    def prepare(self):
        if isinstance(self.customer_groups, dict):
            self.customer_groups = [self.customer_groups]
        for customer_group in self.customer_groups:
            yield self.transform_singular(customer_group), customer_group['categories']
