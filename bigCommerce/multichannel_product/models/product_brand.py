# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, tools, _

_logger = logging.getLogger(__name__)


class BrandChannel(models.Model):
    _name = 'brand.channel'
    _description = 'Brand Channel'

    name = fields.Char(string='Name', related='brand_id.name', readonly=False)
    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True, ondelete='cascade')
    id_on_channel = fields.Char(string='ID on Store', copy=False)
    brand_id = fields.Many2one('product.brand', string='Brand', ondelete='cascade')

    _sql_constraints = [
        ('id_on_channel_uniq', 'unique(id_on_channel, channel_id)', 'Reference must be unique per Channel!'),
    ]

    def _post_brand_to_channel(self):
        for record in self:
            cust_method_name = '%s_post_record' % record.channel_id.platform
            if hasattr(self, cust_method_name):
                getattr(record, cust_method_name)()

    def _put_brand_to_channel(self):
        for record in self:
            cust_method_name = '%s_put_record' % record.channel_id.platform
            if hasattr(self, cust_method_name):
                getattr(record, cust_method_name)()

    def _delete_brand_to_channel(self):
        for record in self:
            cust_method_name = '%s_delete_record' % record.channel_id.platform
            if hasattr(self, cust_method_name):
                getattr(record, cust_method_name)()

    @api.model
    def create(self, vals):
        """
        Extending for creating brand on channel
        :param vals:
        :return:
        """
        try:
            # Search and create brand_id
            if vals.get('name') and 'brand_id' not in vals:
                ProductBrand = self.env['product.brand'].sudo()
                brand_id = ProductBrand.search([('name', '=', vals['name'])], limit=1)
                if not brand_id:
                    brand_id = ProductBrand.create({'name': vals['name']})
                vals['brand_id'] = brand_id.id

            record = super(BrandChannel, self).create(vals)
            if 'for_synching' not in self.env.context:
                record._post_brand_to_channel()
        except Exception as e:
            _logger.exception(str(e))
            self.env.cr.rollback()
            return self.sudo().search([('name', '=', vals['name'])], limit=1)
        return record

    def write(self, vals):
        """
        Extending for updating brand on channel
        :param vals:
        :return:
        """
        res = super(BrandChannel, self).write(vals)
        if 'for_synching' not in self.env.context:
            self._put_brand_to_channel()
        return res

    def unlink(self):
        self._delete_brand_to_channel()
        return super(BrandChannel, self).unlink()


class ProductBrand(models.Model):
    _name = 'product.brand'
    _description = "Product Brands from channel"

    name = fields.Char(string='Brand Name', required=True)
    line_ids = fields.One2many('brand.channel', 'brand_id')
    image = fields.Binary(
        "Image", attachment=True,
        help="This field holds the image used as image for the product, limited to 1024x1024px.")
    image_medium = fields.Binary(
        "Medium-sized image", attachment=True,
        help="Medium-sized image of the product. It is automatically "
             "resized as a 128x128px image, with aspect ratio preserved, "
             "only when the image exceeds one of those sizes. Use this field in form views or some kanban views.")
    image_small = fields.Binary(
        "Small-sized image", attachment=True,
        help="Small-sized image of the product. It is automatically "
             "resized as a 64x64px image, with aspect ratio preserved. "
             "Use this field anywhere a small image is required.")

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Name is unique'),
    ]

    @api.model
    def create(self, vals):
        """
        Extending for creating brand on channel
        :param vals_list:
        :return:
        """
        try:
            return super(ProductBrand, self).create(vals)
        except Exception as e:
            _logger.exception(str(e))
            self.env.cr.rollback()
            return self.sudo().search([('name', '=', vals['name'])], limit=1)

    def get_brand_channel(self, channel_id):
        self.ensure_one()
        brand = self.line_ids.filtered(lambda l: l.channel_id.id == channel_id)
        if not brand:
            brand = self.env['brand.channel'].sudo().create({
                'channel_id': channel_id,
                'brand_id': self.id,
            })
            self.env.cr.commit()
        return brand

    @api.model
    def get_brand_by_name(self, name):
        if name != '':
            brand = self.sudo().search([('name', '=', name)], limit=1)
            if not brand:
                brand = self.sudo().create({'name': name})
                self.env.cr.commit()
            return brand
        return self


