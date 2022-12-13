# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

class ProductExportedField(models.Model):
    _name = 'product.exported.field'
    _description = 'Product Exported Fields'

    platform = fields.Selection([('none', 'None')], default='none', required=True)
    level = fields.Selection([('master_template', 'Master Template'),
                              ('master_variant', 'Master Variant'),
                              ('mapping_template', 'Mapping Template'),
                              ('mapping_variant', 'Mapping Variant')], string='Level',
                             compute='_compute_level', store=True)
    virtual_level = fields.Selection([('master_template', 'Master Template'),
                                      ('master_variant', 'Master Variant'),
                                      ('mapping_template', 'Mapping Template'),
                                      ('mapping_variant', 'Mapping Variant')], string='Virtual Level')
    name = fields.Char(string='Name', compute='_get_title')
    api_ref = fields.Char(string='Field Name in API Request', required=True)
    odoo_field_id = fields.Many2one('ir.model.fields', string='Odoo Field', ondelete='cascade')
    mapping_field_name = fields.Char(string='Mapping Field Name')
    store_field_name = fields.Char(string='Store Field Name')
    is_fixed = fields.Boolean(string='Fixed Field')
    related_template_field_id = fields.Many2one('product.exported.field')

    @api.depends('odoo_field_id', 'virtual_level')
    def _compute_level(self):
        for record in self:
            level = ''
            model = record.odoo_field_id.model_id.model
            if model == 'product.template':
                level = 'master_template'
            elif model == 'product.product':
                level = 'master_variant'
            elif model == 'product.channel':
                level = 'mapping_template'
            elif model == 'product.channel.variant':
                level = 'mapping_variant'
            record.level = level or record.virtual_level

    def _get_title(self):
        for record in self:
            name = ''
            if record.level and 'master' in record.level:
                odoo_field_name = record.odoo_field_id.field_description if record.store_field_name != 'Weight' else 'Weight'
                name = f'{odoo_field_name} → {record.store_field_name}'
            else:
                name = f'{record.store_field_name}'
            record.name = name

    def get_api_refs(self):
        api_refs = self.mapped('api_ref')
        if 'dimensions' in api_refs:
            api_refs.extend(['width', 'length', 'depth', 'height'])
        return api_refs

    def get_merged_fields(self):
        mapping2master = []
        for record in self:
            if record.mapping_field_name == 'dimensions':
                dimensions_mapping = ('width', 'depth', 'height')
                dimensions_template = ('width', 'depth', 'height')
                mapping2master.extend(list(zip(dimensions_mapping, dimensions_template)))
            elif record.mapping_field_name:
                mapping2master.append((record.mapping_field_name, record.odoo_field_id.name))
        return mapping2master
