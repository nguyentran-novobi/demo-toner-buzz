import logging
from itertools import groupby

from odoo import api, models, _

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    @api.model
    def _compute_quantity_to_ship_for_kit(self, phantom_lines):
        filters = {
            'incoming_moves': lambda m: m.location_dest_id.usage == 'customer' and (not m.origin_returned_move_id or (m.origin_returned_move_id and m.to_refund)),
            'outgoing_moves': lambda m: m.location_dest_id.usage != 'customer' and m.to_refund
        }
        res = {}
        for order_line, g in groupby(phantom_lines.sorted(key=lambda r: r.sale_line_id.id), key=lambda r: r.sale_line_id):
            moves = self.env['stock.move'].concat(*list(g))
            bom = moves[0].bom_line_id.bom_id
            order_qty = order_line.product_uom._compute_quantity(order_line.product_uom_qty, bom.product_uom_id)
            qty_delivered = moves._compute_kit_quantities(order_line.product_id, order_qty, bom, filters)
            qty_delivered = bom.product_uom_id._compute_quantity(qty_delivered, order_line.product_uom)
            number_of_bom = qty_delivered / bom.product_qty
            res[order_line] = {
                'qty_delivered': qty_delivered,
                'qty_component_deliveried': {}
            }
            number_of_bom = qty_delivered / bom.product_qty
            for bom_line in bom.bom_line_ids:
                res[order_line]['qty_component_deliveried'][bom_line.product_id] = res[order_line]['qty_component_deliveried'].get(bom_line.product_id, 0) + bom_line.product_qty * number_of_bom
        return res

    def _prepare_exported_shipment_items(self, moves):
        phantom_lines = moves.filtered(lambda l: l.bom_line_id.bom_id.type == 'phantom')
        shipment_items, exported_items =  super()._prepare_exported_shipment_items(moves - phantom_lines)
        if phantom_lines:
            res = self._compute_quantity_to_ship_for_kit(phantom_lines)
            for order_line, values in res.items():
                shipment_items.append({
                    'order_item_id': order_line.id_on_channel,
                    'quantity': values['qty_delivered']
                })
                components = values['qty_component_deliveried']
                for product_id, qty_delivered in components.items():
                    exported_items[product_id] = exported_items.get(product_id, 0) + qty_delivered
        return shipment_items, exported_items
        
        