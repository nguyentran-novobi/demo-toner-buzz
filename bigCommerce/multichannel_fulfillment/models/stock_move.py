# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from datetime import datetime
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
import logging
import psycopg2

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.model
    def _generate_product_domain_using_audit_table(self, product_product_ids, last_sync_inventory):
        if product_product_ids:
            product_domain = """
                        SELECT sqa.product_id
                        FROM stock_quant_audit AS sqa
                        WHERE sqa.product_id IN %s
                    """
            product_domain = self.env.cr._obj.mogrify(product_domain, (tuple(product_product_ids),))
        else:
            product_domain = """
                        SELECT sqa.product_id
                        FROM stock_quant_audit AS sqa
                    """
            product_domain = self.env.cr._obj.mogrify(product_domain, (last_sync_inventory,))

        encoding = psycopg2.extensions.encodings[self.env.cr.connection.encoding]

        return product_domain.decode(encoding, 'replace')

    @api.model
    def _generate_product_domain(self, product_product_ids, last_sync_inventory):
        if product_product_ids:
            product_domain = """
                SELECT DISTINCT move.product_id
                  FROM stock_move AS move
                    WHERE move.product_id IN %s
            """
            product_domain = self.env.cr._obj.mogrify(product_domain, (tuple(product_product_ids),))
        else:
            product_domain = """
                SELECT DISTINCT move.product_id
                FROM stock_move AS move
                WHERE move.write_date >= %s
            """
            product_domain = self.env.cr._obj.mogrify(product_domain, (last_sync_inventory,))

        encoding = psycopg2.extensions.encodings[self.env.cr.connection.encoding]

        return product_domain.decode(encoding, 'replace')

    @api.model
    def _remove_all_record_for_audit_table(self):
        query = "TRUNCATE TABLE stock_quant_audit"
        self.env.cr.execute(query)

    @api.model
    def _get_products_to_sync_inventory(self, product_product_ids, last_sync_inventory):
        query = """
                SELECT id
                FROM product_product
                WHERE id = ANY ({product_domain})
                """

        audit_stock_quant_table = self.env['ir.config_parameter'].sudo().get_param('audit.stock.quant.table')
        if audit_stock_quant_table != 'False':
            product_domain = self._generate_product_domain_using_audit_table(product_product_ids, last_sync_inventory)
        else:
            product_domain = self._generate_product_domain(product_product_ids, last_sync_inventory)

        query = query.format(product_domain=product_domain)
        self.env.cr.execute(query)

        product_ids = (x[0] for x in self.env.cr.fetchall())
        products = self.env['product.product'].browse(product_ids)

        if audit_stock_quant_table != 'False' and not self.env.context.get('run_manual', False):
            self._remove_all_record_for_audit_table()
        return products

    @api.model
    def _get_available_qty(self, product_product_ids, warehouse_ids, last_sync_inventory):
        products = self._get_products_to_sync_inventory(product_product_ids, last_sync_inventory)
        data = {}
        for warehouse_id in warehouse_ids:
            res = products.with_context(warehouse=[warehouse_id])._compute_quantities_dict(self._context.get('lot_id'), self._context.get('owner_id'), self._context.get('package_id'), self._context.get('from_date'), self._context.get('to_date'))
            for product_id in res:
                free_qty = res[product_id]['free_qty']
                data.setdefault(product_id, {})[warehouse_id] = free_qty if free_qty > 0 else 0
        return data

    @api.model
    def inventory_sync(self, channel_id=None, all_records=False, nightly_update=False, product_product_ids=None):

        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        IrConfigParameter = self.env['ir.config_parameter'].sudo()
        last_sync_inventory = IrConfigParameter.get_param('ob.last_sync_inventory') or IrConfigParameter.get_param('database.create_date')

        if all_records or product_product_ids:
            last_sync_inventory = IrConfigParameter.get_param('database.create_date')

        IrConfigParameter.set_param('ob.last_sync_inventory', now)

        #
        # Only get quants on active warehouses of channel
        #
        if not channel_id:
            active_channels = self.env['ecommerce.channel'].sudo().search([('active', '=', True),
                                                                           ('is_enable_inventory_sync', '=', True),
                                                                           ('active_warehouse_ids', '!=', False)])

        else:
            active_channels = self.env['ecommerce.channel'].sudo().browse(channel_id)

        run_manual = True if all_records else False
        products = self.with_context(run_manual=run_manual)._get_products_to_sync_inventory(product_product_ids, last_sync_inventory)
        if products or all_records:
            context = self.env.context
            for channel in active_channels:
                channel.with_context(**context).update_inventory(exported_products=products, bulk_sync=all_records)
            if nightly_update:
                active_channels.sudo().write({'last_all_inventory_sync': now, 'warning_message': False})
        else:
            active_channels.sudo().write({'warning_message': False})

    def _get_new_picking_values(self):
        vals = super(StockMove, self)._get_new_picking_values()
        group = self.mapped('group_id')
        if group and group[0].sale_id:
            order = group[0].sale_id
            vals['requested_carrier'] = order.requested_shipping_method
        return vals
