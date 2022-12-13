# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ProductProductMergeInfo(models.Model):
    _name = "product.product.merge.info"
    _description = "Product Product Merge Info"
    _rec_name = 'product_channel_variant_id'

    product_product_id = fields.Many2one('product.product', string='Product Template', index=True, required=False)
    product_channel_variant_id = fields.Many2one('product.channel.variant', string='Channel',
                                                 index=True, required=False, ondelete='cascade')
    product_template_merge_info_id = fields.Many2one('product.template.merge.info', ondelete='cascade')
    data = fields.Text()

    _sql_constraints = [
        ('_unique', 'unique (product_product_id, product_channel_variant_id)', "Unique for channel"),
    ]


class ProductMergeInfo(models.Model):
    _name = "product.template.merge.info"
    _description = "Product Template Merge Info"
    _rec_name = 'channel_id'

    product_tmpl_id = fields.Many2one('product.template', string='Product Template', index=True,
                                      required=True, ondelete='cascade')
    product_channel_id = fields.Many2one('product.channel', string='Product Mapping', index=True,
                                         required=True, ondelete='cascade')
    channel_id = fields.Many2one('ecommerce.channel', related='product_channel_id.channel_id')
    data = fields.Text()
    product_variant_merge_info_ids = fields.One2many('product.product.merge.info', 'product_template_merge_info_id')

    _sql_constraints = [
        ('_unique', 'unique (product_channel_id, product_tmpl_id)', "Unique for channel"),
    ]
