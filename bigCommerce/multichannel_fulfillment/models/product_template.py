# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_deliverable_service = fields.Boolean('Deliverable Service',
                                            compute='_compute_is_deliverable_service', search='_search_is_deliverable_service')

    def _compute_is_deliverable_service(self):
        for record in self:
            record.is_deliverable_service = all((record.type == 'service', record.service_type == 'manual',
                                                 record.invoice_policy == 'delivery', record.sale_ok))

    def _search_is_deliverable_service(self, operator, value):
        if operator not in ('=', '!=', '<>'):
            raise ValueError('Invalid operator: %s' % (operator,))
        op = ('!=' if operator == '=' else '=') if not value else operator
        conj = '|' if op != '=' else '&'
        domain = [conj, conj, ('type', op, 'service'), ('service_type', op, 'manual'), ('invoice_policy', op, 'delivery')]
        return domain
