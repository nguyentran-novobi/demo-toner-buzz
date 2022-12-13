from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AlternateSKU(models.Model):
    _name = 'product.alternate.sku'
    _description = 'Product Alternate SKU'
    _order = 'sequence, id'

    name = fields.Char(string='Alternate SKU', required=True)
    sequence = fields.Integer(default=10)
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        inverse='_inverse_product_template',
    )
    product_product_id = fields.Many2one(
        'product.product',
        string='Product Variant',
        inverse='_inverse_product_product',
    )
    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True)
    product_channel_variant_id = fields.Many2one('product.channel.variant', string='Product Mapping', readonly=True)

    @api.constrains('name', 'channel_id')
    def _check_alternate_sku(self):
        for record in self:
            if self.search_count([('name', '=', record.name), ('channel_id', '=', record.channel_id.id)]) > 1:
                raise ValidationError(_("SKU %s on %s has existed on the system." % (record.name, record.channel_id.name)))

    def _inverse_product_template(self):
        records = self.filtered(lambda r: r.product_tmpl_id)
        for record in records:
            variants = record.product_tmpl_id.product_variant_ids
            if len(variants) == 1:
                record.product_product_id = variants[:1]

    def _inverse_product_product(self):
        records = self.filtered(lambda r: r.product_product_id)
        for record in records:
            record.product_tmpl_id = record.product_product_id.product_tmpl_id

    def write(self, vals):
        if 'name' in vals:
            self.mapped('product_channel_variant_id').unlink()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_alternate_sku(self):
        self.mapped('product_channel_variant_id').unlink()
