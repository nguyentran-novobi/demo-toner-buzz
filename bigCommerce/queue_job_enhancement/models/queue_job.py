from odoo import models

from odoo.addons.queue_job.fields import JobSerialized


class QueueJob(models.Model):
    _inherit = 'queue.job'

    context = JobSerialized(readonly=True, base_type=dict)
