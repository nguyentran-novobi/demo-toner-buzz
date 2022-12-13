# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class OrderChannelTransaction(models.Model):
    _name = "order.channel.transaction"
    _description = "Order Transactions"

    order_id = fields.Many2one('sale.order', string='Order')
    channel_id = fields.Many2one('ecommerce.channel', string='Store', related='order_id.channel_id')
    gateway = fields.Char(string='Gateway')
    gateway_transaction_id = fields.Char(string='Gateway Transaction ID')
    amount = fields.Float(string='Amount')
    date_created = fields.Datetime(string='Date Created')
    datas = fields.Text(string='Datas')
    id_on_channel = fields.Char(help='ID of record on Channel')

    @api.model
    def create_jobs_for_synching(self, vals_list):
        """
        Spit values list to smaller list and add to Queue Job
        :param vals_list:
        :param channel_id:
        :return:
        """
        return self.with_delay()._sync_in_queue_job(vals_list).uuid

    @api.model
    def _sync_in_queue_job(self, vals_list):
        return self.create(vals_list).ids