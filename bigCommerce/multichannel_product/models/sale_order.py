# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import logging
import json

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def process_transactions(self, transactions, record):
        ############################################################################
        # @ Description
        #   - Process common part of getting transaction from each channel
        #   - This function will be called in function _get_order_transactions in sale_order.py of each channel
        # @ Parameters
        #   - list_tax_amount (list) : list amount value of Tax
        # @ Return
        #   - None
        ############################################################################
        result = []
        synced_transactions = record.channel_transaction_ids.mapped(
            'id_on_channel') if record.channel_transaction_ids else []
        new_transactions = list(filter(lambda t: t['id'] not in synced_transactions, transactions))
        for transaction in new_transactions:
            result.append({
                'gateway': transaction.get('gateway'),
                'gateway_transaction_id': transaction.get('gateway_transaction_id'),
                'amount': transaction.get('amount'),
                'date_created': transaction.get('date_created'),
                'datas': json.dumps(transaction),
                'id_on_channel': transaction.get('id'),
                'order_id': record.id
            })
        return result
