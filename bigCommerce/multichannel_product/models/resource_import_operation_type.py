from odoo import fields, models


class ResourceImportOperationType(models.Model):
    _name = 'resource.import.operation.type'
    _description = 'Resource Importing Operation Type'
    _order = 'sequence asc, platform'

    name = fields.Char('Label', help='The label to display to users')
    sequence = fields.Integer(default=15)
    platform = fields.Selection([])
    resource = fields.Selection([('product', 'Product')])
    code = fields.Char(help='The codename of this type for technical comparison')
    type = fields.Selection([
        ('from_last_sync', 'From last sync'),
        ('visible_or_active', 'Visible on Storefront'),
        ('all', 'All'),
        ('time_range', 'Time Range'),
        ('ids', 'IDs'),
        ('sku', 'SKUs'),
    ], help='The group of this type. Used for technical comparison')
    is_update_last_sync = fields.Boolean(default=False)
