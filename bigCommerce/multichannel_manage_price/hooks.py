from odoo.api import Environment, SUPERUSER_ID


def pre_init_hook(cr):
    env = Environment(cr, SUPERUSER_ID, {})
    products = env['product.product'].search([])
    for product in products:
        product.update({
            'variant_price': product.lst_price
        })
