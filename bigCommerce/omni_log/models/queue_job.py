# Copyright 2013-2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
from odoo import _, api, fields, models, registry, SUPERUSER_ID

_logger = logging.getLogger(__name__)


class QueueJob(models.Model):
    _inherit = 'queue.job'

    log_id = fields.Many2one('omni.log', string='Omni log')

    def write(self, vals):
        for record in self:
            def write_log():
                db_registry = registry(db_name)
                with db_registry.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, context)
                    rec = env['queue.job'].browse(res_id)
                    if rec.log_id and 'state' in vals:
                        status = vals['state']
                        try:
                            if status in ['done', 'failed']:
                                if status == "done":
                                    rec.log_id.update_status(status=status, message=None)
                                if status == "failed":
                                    rec.log_id.update_status(status=status, message=rec.exc_info)
                        except Exception as err:
                            rec.log_id.update_status(status='failed', message=str(err))

                    cr.commit()

            db_name = self.env.cr.dbname
            context = self.env.context
            res_id = record.id
            self.env.cr.postcommit.add(write_log)
        return super(QueueJob, self).write(vals)

    @api.model
    def create(self, vals):
        if 'log_id' in self.env.context:
            vals['log_id'] = int(self.env.context['log_id'])
        return super(QueueJob, self).create(vals)
