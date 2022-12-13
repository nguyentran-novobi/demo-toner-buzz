from odoo import fields, models


class ResourceImportOperationType(models.Model):
    _inherit = 'resource.import.operation.type'

    platform = fields.Selection(selection_add=[('bigcommerce', 'BigCommerce')])
