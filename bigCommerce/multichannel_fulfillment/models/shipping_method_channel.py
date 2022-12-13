# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ShippingMethodChannel(models.Model):
    _name = 'shipping.method.channel'
    _description = 'Shipping Method on each Channel'

    name = fields.Char('Requested Service', required=True, index=True, copy=False)
    delivery_carrier_id = fields.Many2one('delivery.carrier', string='Shipping Service', copy=False)
    provider = fields.Char(string='Provider', store=True, compute='_compute_provider', copy=False)
    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True)
    active = fields.Boolean('Active', default=True, copy=False)

    _sql_constraints = [
        ('name_uniq', 'unique (name, channel_id)', 'This requested service has already existed. Enter another name.')
    ]

    @api.depends('delivery_carrier_id')
    def _compute_provider(self):
        for record in self:
            record.provider = record.delivery_carrier_id.delivery_type
