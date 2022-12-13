from odoo import fields, models, api, _


class PaymentGateway(models.Model):
    _name = 'channel.payment.gateway'
    _description = 'Payment Gateway'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    platform = fields.Selection(related='channel_id.platform')
    channel_id = fields.Many2one('ecommerce.channel', string='Store', required=True, ondelete='cascade')
    id_on_channel = fields.Char(string='Id on Channel')

    _sql_constraints = [
        ('unique_code', 'unique (code, channel_id)', 'Payment Gateway already exists')
    ]
