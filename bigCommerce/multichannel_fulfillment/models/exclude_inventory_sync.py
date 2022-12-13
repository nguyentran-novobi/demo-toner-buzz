from odoo import api, fields, models, _

class ExcludeInventorySync(models.Model):
    _name = 'exclude.inventory.sync'
    _description = 'Exclude Inventory Sync'

    name = fields.Char(string='Name', compute='_compute_name')
    channel_id = fields.Many2one('ecommerce.channel', string='Channel', required=True, ondelete='cascade')
    applied_on = fields.Selection([('2_product_category', 'Product Category'),
                                   ('1_product', 'Product'),
                                   ('0_product_variant', 'Product Variant')], "Apply On",
                                  default='2_product_category', required=True,
                                  help='Exclude Inventory Sync applicable on selected option')
    categ_ids = fields.Many2many('product.category', string='Categories')
    product_tmpl_ids = fields.Many2many('product.template', string='Products')
    product_product_ids = fields.Many2many('product.product', string='Product Variants')

    @api.depends('applied_on', 'categ_ids', 'product_tmpl_ids', 'product_product_ids')
    def _compute_name(self):
        for record in self:
            if record.categ_ids and record.applied_on == '2_product_category':
                record.name = _("Categories: %s") % (', '.join(record.mapped('categ_ids.display_name')))
            elif record.product_tmpl_ids and record.applied_on == '1_product':
                record.name = _("Products: %s") % (', '.join(record.mapped('product_tmpl_ids.display_name')))
            elif record.product_product_ids and record.applied_on == '0_product_variant':
                record.name = _("Variants: %s") % (', '.join(record.product_product_ids._origin.with_context(display_default_code=False).mapped('display_name')))
            else:
                record.name = False

    def write(self, values):
        if values.get('applied_on', False):
            # Ensure item consistency for later searches.
            applied_on = values['applied_on']
            if applied_on == '2_product_category':
                values.update(dict(product_product_ids=[(5, 0, 0)], product_tmpl_ids=[(5, 0, 0)]))
            elif applied_on == '1_product':
                values.update(dict(product_product_ids=[(5, 0, 0)], categ_ids=[(5, 0, 0)]))
            elif applied_on == '0_product_variant':
                values.update(dict(categ_ids=[(5, 0, 0)], product_tmpl_ids=[(5, 0, 0)]))
        res = super().write(values)
        return res
