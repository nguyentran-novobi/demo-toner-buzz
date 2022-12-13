import logging
import functools

from odoo.addons.queue_job.job import Job as JobBase
from odoo.addons.queue_job.exception import NoSuchJobError

_logger = logging.getLogger(__name__)

UNSET = object()


def trim_unset_from_dict(obj):
    return {
        k: v
        for k, v in obj.items()
        if v is not UNSET
    }


class Job(JobBase):
    _context: dict

    @classmethod
    @functools.wraps(JobBase.load)
    def load(cls, env, job_uuid):
        exe_cls = Job if cls == JobBase else cls
        stored = exe_cls.db_record_from_uuid(env, job_uuid)
        if not stored:
            raise NoSuchJobError(
                "Job %s does no longer exist in the storage." % job_uuid
            )
        return exe_cls._load_from_db_record(stored)

    _original_load = JobBase.load
    JobBase.load = load

    @classmethod
    def _load_from_db_record(cls, job_db_record):
        job = super()._load_from_db_record(job_db_record)
        job._context = job_db_record.context or {}
        return job

    @classmethod
    @functools.wraps(JobBase.enqueue)
    def enqueue(
            cls,
            func,
            args=None,
            kwargs=None,
            priority=None,
            eta=None,
            max_retries=None,
            description=None,
            channel=None,
            identity_key=None,
    ):
        exe_cls = Job if cls == JobBase else cls
        new_job = exe_cls(
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            eta=eta,
            max_retries=max_retries,
            description=description,
            channel=channel,
            identity_key=identity_key,
        )
        if new_job.identity_key:
            existing = new_job.job_record_with_same_identity_key()
            if existing:
                _logger.debug(
                    "a job has not been enqueued due to having "
                    "the same identity key (%s) than job %s",
                    new_job.identity_key,
                    existing.uuid,
                )
                return exe_cls._load_from_db_record(existing)
        new_job.store()
        _logger.debug(
            "enqueued %s:%s(*%r, **%r) with uuid: %s",
            new_job.recordset,
            new_job.method_name,
            new_job.args,
            new_job.kwargs,
            new_job.uuid,
        )
        return new_job

    _original_enqueue = JobBase.enqueue
    JobBase.enqueue = enqueue

    def store(self):
        job_model = self.env['queue.job']
        edit_sentinel = job_model.EDIT_SENTINEL
        ctx = dict(_job_edit_sentinel=edit_sentinel)
        db_record = self.db_record()
        if db_record:
            vals = self._prepare_common_stored_values()
            db_record.with_context(**ctx).write(vals)
        else:
            vals = self._prepare_create_stored_values()
            job_model.with_context(**ctx).sudo().create(vals)

    def _prepare_create_stored_values(self):
        vals = self._prepare_common_stored_values()
        vals.update({
            'uuid': self.uuid,
            'name': self.description,
            'date_created': self.date_created,
            'method_name': self.method_name,
            'records': self.recordset,
            'args': self.args,
            'kwargs': self.kwargs,
            'channel': self.channel or UNSET,
            'context': self.context,
        })
        return trim_unset_from_dict(vals)

    def _prepare_common_stored_values(self):
        vals = {
            'state': self.state,
            'priority': self.priority,
            'retry': self.retry,
            'max_retries': self.max_retries,
            'exc_info': self.exc_info,
            'company_id': self.company_id,
            'result': str(self.result) if self.result else False,
            'date_enqueued': self.date_enqueued or False,
            'date_started': self.date_started or False,
            'date_done': self.date_done or False,
            'eta': self.eta or False,
            'identity_key': self.identity_key or False,
            'worker_pid': self.worker_pid,
        }
        return vals

    @property
    def func(self):
        ctx = dict(self.context) or {}
        ctx.update(job_uuid=self.uuid)
        recordset = self.recordset.with_context(**ctx)
        return getattr(recordset, self.method_name)

    @property
    def context(self):
        if hasattr(self, '_context'):
            return self._context
        return self.recordset.env.context
