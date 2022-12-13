# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class OrderShipmentItem(models.Model):
    _name = 'order.shipment.item'
    _description = 'Order Shipment Items'

    order_shipment_id = fields.Many2one('order.shipment')
    order_line_id = fields.Many2one('sale.order.line')
    quantity = fields.Float(string='Quantity')

class OrderShipment(models.Model):
    _name = "order.shipment"
    _description = "Order Shipments"

    order_id = fields.Many2one('sale.order', string='Order')
    id_on_channel = fields.Char(string='ID on Channel')
    shipping_method = fields.Char(string='Shipment Method')
    shipment_provider = fields.Char(string='Shipment Provider')
    tracking_number = fields.Char(string='Tracking Number')
    tracking_carrier = fields.Char(string='Tracking Carrier')
    item_line_ids = fields.One2many('order.shipment.item', 'order_shipment_id', string='Items')
    datas = fields.Text(string='Datas')

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