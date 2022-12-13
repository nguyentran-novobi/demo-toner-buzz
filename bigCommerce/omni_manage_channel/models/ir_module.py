# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import logging
import threading

_logger = logging.getLogger(__name__)


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    @api.model
    def _uninstall_app(self, uninstall_apps):
        new_cr = self.pool.cursor()
        self = self.with_env(self.env(cr=new_cr))
        modules = self.sudo().search([('name', 'in', uninstall_apps)])
        try:
            for module in modules:
                if module.state == 'installed':
                    module.with_context(prefetch_fields=False).with_user(1).button_immediate_uninstall()
                    self._cr.commit()

            remaining_apps = ['point_of_sale', 'sale_subscription', 'sale_renting', 'social_sale', 'sign', 'website']
            remaining_modules = self.sudo().search([('name', 'in', remaining_apps),
                                                    ('name', 'not in', uninstall_apps)])
            for module in remaining_modules:
                if module.state != 'installed':
                    module.with_context(prefetch_fields=False).with_user(1).button_immediate_install()
                    self._cr.commit()
            new_cr.close()
        except Exception:
            pass

    @api.model
    def ob_uninstall_app(self, uninstall_apps):
        try:
            thread = threading.Thread(target=self._uninstall_app, kwargs={'uninstall_apps': uninstall_apps})
            thread.start()
        except Exception as e:
            pass