from odoo import fields, models, api, _


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    module_multichannel_manage_price = fields.Boolean(string='Manage Variant Price')
