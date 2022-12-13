# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class ProductChangeChannel(models.TransientModel):
    """
    This wizard is used to change product channel of product
    """
    _name = 'product.change.channel'
    _description = 'Change produdct channel'

    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', required=True)

    def change_product_channel(self):
        self.ensure_one()
        self.product_tmpl_id.with_context(get_information=True).write({'selected_channel_id': self.channel_id.id})
        return {'type': 'ir.actions.act_window_close', 'tag': 'reload'}
