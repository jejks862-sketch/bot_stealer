from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)


class ReminderScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.active_jobs = {}

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def stop(self):
        if self.scheduler.running:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    logger.info("Scheduler stopped (event loop already closed)")
                    return
            except RuntimeError:
                logger.info("Scheduler stopped (no event loop)")
                return
            
            try:
                self.scheduler.shutdown()
                logger.info("Scheduler stopped")
            except RuntimeError:
                logger.info("Scheduler stopped (event loop closed)")

    def add_job(self, func, trigger: str, job_id: str, **kwargs):
        try:
            job = self.scheduler.add_job(
                func,
                trigger,
                id=job_id,
                **kwargs
            )
            self.active_jobs[job_id] = job
            logger.info(f"Job added: {job_id}")
            return job
        except Exception as e:
            logger.error(f"Error adding job {job_id}: {e}")
            return None

    def remove_job(self, job_id: str):
        try:
            self.scheduler.remove_job(job_id)
            self.active_jobs.pop(job_id, None)
            logger.info(f"Job removed: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing job {job_id}: {e}")
            return False

    def reschedule_job(self, job_id: str, **kwargs):
        try:
            job = self.scheduler.reschedule_job(job_id, **kwargs)
            logger.info(f"Job rescheduled: {job_id}")
            return job
        except Exception as e:
            logger.error(f"Error rescheduling job {job_id}: {e}")
            return None

    def get_job(self, job_id: str):
        return self.active_jobs.get(job_id)

    def get_all_jobs(self):
        return list(self.active_jobs.values())
