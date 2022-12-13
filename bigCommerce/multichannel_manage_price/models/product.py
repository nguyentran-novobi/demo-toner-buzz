from odoo import fields, models, api, _


class Product(models.Model):
    _inherit = 'product.product'

    @api.depends('list_price', 'price_extra')
    @api.depends_context('uom')
    def _compute_product_lst_price(self):
        for product in self:
            product.lst_price = product.variant_price

    def _set_product_lst_price(self):
        for product in self:
            product.variant_price = product.lst_price
