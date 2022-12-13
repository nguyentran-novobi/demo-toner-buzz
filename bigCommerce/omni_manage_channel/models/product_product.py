# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _create_inventory_adjustment(self, datas):
        company_user = self.env.company
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', company_user.id)], limit=1)
        if warehouse:
            location_id = warehouse.lot_stock_id.id
        vals = {
            'name': 'Sync Inventory',
            'filter': 'partial',
            'line_ids': [(0, 0, {
                'product_id': e['product_id'],
                'product_qty': e['product_qty'],
                'location_id': location_id
            }) for e in datas]
        }
        record = self.env['stock.inventory'].sudo().create(vals)
        record._action_done()

    @api.model
    def _import_inventory(self, channel_id, data_inventory):
        datas = []
        ids = [key for key in list(data_inventory.keys())]
        products = self.env['product.channel.variant'].sudo().search([('id_on_channel', 'in', ids),
                                                                      ('id_on_channel', '!=', False),
                                                                      ('channel_id.id', '=', channel_id),
                                                                      ('product_product_id.type', '=', 'product')])
        for product in products:
            datas.append({
                'product_id': product.product_product_id.id,
                'product_qty': float(data_inventory[product.id_on_channel])
            })
        self._create_inventory_adjustment(datas)
        return True