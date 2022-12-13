# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from itertools import groupby
from odoo import models, api, fields

class ProductChannelVariant(models.Model):
    _inherit = 'product.channel.variant'

    free_qty = fields.Float(string='Available', compute='_compute_free_qty')

    @api.model
    def _get_available_qty(self, products, active_warehouse_ids):
        res = products.with_context(warehouse=active_warehouse_ids)._compute_quantities_dict(self._context.get('lot_id'), self._context.get('owner_id'), self._context.get('package_id'), self._context.get('from_date'), self._context.get('to_date'))
        if 'channel' in self.env.context:
            caq = self.env.context['channel']._compute_available_qty
            for product_id in res:
                res[product_id]['free_qty'] = caq(res[product_id]['free_qty'])
        return res

    def _compute_free_qty(self):
        data = {}
        context = self.env.context.copy()
        for channel, records in groupby(self.sorted(key=lambda r: r.channel_id.id), key=lambda r: r.channel_id):
            if channel:
                active_warehouse_ids = channel._get_syncing_warehouses().ids
                products = self.env['product.product'].browse(list(filter(bool, (record.product_product_id.id for record in records))))
                res = self.with_context(dict(context, channel=channel))._get_available_qty(products, active_warehouse_ids)
                data.update({product_id: res[product_id]['free_qty'] if res[product_id]['free_qty'] > 0 else 0 for product_id in res})

        for record in self:
            caq = record.channel_id._compute_available_qty
            record.free_qty = data.get(record.product_product_id.id, caq(0.0))
