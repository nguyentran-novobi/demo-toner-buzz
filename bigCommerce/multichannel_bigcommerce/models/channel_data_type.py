from odoo import fields, models, api, _


class ChannelDataType(models.Model):
    _inherit = 'channel.data.type'

    platform = fields.Selection(selection_add=[('bigcommerce', 'BigCommerce')], ondelete={'bigcommerce': 'set default'})
