# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import logging
import requests
from ..utils.bigcommerce_customer_helper import BigCommerceCustomerImporter, BigCommerceCustomerImportBuilder

_logger = logging.getLogger(__name__)

class CustomerChannel(models.Model):
    _inherit = "customer.channel"

    @api.model
    def bigcommerce_get_data(self, channel_id, id_on_channel=None, async_load=True, all_records=False):
        
        def prepare_importer(channel):
            res = BigCommerceCustomerImporter()
            res.channel = channel
            res.id_on_channel = id_on_channel
            res.all_records = all_records
            return res
        
        def prepare_builder(customer_data):
            res = BigCommerceCustomerImportBuilder()
            if isinstance(customer_data, dict):
                customer_data = [customer_data]
            res.customers = customer_data
            return res

        def fetch_customer(gen):
            while True:
                try:
                    customer = next(gen)
                    country = self.env['res.country'].sudo().search([('code', '=ilike', customer['country_code'])], limit=1)
                    state = self.env['res.country.state']
                    if country and customer['state_name']:
                        state = self.env['res.country.state'].sudo().search(
                            [('name', '=', customer['state_name']), ('country_id.id', '=', country.id)], limit=1)
                    customer.update({
                        'country_id': country.id,
                        'state_id': state.id
                    })
                    yield customer
                except StopIteration:
                    break

        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)
        importer = prepare_importer(channel)
        customers = []
        uuids = []
        for pulled in importer.do_import():
            if pulled.data:
                builder = prepare_builder(pulled.data)
                customers = list(fetch_customer(builder.prepare()))
                if async_load:
                    uuids.extend(self.create_jobs_for_synching(customers, channel_id))
                else:
                    # No create job
                    return self._sync_in_queue_job(customers, channel_id)
            else:
                if pulled.last_response == None or (pulled.last_response and not pulled.last_response.ok()):
                    _logger.error('Error while importing customer: %s',
                                  pulled.last_response.get_error())
                    channel.sudo().disconnect()

        return customers, uuids


