# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class UoM(models.Model):
    _inherit = 'uom.uom'

    @api.constrains('category_id', 'uom_type', 'active')
    def _check_category_reference_uniqueness(self):
        """ Force the existence of only one UoM reference per category
            NOTE: this is a constraint on the all table. This might not be a good practice, but this is
            not possible to do it in SQL directly.
        """
        return True
