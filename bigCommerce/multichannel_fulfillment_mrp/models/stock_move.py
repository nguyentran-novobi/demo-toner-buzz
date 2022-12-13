import logging
from odoo import api, models, _

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    @api.model
    def _get_products_to_sync_inventory(self, product_product_ids, last_sync_inventory):
        """
        Extend this function to get kits to do inventory sync
        """
        products = super()._get_products_to_sync_inventory(product_product_ids, last_sync_inventory)
        if not products:
            return products
        _query = """
            WITH RECURSIVE kit_table AS (
                SELECT pp.id AS pp_id FROM mrp_bom_line AS mbl
                INNER JOIN mrp_bom AS mb ON mb.id = mbl.bom_id
                INNER JOIN product_product AS pp ON pp.product_tmpl_id = mb.product_tmpl_id
                WHERE mbl.product_id IN %s AND mb.type = 'phantom'
                UNION (
                    SELECT pp.id AS pp_id FROM mrp_bom_line AS mbl
                    INNER JOIN mrp_bom AS mb ON mb.id = mbl.bom_id
                    INNER JOIN product_product AS pp ON pp.product_tmpl_id = mb.product_tmpl_id
                    INNER JOIN kit_table ON kit_table.pp_id = mbl.product_id
                    WHERE mb.type = 'phantom'
                )
            )
            SELECT * FROM kit_table
        """
        self.env.cr.execute(_query, (tuple(products.ids),))
        product_ids = list(set([x[0] for x in self.env.cr.fetchall()] + products.ids))
        return self.env['product.product'].browse(product_ids)
