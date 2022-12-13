from odoo import fields, models, api, _


class ChannelDataType(models.Model):
    _name = 'channel.data.type'
    _description = 'Channel Data Type'

    name = fields.Char(string='Name', required=True)
    platform = fields.Selection([('none', 'None')], default='none', string='Platform')
    res_model = fields.Char(string='Model', required=True)

    def channel_import_others(self, channel, ids, all_records):
        self.env[self.res_model].channel_import_data(channel, ids, all_records)

    def channel_export_others(self, ids):
        self.env[self.res_model].channel_export_data(ids)
