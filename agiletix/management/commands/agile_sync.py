import logging
logger = logging.getLogger('agiletix')

import datetime

from agiletix.tasks import agile_sync_task

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    """
    This is a management command to sync events from Agile
    
    """

    def add_arguments(self, parser):
        parser.add_argument('--start',
                            help="Start for sync",
                            default='now',
                            )
        parser.add_argument('--end',
                            help="End for sync",
                            default='3m',
                            )

    def handle(self, *args, **options):
        logger.info("Starting agile sync...")
        start_date = timezone.localtime(timezone.now())
        end_date = start_date + datetime.timedelta(days=90)
        agile_sync_task(start_date, end_date)
        logger.info("Agile sync complete.")
