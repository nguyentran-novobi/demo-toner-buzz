# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductChannelImage(models.Model):
    _name = 'product.channel.image'
    _description = 'Product Channel Image'
    _order = 'sequence asc'

    name = fields.Char(string='Name')
    file_name = fields.Char(string="File Name", default="image.png")
    image = fields.Binary(string='Image', attachment=True, required=True)
    image_url = fields.Char(string="Image URL", compute="_compute_image_url")
    image_description = fields.Char(string="Description")
    is_thumbnail = fields.Boolean(string="Is Thumbnail?")

    id_on_channel = fields.Char(string='Product Channel Image ID', copy=False, help='ID of product image on Channel')
    channel_id = fields.Many2one('ecommerce.channel', related='product_channel_id.channel_id', string='Store')

    product_tmpl_id = fields.Many2one('product.template', string='Related Product', copy=True, ondelete='cascade')
    product_channel_id = fields.Many2one('product.channel',
                                         string='Related Mapping', copy=True, ondelete='cascade')

    product_channel_variant_ids = fields.Many2many('product.channel.variant')

    sequence = fields.Integer(string='Sequence')

    @api.constrains('is_thumbnail')
    def _check_invalid_multiple_thumbnail(self):
        if 'for_synching' not in self.env.context:
            for record in self:
                if self.search_count([('product_tmpl_id', '!=', False), ('product_tmpl_id', '=', record.product_tmpl_id.id), ('is_thumbnail', '=', True)]) > 1:
                    raise ValidationError(_('Please make sure that you choose only one image as the product thumbnail.'))
        return True

    def _compute_image_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            record.image_url = "%s/web/image/%s/%s/image/%s.jpg" % (base_url, record._name, record.id, record.id)

    @api.model
    def get_product_images(self, images, channel):
        cust_method_name = '%s_get_product_images' % channel.platform
        if hasattr(self, cust_method_name):
            return getattr(self, cust_method_name)(images, channel.id)

    def unlink(self):
        self.filtered(lambda s: s.product_tmpl_id).mapped('product_tmpl_id').update({'has_change_image': True})
        self -= self.filtered(lambda r: r.product_channel_variant_ids)
        return super(ProductChannelImage, self).unlink()
    
    @api.model
    def create(self, vals):
        if 'product_channel_id' in vals and 'product_tmpl_id' not in vals:
            vals['product_tmpl_id'] = False
        res = super().create(vals)
        if res.product_tmpl_id:
            res.product_tmpl_id.update({'has_change_image': True})
        return res

    def write(self, vals):
        res = super().write(vals)
        self.filtered(lambda s: s.product_tmpl_id).mapped('product_tmpl_id').update({'has_change_image': True})
        return res
