# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class ProductChannelComposer(models.TransientModel):
    _name = 'product.channel.composer'
    _description = 'For publishing to channel'

    product_tmpl_id = fields.Many2one('product.template', string='Product', required=True)
    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True)

    def publish(self):
        default_attribute_line_ids = []
        for line in self.product_tmpl_id.attribute_line_ids:
            default_attribute_line_ids.append((0, 0, {
                'attribute_id': line.attribute_id.id,
                'value_ids': [(6, 0, line.value_ids.ids)],
            }))

        context = {
            'default_name': self.product_tmpl_id.name,
            'default_product_tmpl_id': self.product_tmpl_id.id,
            'default_channel_id': self.channel_id.id,
            'default_sku': self.product_tmpl_id.default_code,
            'default_list_price': self.product_tmpl_id.list_price,
            'default_weight_in_oz': self.product_tmpl_id.weight_in_oz,
            'default_attribute_line_ids': default_attribute_line_ids if default_attribute_line_ids else False,
            # BigCommerce
            'default_type': 'physical' if self.product_tmpl_id.type in ['product', 'consu'] else 'digital',
        }

        return {
            'name': _('Product Channel'),
            'res_model': 'product.channel',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('multichannel_product.view_product_channel_form').id,
            'target': 'current',
            'context': context
        }