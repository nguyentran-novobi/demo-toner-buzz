# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.osv import expression
from odoo.exceptions import ValidationError


class ExportPricelistComposer(models.TransientModel):
    _name = 'export.pricelist.composer'
    _description = 'Export Pricelist Composer'

    pricelist_id = fields.Many2one('product.pricelist', required=True)
    allowed_channel_ids = fields.Many2many('ecommerce.channel', compute='_compute_allowed_channels')
    channel_id = fields.Many2one(
        'ecommerce.channel',
        string='Store',
        required=True,
        domain="[('id', 'in', allowed_channel_ids)]",
    )

    @api.depends('pricelist_id')
    def _compute_allowed_channels(self):
        for record in self:
            domain = [
                ('platform', '!=', 'none'),
                ('can_export_pricelist_from_master', '=', True),
            ]
            company = record.pricelist_id.company_id
            if company:
                domain = expression.AND([domain, [
                    ('company_id', '=', company.id)
                ]])
            channels = self.env['ecommerce.channel'].search(domain)
            record.update({
                'allowed_channel_ids': [(6, 0, channels.ids)]
            })

    def export(self):
        self.with_context(active_test=False).channel_id.ensure_operating()
        self._ensure_currency_supported()
        channel_pricelist = self._export_to_store()
        return self._redirect_to_pricelist_form(channel_pricelist)

    def _ensure_currency_supported(self):
        if self.pricelist_id.currency_id not in self.channel_id.currency_ids:
            raise ValidationError(_('Cannot export this pricelist. Currency is not supported in the online store.'))

    def _export_to_store(self):
        mapping = self._search_for_linked_mapping_pricelist()
        vals = self.env['channel.pricelist'].prepare_vals_from_master(self.pricelist_id, self.channel_id)
        res = self._create_or_update_mapping(mapping, vals)
        res.export_to_channel()
        return res

    def _search_for_linked_mapping_pricelist(self):
        return self.pricelist_id.channel_pricelist_ids.filtered(lambda r: r.channel_id == self.channel_id)[:1]

    def _create_or_update_mapping(self, mapping, vals):
        if mapping:
            mapping.update(vals)
            res = mapping
        else:
            res = self.env['channel.pricelist'].create(vals)
        return res

    def _redirect_to_pricelist_form(self, pricelist):
        form_view = self.env.ref('multichannel_bigcommerce.view_channel_pricelist_form')
        return {
            'name': 'Price List',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'channel.pricelist',
            'view_id': form_view.id,
            'res_id': pricelist.id,
            'type': 'ir.actions.act_window',
            'context': {
                'form_view_initial_mode': 'edit',
                'default_channel_id': self.channel_id.id,
            }
        }
