from __future__ import annotations

import logging
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.time import now_shanghai
from app.runtime import RuntimeContainer


logger = logging.getLogger(__name__)


class MarketScheduler:
    JOB_ID = "capital-voyage-market-poll"

    def __init__(self, runtime: RuntimeContainer):
        self.runtime = runtime
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    def start(self) -> None:
        if self.scheduler.running:
            return
        self.scheduler.start()
        self._schedule(0)

    def _schedule(self, delay: int) -> None:
        self.scheduler.add_job(
            self._run,
            trigger="date",
            run_date=now_shanghai() + timedelta(seconds=delay),
            id=self.JOB_ID,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    def _run(self) -> None:
        result = self.runtime.poller.poll_once()
        try:
            self.runtime.evaluate_monitors()
        except Exception:
            logger.exception("monitor evaluation failed")
        finally:
            self._schedule(result.next_interval_seconds)

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
