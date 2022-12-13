# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models, _

_logger = logging.getLogger(__name__)

class Picking(models.Model):
    _inherit = 'stock.picking'

    channel_id = fields.Many2one(related='sale_id.channel_id')