# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import re
import logging
from operator import attrgetter, or_

from odoo import api, fields, models, _
from odoo.addons.http_routing.models.ir_http import slugify
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MissingCategory(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class ProductChannelCategory(models.Model):
    _name = "product.channel.category"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Product Store Category"
    _order = 'id_on_channel'
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'display_name'
    
    display_name = fields.Char(string='Display Name', compute='_compute_display_name')
    name = fields.Char(string='Name', required=True)
    platform = fields.Selection(related='channel_id.platform')
    id_on_channel = fields.Char(string='ID on Store', required=False,  copy=False)
    parent_id = fields.Many2one('product.channel.category', string='Parent Category')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('product.channel.category', 'parent_id', string='Child Categories')
    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True)

    internal_category_id = fields.Many2one('product.category', string='Internal Category')
    need_to_export = fields.Boolean(string='Need to Export', readonly=True, copy=False)
    need_to_export_display = fields.Boolean(compute='_compute_need_to_export_display')
    is_exported_to_store = fields.Boolean(string='Exported to Store', compute='_compute_is_exported_to_store')
    image = fields.Image(string='Image')
    image_url = fields.Char(string="Image URL", compute="_compute_image_url")
    description = fields.Text(string='Description')
    sort_order = fields.Integer(string='Sort Order')
    url = fields.Char(string='URL')
    page_title = fields.Char(string='Page Title')
    search_keywords = fields.Char(string='Search Keywords')
    meta_keywords = fields.Char(string='Meta Keywords')
    meta_description = fields.Text(string='Meta Description')
    is_visible = fields.Boolean(string='Is Visible', default=True)

    _sql_constraints = [
        ('uniq_name', 'unique (id_on_channel,channel_id)',
         'This category already exists !')
    ]

    @api.depends('id_on_channel', 'need_to_export')
    def _compute_need_to_export_display(self):
        enabled = self.filtered(lambda r: r.is_exported_to_store and r.need_to_export)
        enabled.update({'need_to_export_display': True})
        (self - enabled).update({'need_to_export_display': False})

    @api.depends('id_on_channel')
    def _compute_is_exported_to_store(self):
        for record in self:
            record.is_exported_to_store = True if record.id_on_channel else False

    def _compute_image_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            record.image_url = "%s/web/image/%s/%s/image/%s.jpg" % (base_url, record._name, record.id, record.id)

    def channel_import_category(self, channel, ids=None):
        method = '{}_get_data'.format(channel.platform)
        if hasattr(self, method):
            getattr(self.with_delay(), method)(channel_id=channel.id,
                                               ids=ids or [])

    @api.depends('name', 'parent_id', 'parent_id.name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.parent_id.display_name} / {record.name}" if record.parent_id else record.name

    @api.model
    def create(self, vals):
        """
        Extending for creating category on channel
        :param vals_list:
        :return:
        """
        try:
            record = super(ProductChannelCategory, self).create(vals)
        except Exception:
            domain = [('name', '=', vals['name'])]
            if vals.get('channel_id', False):
                domain.extend([('channel_id', '=', vals['channel_id']),
                         ('id_on_channel', '=', vals['id_on_channel'])])
            record = self.search(domain, limit=1)

        return record

    def write(self, vals):
        """
        Extending for updating category on channel
        :param vals:
        :return:
        """
        if 'for_synching' not in self.env.context and 'need_to_export' not in vals:
            vals['need_to_export'] = True
        return super(ProductChannelCategory, self).write(vals)

    def _generate_url(self):
        self.ensure_one()

        def recursive(record):
            if not record:
                return '/'
            to_slugify = record.name or ''
            return recursive(record.parent_id) + f'{slugify(to_slugify)}/'

        return recursive(self)

    @api.constrains('url')
    def _check_url(self):
        pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
        for record in self.filtered(attrgetter('url')):
            adj_url = record.url
            adj_url = adj_url[1:] if adj_url.startswith('/') else adj_url
            adj_url = adj_url[:-1] if adj_url.endswith('/') else adj_url
            if not all(map(lambda s: re.match(pattern, s), adj_url.split('/'))):
                raise ValidationError(_('"%s" is an invalid Category URL', record.url))
        return True

    @api.onchange('name', 'parent_id')
    def _onchange_name(self):
        self.url = self._generate_url()

    def action_generate_url(self):
        self.ensure_one()
        self.url = self._generate_url()

    @api.model
    def channel_import_data(self, channel, ids, all_records):
        method = '{}_get_data'.format(channel.platform)
        if hasattr(self, method):
            getattr(self, method)(channel.id, ids=ids, all_records=all_records)

    @api.model
    def channel_export_data(self, ids=[]):
        ids = self.env.context.get('active_ids', []) or ids
        categories = self.env['product.channel.category'].browse(ids)
        channel = categories.mapped('channel_id')
        method = '{}_export_categories'.format(channel.platform)
        if hasattr(categories, method):
            getattr(categories, method)()

    def unlink(self):
        product_channels = self.env['product.channel'].search([('categ_ids.id', 'in', self.ids)])
        if product_channels:
            raise ValidationError(_("Cannot delete categories already linked to product mappings."))
        return super().unlink()
