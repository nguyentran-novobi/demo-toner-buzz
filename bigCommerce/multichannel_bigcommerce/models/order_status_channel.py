# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

class OrderStatusChannel(models.Model):
    _inherit = 'order.status.channel'

    platform = fields.Selection(selection_add=[('bigcommerce', 'BigCommerce')], ondelete={'bigcommerce': 'set default'})