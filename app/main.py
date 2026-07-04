"""Trade Cost Simulator API.

Serves the frontend, the country/cargo config, the persisted ocean freight
rate matrix, and endpoints to update that matrix manually or by triggering
the Cogoport scraper (single route inline, full matrix as a background job).
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import storage

BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = FastAPI(title="Trade Cost Simulator")


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _country_codes() -> list[str]:
    return [c["code"] for c in _load_json(BASE_DIR / "data" / "countries.json")["countries"]]


@app.on_event("startup")
def _seed_rates() -> None:
    storage.seed_if_empty(_country_codes())


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@app.get("/api/config")
def get_config() -> dict:
    countries = _load_json(BASE_DIR / "data" / "countries.json")
    cargo = _load_json(BASE_DIR / "data" / "cargo_profiles.json")
    return {"countries": countries["countries"], "cargoProfiles": cargo["profiles"]}


# ---------------------------------------------------------------------------
# Freight rates
# ---------------------------------------------------------------------------

@app.get("/api/rates")
def get_rates() -> dict:
    return storage.get_all()


class ManualRateUpdate(BaseModel):
    rate: float = Field(gt=0)
    note: str = ""


@app.put("/api/rates/{route_key}")
def put_rate(route_key: str, body: ManualRateUpdate) -> dict:
    if "-" not in route_key:
        raise HTTPException(400, "route_key must look like ORIGIN-DEST, e.g. KR-US")
    return storage.set_rate(route_key, body.rate, source="manual", note=body.note)


class BulkRateUpdate(BaseModel):
    routes: dict[str, float]
    note: str = "수동 일괄 업데이트"


@app.post("/api/rates/bulk")
def post_rates_bulk(body: BulkRateUpdate) -> dict:
    count = storage.set_many(body.routes, source="manual", note=body.note)
    return {"updated": count}


# ---------------------------------------------------------------------------
# Cogoport scraper integration
# ---------------------------------------------------------------------------

class RefreshOneRequest(BaseModel):
    origin: str
    dest: str
    origin_query: str
    dest_query: str


@app.post("/api/rates/refresh")
def refresh_one(body: RefreshOneRequest) -> dict:
    """Scrape a single route inline and persist the result. Blocking (~10-20s)."""
    try:
        from scraper.cogoport_scraper import CogoportScraper
    except ImportError as e:
        raise HTTPException(
            503,
            f"스크래퍼 의존성이 설치되어 있지 않습니다 (playwright install 필요): {e}",
        ) from e

    try:
        with CogoportScraper(headless=True) as scraper:
            result = scraper.search_rate(body.origin_query, body.dest_query)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"스크래핑 실행 중 오류: {e}") from e

    if result.rate is None:
        raise HTTPException(502, f"운임 조회 실패: {result.error}")

    route_key = f"{body.origin}-{body.dest}"
    entry = storage.set_rate(route_key, result.rate, source="scraped", note="Cogoport 자동 조회")
    return {"routeKey": route_key, **entry}


# --- Background batch refresh (all routes) ---------------------------------

_jobs: dict[str, dict] = {}
_jobs_lock = Lock()


def _run_batch_refresh(job_id: str, delay_seconds: float) -> None:
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
    try:
        from scraper.cogoport_scraper import scrape_all

        results = scrape_all(headless=True, delay_seconds=delay_seconds)
        count = storage.set_many(results, source="scraped", note="Cogoport RPA 배치 업데이트")
        with _jobs_lock:
            _jobs[job_id].update(status="done", updated=count, finishedAt=_now_iso())
    except Exception as e:  # noqa: BLE001
        with _jobs_lock:
            _jobs[job_id].update(status="error", error=str(e), finishedAt=_now_iso())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@app.post("/api/rates/refresh-all")
def refresh_all(background_tasks: BackgroundTasks, delay_seconds: float = 3.0) -> dict:
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "startedAt": _now_iso()}
    background_tasks.add_task(_run_batch_refresh, job_id, delay_seconds)
    return {"jobId": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
