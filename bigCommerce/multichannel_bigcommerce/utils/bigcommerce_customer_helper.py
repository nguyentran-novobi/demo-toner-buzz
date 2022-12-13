# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from typing import Any
from datetime import datetime
from .bigcommerce_api_helper import BigCommerceHelper
from odoo.addons.channel_base_sdk.utils.common import resource_formatter as common_formatter
from odoo.addons.channel_base_sdk.utils.common.exceptions import EmptyDataError

_logger = logging.getLogger(__name__)

class BigCommerceCustomerHelper:
    _api: BigCommerceHelper

    def __init__(self, channel):
        self._api = BigCommerceHelper.connect_with_channel(channel)
        
class BigCommerceCustomerImporter:
    channel: Any
    id_on_channel: str
    all_records = False

    def do_import(self):
        params = self.prepare_common_params()
        yield from self.get_data(params)

    def prepare_common_params(self):                
        res = dict(limit='250', sort='id:asc', include='addresses')
        return res

    def get_data(self, kw):
        try:
            res = self.get_first_data(kw)
            yield res
            yield from self.get_next_data(res)
        except Exception as ex:
            _logger.exception("Error while getting customer: %s", str(ex))
            raise

    def get_first_data(self, kw):
        api = BigCommerceHelper.connect_with_channel(self.channel)
        if self.id_on_channel:
            ack = api.customers.acknowledge(self.id_on_channel)
            res = ack.get_by_id(**kw)
        else:
            res = api.customers.all(**kw)
        return res

    def get_next_data(self, res):
        try:
            while res.data:
                res = res.get_next_page()
                yield res
        except EmptyDataError:
            pass

class SingularCustomerDataInTrans(common_formatter.DataTrans):

    def __call__(self, customer):
        basic_data = self.process_basic_data(customer)        
        result = {
            **basic_data,
        }
        return result

    @classmethod
    def process_basic_data(cls, customer):
        return {
            'name': "{} {}".format(customer['first_name'], customer['last_name']),
            'phone': customer.get('phone', ''),
            'email': customer['email'],
            'id': customer['id'],
            'street': customer.get('street', ''),
            'street2': customer.get('street2', ''),
            'city': customer.get('city', ''),
            'zip': customer.get('zip', ''),
            'state_name': customer.get('state_name', ''),
            'country_code': customer.get('country_code', ''),
        }
        
class BigCommerceCustomerImportBuilder:
    transform_customer = SingularCustomerDataInTrans()
    customers: Any
    
    def prepare(self):
        for customer in self.customers:
            customer = self.transform_customer(customer)
            yield customer