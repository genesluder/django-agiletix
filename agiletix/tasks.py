import logging
logger = logging.getLogger('agiletix')

from contextlib import contextmanager

from agiletix.sync_service import sync_events
from celery import task
from celery.five import monotonic

from django.core.cache import cache


LOCK_EXPIRE = 60 * 2  # Lock expires in 2 minutes


@contextmanager
def memcache_lock(lock_id, oid):
    timeout_at = monotonic() + LOCK_EXPIRE - 3
    # cache.add fails if the key already exists
    status = cache.add(lock_id, oid, LOCK_EXPIRE)
    try:
        yield status
    finally:
        # memcache delete is very slow, but we have to use it to take
        # advantage of using add() for atomic locking
        if monotonic() < timeout_at:
            # don't release the lock if we exceeded the timeout
            # to lessen the chance of releasing an expired lock
            # owned by someone else.
            cache.delete(lock_id)


@task(bind=True)
def agile_sync_task(self, start_date, end_date):
    lock_id = 'agile-sync-lock'
    with memcache_lock(lock_id, self.app.oid) as acquired:
        if acquired:
            sync_events(start_date, end_date)
            return
    logger.info('Agile sync is already being executed by another worker')
