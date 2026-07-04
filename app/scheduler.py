"""Daily automatic refresh of every ocean freight route from Cogoport.

Runs once a day via APScheduler (separate thread pool, doesn't block the
FastAPI event loop) so "해상운임 관리" reflects Cogoport's price for the day
without anyone clicking a button. Configurable via env vars:

    DAILY_REFRESH_ENABLED=true        # set to false to disable entirely
    DAILY_REFRESH_HOUR=7              # 0-23, in DAILY_REFRESH_TZ
    DAILY_REFRESH_MINUTE=0
    DAILY_REFRESH_TZ=UTC              # e.g. Asia/Seoul
    COGOPORT_REQUEST_DELAY_SECONDS=3  # pause between routes, be polite
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app import storage

JOB_ID = "daily_cogoport_refresh"

_scheduler: BackgroundScheduler | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _merge_status(update: dict) -> dict:
    status = storage.get_scheduler_status()
    status.update(update)
    return status


def run_daily_refresh(delay_seconds: float) -> None:
    storage.set_scheduler_status(_merge_status({"status": "running", "startedAt": _now_iso()}))
    try:
        from scraper.cogoport_scraper import scrape_all_and_store

        results, count = scrape_all_and_store(
            headless=True, delay_seconds=delay_seconds, note="Cogoport 자동 일일 갱신"
        )
        storage.set_scheduler_status(
            _merge_status(
                {
                    "status": "done",
                    "updated": count,
                    "totalRoutes": len(results),
                    "finishedAt": _now_iso(),
                    "error": None,
                }
            )
        )
    except Exception as e:  # noqa: BLE001
        storage.set_scheduler_status(
            _merge_status({"status": "error", "error": str(e), "finishedAt": _now_iso()})
        )


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if os.environ.get("DAILY_REFRESH_ENABLED", "true").strip().lower() not in ("1", "true", "yes"):
        storage.set_scheduler_status(_merge_status({"enabled": False}))
        return None

    hour = int(os.environ.get("DAILY_REFRESH_HOUR", "7"))
    minute = int(os.environ.get("DAILY_REFRESH_MINUTE", "0"))
    tz = os.environ.get("DAILY_REFRESH_TZ", "UTC")
    delay_seconds = float(os.environ.get("COGOPORT_REQUEST_DELAY_SECONDS", "3.0"))

    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(
        run_daily_refresh,
        CronTrigger(hour=hour, minute=minute, timezone=tz),
        args=[delay_seconds],
        id=JOB_ID,
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler

    storage.set_scheduler_status(
        _merge_status({"enabled": True, "hour": hour, "minute": minute, "timezone": tz})
    )
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def get_next_run_time() -> str | None:
    if _scheduler is None:
        return None
    job = _scheduler.get_job(JOB_ID)
    if job is None or job.next_run_time is None:
        return None
    return job.next_run_time.isoformat()
