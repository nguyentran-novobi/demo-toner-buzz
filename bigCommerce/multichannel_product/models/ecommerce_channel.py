# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, _

from ..utils.unit_converter import UnitConverter


_logger = logging.getLogger(__name__)


def force_float(value):
    try:
        return float(value)
    except TypeError:
        return 0


class EcommerceChannel(models.Model):
    _inherit = "ecommerce.channel"

    master_template_exported_field_ids = fields.Many2many('product.exported.field',
                                                          'mt_ex_field',
                                                          'mt_id',
                                                          'mt_channel_id',
                                                          string='Master Template Exported Fields')

    default_master_template_exported_field_ids = fields.Many2many('product.exported.field',
                                                                  'default_mt_ex_field',
                                                                  'mt_id',
                                                                  'mt_channel_id',
                                                                  string='Default Master Template Exported Fields')

    master_variant_exported_field_ids = fields.Many2many('product.exported.field',
                                                         'mv_ex_field',
                                                         'mv_id',
                                                         'mv_channel_id',
                                                         compute='_compute_master_variant_exported_fields',
                                                         string='Master Variant Exported Fields',
                                                         store=True)

    default_master_variant_exported_field_ids = fields.Many2many('product.exported.field',
                                                                 'default_mv_default_ex_field',
                                                                 'mv_id',
                                                                 'mv_channel_id',
                                                                 string='Default Master Variant Exported Fields')

    mapping_template_exported_field_ids = fields.Many2many('product.exported.field',
                                                           'mpt_ex_field',
                                                           'mpt_id',
                                                           'mpt_channel_id',
                                                           string='Mapping Template Exported Fields')

    auto_override_imported_field_ids = fields.Many2many('product.imported.field',
                                                        'mpt_im_field',
                                                        'mpt_id',
                                                        'mpt_channel_id',
                                                        string='Product Fields are Overridden')

    default_mapping_template_exported_field_ids = fields.Many2many('product.exported.field',
                                                                   'default_mpt_ex_field',
                                                                   'mpt_id',
                                                                   'mpt_channel_id',
                                                                   string='Mapping Template Exported Fields')

    mapping_variant_exported_field_ids = fields.Many2many('product.exported.field',
                                                          'mpvt_ex_field',
                                                          'mpvt_id',
                                                          'mpvt_channel_id',
                                                          compute='_compute_mapping_variant_exported_fields',
                                                          string='Mapping Variant Exported Fields',
                                                          store=True)

    default_mapping_variant_exported_field_ids = fields.Many2many('product.exported.field',
                                                                  'default_mpvt_ex_field',
                                                                  'mpvt_id',
                                                                  'mpvt_channel_id',
                                                                  string='Mapping Variant Exported Fields')

    manage_images = fields.Boolean(string='Auto download images when importing product',
                                   compute='_compute_manage_image', store=True)

    auto_create_master_product = fields.Boolean(string='Auto Create Product if Not Found', default=True)

    default_categ_id = fields.Many2one('product.channel.category', string='Default Category')

    can_export_product = fields.Boolean(string='Enable Export Product', default=True)
    can_export_product_from_master = fields.Boolean(string='Enable Export from Product', default=True)
    can_export_product_from_mapping = fields.Boolean(string='Enable Export from Mapping', default=True)
    can_export_pricelist_from_master = fields.Boolean(string='Enable Export from Pricelist', default=False)
    auto_override_product = fields.Boolean(string='Auto Override Product Info after Importing')
    is_mapping_managed = fields.Boolean(string='Is Mapping Managed', default=True)
    auto_create_master_product_help_text = fields.Char(compute='_compute_auto_create_master_help_text')
    master_exported_field_help_text = fields.Text(compute='_compute_master_exported_field_help_text')

    def _compute_auto_create_master_help_text(self):
        for record in self:
            record.auto_create_master_product_help_text = """Automatically create a new product
                                        if system couldn't find the product based on SKU"""

    def _compute_master_exported_field_help_text(self):
        for record in self:
            record.master_exported_field_help_text = """Fields exported by default: SKU, Name, Variants"""

    @api.depends('master_template_exported_field_ids')
    def _compute_manage_image(self):
        image_master_field = self.env.ref('multichannel_product.field_product_template__product_channel_image_ids')
        for record in self:
            record.manage_images = True if record.master_template_exported_field_ids.filtered(lambda f: f.odoo_field_id.id == image_master_field.id) else False

    @api.depends('master_template_exported_field_ids')
    def _compute_master_variant_exported_fields(self):
        fixed_exported_fields = self.env['product.exported.field'].sudo().search([('level', '=', 'master_variant'),
                                                                                  ('is_fixed', '=', True)])
        for record in self:
            fields = fixed_exported_fields.filtered(lambda f: f.platform == record.platform)
            fields += self.env['product.exported.field'].sudo().search([('related_template_field_id', 'in', record.master_template_exported_field_ids.ids)])
            if fields:
                record.master_variant_exported_field_ids = [(6, 0, fields.ids)]
            else:
                record.master_variant_exported_field_ids = [(5, 0, 0)]

    @api.depends('mapping_template_exported_field_ids')
    def _compute_mapping_variant_exported_fields(self):
        fixed_exported_fields = self.env['product.exported.field'].sudo().search([('level', '=', 'mapping_variant'),
                                                                                  ('is_fixed', '=', True)])
        for record in self:
            fields = fixed_exported_fields.filtered(lambda f: f.platform == record.platform)
            fields += self.env['product.exported.field'].sudo().search([('related_template_field_id', 'in', record.mapping_template_exported_field_ids.ids)])
            if fields:
                record.mapping_variant_exported_field_ids = [(6, 0, fields.ids)]
            else:
                record.mapping_variant_exported_field_ids = [(5, 0, 0)]

    def _convert_channel_weight(self, weight, unit=None, inverse=False):
        """
        Convert weight value from the provided `unit` to channel unit.
        If `unit` is not provided, unit in Odoo settings will be used.
        If `inverse` flag is True, value will be converted from channel unit to `unit`.
        :param float weight: The weight to be converted
        :param str unit: Unit of value, will be unit of result if `inverse` is True.
        :param bool inverse: False if convert from Odoo to Channel, True otherwise
        :return: The converted weight
        :rtype: float
        """

        self.ensure_one()
        weight = force_float(weight)
        setting_unit = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()

        kw = dict(from_unit=unit or setting_unit, to_unit=self.weight_unit)
        if inverse:
            kw['from_unit'], kw['to_unit'] = kw['to_unit'], kw['from_unit']

        return UnitConverter(self).convert_weight(weight, **kw)

    def _convert_channel_dimension(self, value, unit=None, inverse=False):
        """
        Convert dimension value from the provided `unit` to channel unit.
        If `unit` is not provided, unit in Odoo settings will be used.
        If `inverse` flag is True, value will be converted from channel unit to `unit`.
        :param float value: The value to be converted
        :param str unit: Unit of value, will be unit of result if `inverse` is True.
        :param bool inverse: False if convert from Odoo to Channel, True otherwise
        :return: The converted value
        :rtype: float
        """

        self.ensure_one()
        value = force_float(value)
        setting_unit = self.env['product.template']._get_length_uom_id_from_ir_config_parameter()

        kw = dict(from_unit=unit or setting_unit, to_unit=self.dimension_unit)
        if inverse:
            kw['from_unit'], kw['to_unit'] = kw['to_unit'], kw['from_unit']

        return UnitConverter(self).convert_length(value, **kw)

    def open_product_channel_categories(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('multichannel_product.action_channel_category')
        action.update({
            'context': {'include_platform': True, 'default_channel_id': self.id},
            'domain': [('channel_id.id', '=', self.id)],
            'target': 'main',
            'display_name': '%s - Categories' % ("[%s] %s" % (self.platform.upper(), self.name))
        })
        return action

    def open_product_brands(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('multichannel_product.action_channel_brand_name')
        action.update({
            'context': {'include_platform': True},
            'target': 'main',
            'display_name': '%s - Brands' % ("[%s] %s" % (self.platform.upper(), self.name))
        })
        return action

    def open_import_product(self):
        self.ensure_one()
        self.ensure_operating()

        field_names = []

        last_option_sync_product = None
        if self.is_in_syncing:
            last_option_sync_product = self.last_option_sync_product

        return {
            'type': 'ir.actions.client',
            'tag': 'action.import_product_channel',
            'target': 'main',
            'context': {
                'channel_platform': self.platform,
                'channel_name': self.name,
                'channel_id': self.id,
                'last_option_sync_product': last_option_sync_product,
                'last_sync_product': fields.Datetime.to_string(self.last_sync_product) if self.last_sync_product else '',
                'auto_create_master': self.get_setting('auto_create_master_product'),
                'is_in_syncing': self.is_in_syncing,
                'options': ['last_sync', 'visible_products', 'all_products'],
                'fields': field_names,
            }
        }

    def action_import_product_manually(self):
        self.ensure_one()
        self.ensure_operating()
        return {
            'name': _('Import Products'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'import.resource.operation',
            'target': 'new',
            'context': {'default_channel_id': self.id, 'active_test': True}
        }

    def open_import_other_data(self):
        self.ensure_one()
        self.ensure_operating()
        return {
            'name': _("Import Other Data"),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'import.other.data',
            'target': 'new',
            'context': {'default_channel_id': self.id, 'active_test': True}
        }

    # Log Management
    def open_log_import_product(self):
        action = self._get_base_log_action()
        action.update({
            'domain': [('channel_id.id', '=', self.id), ('operation_type', '=', 'import_product')],
            'display_name': f'{self.name} - Logs - Product Import',
            'views': [
                (self.env.ref('omni_log.product_import_log_view_tree').id, 'list'),
                (self.env.ref('omni_log.product_import_log_view_form').id, 'form')
            ]
        })
        return action

    def open_log_import_other_data(self):
        action = self._get_base_log_action()
        action.update({
            'domain': [('channel_id.id', '=', self.id), ('operation_type', '=', 'import_others')],
            'display_name': f'{self.name} - Logs - Other Data Import',
            'views': [
                (self.env.ref('omni_log.other_import_log_view_tree').id, 'list'),
                (self.env.ref('omni_log.other_import_log_view_form').id, 'form')
            ]
        })
        return action

    def open_log_export_product(self):
        action = self._get_base_log_action()
        action.update({
            'domain': [('channel_id.id', '=', self.id), ('operation_type', 'in', ['export_master', 'export_mapping'])],
            'display_name': f'{self.name} - Logs - Product Export',
            'views': [
                (self.env.ref('omni_log.export_product_log_view_tree').id, 'list'),
                (self.env.ref('omni_log.export_product_log_view_form').id, 'form')
            ]
        })
        return action

    def open_log_export_other_data(self):
        action = self._get_base_log_action()
        action.update({
            'domain': [('channel_id.id', '=', self.id), ('operation_type', '=', 'export_others')],
            'display_name': f'{self.name} - Logs - Other Data Export',
            'views': [
                (self.env.ref('omni_log.other_export_log_view_tree').id, 'list'),
                (self.env.ref('omni_log.other_export_log_view_form').id, 'form')
            ]
        })
        return action

    def get_listing_form_view_action(self, res_id):
        self.ensure_one()
        platform = self.platform
        method_name = f'{platform}_get_listing_form_view_action'
        if hasattr(self, method_name):
            return getattr(self, method_name)(res_id)
        return {}

    def get_auto_overridden_fields(self):
        self.ensure_one()
        return self.auto_override_imported_field_ids.get_odoo_fields() + self._get_default_overridden_fields()

    @api.model
    def _get_default_overridden_fields(self):
        return ['type']
    
    def _get_product_exported_fields(self):
        return {
            'master_template': (self.master_template_exported_field_ids + self.default_master_template_exported_field_ids).get_api_refs(),
            'master_variant': (self.master_variant_exported_field_ids + self.default_master_variant_exported_field_ids).get_api_refs(),
            'mapping_template': (self.mapping_template_exported_field_ids + self.default_mapping_template_exported_field_ids).get_api_refs(),
            'mapping_variant': (self.mapping_variant_exported_field_ids + self.default_mapping_variant_exported_field_ids).get_api_refs()
        }

    def _get_product_merged_fields(self):
        return {
            'template': (self.master_template_exported_field_ids + self.default_master_template_exported_field_ids).get_merged_fields(),
            'variant': (self.master_variant_exported_field_ids + self.default_master_variant_exported_field_ids).get_merged_fields(),
        }

    @api.model
    def prepare_product_imported_fields(self, platform):
        imported_fields = self.env['product.imported.field'].sudo().search([('platform', '=', platform)])
        return {
            'auto_override_imported_field_ids': [(6, 0, imported_fields.filtered(lambda f: f.level == 'master_template').ids)]
        }

    @api.model
    def prepare_product_exported_fields(self, platform):
        exported_fields = self.env['product.exported.field'].sudo().search([('platform', '=', platform)])
        return {
            'master_template_exported_field_ids': [(6, 0, exported_fields.filtered(lambda f: f.level == 'master_template' and not f.is_fixed).ids)],
            'master_variant_exported_field_ids': [(6, 0, exported_fields.filtered(lambda f: f.level == 'master_variant' and not f.is_fixed).ids)],
            'mapping_template_exported_field_ids': [(6, 0, exported_fields.filtered(lambda f: f.level == 'mapping_template' and not f.is_fixed).ids)],
            'mapping_variant_exported_field_ids': [(6, 0, exported_fields.filtered(lambda f: f.level == 'mapping_variant' and not f.is_fixed).ids)],
            'default_master_template_exported_field_ids': [(6, 0, exported_fields.filtered(lambda f: f.level == 'master_template' and f.is_fixed).ids)],
            'default_master_variant_exported_field_ids': [(6, 0, exported_fields.filtered(lambda f: f.level == 'master_variant' and f.is_fixed).ids)],
            'default_mapping_template_exported_field_ids': [(6, 0, exported_fields.filtered(lambda f: f.level == 'mapping_template' and f.is_fixed).ids)],
            'default_mapping_variant_exported_field_ids': [(6, 0, exported_fields.filtered(lambda f: f.level == 'mapping_variant' and f.is_fixed).ids)]
        }

    def get_action_product_mapping_menu(self, res_model, view_ids):
        self.ensure_one()
        return {
            'name': f'{self.name} - Product Mappings',
            'type': 'ir.actions.act_window',
            'domain': [('channel_id.id', '=', self.id), ('state', '!=', 'draft')],
            'context': {
                'action_publishing_channel': True,
                'include_platform': True,
                'custom_import': True,
                'default_platform': self.platform,
                'default_channel_id': self.id
            },
            'res_model': res_model,
            'view_ids': view_ids
        }

    def create_product_mapping_menu(self, **kwargs):
        self.ensure_one()
        res_model = kwargs.get('res_model', 'product.channel')
        action_view_id = kwargs.get('action_view_id',
                                    self.env.ref('multichannel_product.view_product_channel_tree').id)
        if self.platform:
            view_ids = [(5, 0, 0), (0, 0, {'view_mode': 'tree', 'view_id': action_view_id})]

            cust_method_name = '%s_get_mapping_views' % self.platform
            if hasattr(self, cust_method_name):
                parent, view_ids = getattr(self, cust_method_name)()
            else:
                parent = self.env.ref('omni_manage_channel.menu_listings_root')

            parent.sudo().write({'active': True})

            action_values = self.get_action_product_mapping_menu(res_model, view_ids)

            action = self.env['ir.actions.act_window'].sudo().create(action_values)

            self.env['ir.model.data'].sudo().create({
                'name': 'action_{channel_id}'.format(channel_id=self.id),
                'module': 'multichannel_product',
                'model': action._name,
                'noupdate': True,
                'res_id': action.id,
            })
            values = {
                'parent_id': parent.id,
                'name': self.name,
                'sequence': 2,
                'action': 'ir.actions.act_window,%s' % str(action.id),
                'active': True if self.is_mapping_managed else False
            }
            menu = self.env['ir.ui.menu'].sudo().create(values)
            self.env['ir.model.data'].sudo().create({
                'name': 'menu_{channel_id}'.format(channel_id=self.id),
                'module': 'multichannel_product',
                'model': menu._name,
                'noupdate': True,
                'res_id': menu.id,
            })
            self.with_context(for_channel_creation=True).sudo().write({'menu_listing_id': menu.id})

    def write(self, vals):
        res = super(EcommerceChannel, self).write(vals)
        if 'is_mapping_managed' in vals:
            if vals['is_mapping_managed']:
                menu_listings = self.mapped('menu_listing_id')
                menu_listings.sudo().write({'active': False})
            else:
                menu_listings = self.filtered(lambda r: r.active).mapped('menu_listing_id')
                if menu_listings:
                    menu_listings.sudo().write({'active': True})
        return res

    @api.model
    def create(self, vals):
        vals.update({
            **self.prepare_product_exported_fields(vals['platform']), 
            **self.prepare_product_imported_fields(vals['platform'])
        })
        record = super().create(vals)
        record.create_product_mapping_menu()
        return record
