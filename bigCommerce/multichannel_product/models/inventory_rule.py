# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

class InventoryRule(models.Model):
    _name = 'inventory.rule'
    _description = 'Inventory Rule'

    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    qty_field_used = fields.Selection([('qty_available', 'Available'),
                                       ('virtual_available', 'Quantity On Hand'),
                                       ('fixed', 'Fixed')], string='Qty Field Used', required=True)

    quantity = fields.Integer(string='Quantity', required=True)
    based_on = fields.Selection([('percentage', 'Percentage of Total Inventory'),
                                 ('less', 'Less than Total Inventory'),
                                 ('more', 'More than Total Inventory'),
                                 ('fixed', '# of Unit(s)')], string='Based On', required=True)
    priority = fields.Integer(string='Priority')
    start_date = fields.Date(string='Start Date', default=fields.Date.today(), required=True)
    end_date = fields.Date(string='End Date')
    active = fields.Boolean(string='Active', default=True)
    type = fields.Selection([('global', 'Global'), ('channel', 'Channel'), ('warehouse', 'Warehouse')],
                            string='Type of Rule', required=True)
    is_deleted = fields.Boolean(string='Is deleted', default=True)