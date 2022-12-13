# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import models, fields, api, exceptions, _
from odoo.tools.safe_eval import safe_eval
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class QueueJob(models.Model):
    """Model storing the jobs to be executed."""
    _inherit = 'queue.job'

    has_infailedsqltransaction = fields.Boolean(compute='_check_error', store=True)
    has_cachemiss = fields.Boolean(compute='_check_exc_info', store=True)

    @api.depends('result')
    def _check_error(self):
        for record in self:
            record.has_infailedsqltransaction = True if record.result and 'psycopg2.errors.InFailedSqlTransaction' in record.result else False

    @api.depends('exc_info')
    def _check_exc_info(self):
        for record in self:
            record.has_cachemiss = True if record.exc_info and 'CacheMiss' in record.exc_info else False

    @api.model
    def check_job(self):
        before_30m_current = datetime.now() - timedelta(minutes=30)
        requeue_jobs = self.sudo().search(['&', ('state', 'not in', ['done', 'failed']), '|', ('date_created', '<', before_30m_current),
                                           '|', ('has_infailedsqltransaction', '=', True), ('has_cachemiss', '=', True)])
        requeue_jobs.button_done()
        requeue_jobs.requeue()
        return True

    def write(self, vals):
        res = super(QueueJob, self).write(vals)
        if vals.get("state") == "failed":
            records = self.filtered(lambda r: r.exc_info and 'CacheMiss' in r.exc_info)
            records.requeue()
        return res
