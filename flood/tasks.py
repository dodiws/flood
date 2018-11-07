
from celery.task.schedules import crontab
from celery.decorators import periodic_task
from celery.utils.log import get_task_logger
from datetime import datetime
from .views import runGlofasDownloader
# from celery import shared_task
from .isdc_gfms import ISDC_GFMSProcessor

logger = get_task_logger(__name__)

@periodic_task(run_every=(crontab(hour='3')))
def runGetGlofasDS():
	runGlofasDownloader()

# @shared_task()
@periodic_task(run_every=(crontab(hour='*')))
def gfms_task():
    processor = ISDC_GFMSProcessor()
    processor.run()
