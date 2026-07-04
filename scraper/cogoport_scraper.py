"""Cogoport ocean freight rate scraper (Playwright-based).

Replaces the previous Selenium prototype. Selector strings live in
selectors.json so a Cogoport UI change only needs a config edit, not a
code change. Login is optional and only attempted when COGOPORT_EMAIL /
COGOPORT_PASSWORD are set in the environment.

Usage:
    python -m scraper.cogoport_scraper --origin KRPUS --dest USCKV
    python -m scraper.cogoport_scraper --all --headless

The `--all` mode reads app/data/countries.json, builds every origin/dest
port pair, scrapes them one by one (with a polite delay between requests)
and writes results straight into the app's freight rate store.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError

SCRAPER_DIR = Path(__file__).parent
APP_DIR = SCRAPER_DIR.parent / "app"

sys.path.insert(0, str(SCRAPER_DIR.parent))


def load_selectors() -> dict:
    with (SCRAPER_DIR / "selectors.json").open("r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class ScrapeResult:
    origin_port: str
    dest_port: str
    rate: int | None
    error: str | None = None


class CogoportScraper:
    """Reusable browser session for scraping one or many routes.

    사이트 로그인이 필요하거나 실제 검색 흐름(자동완성, 다단계 폼 등)이 다르면
    이 클래스의 search_rate()만 사이트 구조에 맞게 조정하면 됩니다.
    """

    def __init__(self, headless: bool = True, slow_mo_ms: int = 0):
        self.headless = headless
        self.slow_mo_ms = slow_mo_ms
        self.selectors = load_selectors()
        self._playwright = None
        self._browser = None
        self._page: Page | None = None

    def __enter__(self) -> "CogoportScraper":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless, slow_mo=self.slow_mo_ms
        )
        self._page = self._browser.new_page()
        self._page.goto(self.selectors["base_url"], wait_until="domcontentloaded")
        self._maybe_login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def _maybe_login(self) -> None:
        email = os.environ.get("COGOPORT_EMAIL")
        password = os.environ.get("COGOPORT_PASSWORD")
        if not (email and password):
            return
        login = self.selectors["login"]
        try:
            self._page.click(login["trigger_button"], timeout=5000)
            self._page.fill(login["email_input"], email)
            self._page.fill(login["password_input"], password)
            self._page.click(login["submit_button"])
            self._page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            print("[warn] 로그인 절차를 찾지 못했습니다 - 셀렉터를 확인하세요.", file=sys.stderr)

    def search_rate(self, origin_port: str, dest_port: str) -> ScrapeResult:
        s = self.selectors["search"]
        r = self.selectors["result"]
        page = self._page
        assert page is not None
        try:
            page.fill(s["origin_input"], origin_port)
            page.wait_for_timeout(800)
            page.fill(s["destination_input"], dest_port)
            page.wait_for_timeout(800)
            page.click(s["search_button"])

            price_el = page.wait_for_selector(
                r["price_element"],
                timeout=r["result_timeout_ms"],
            )
            raw_text = price_el.inner_text()
            rate = int(re.sub(r"[^0-9]", "", raw_text))
            return ScrapeResult(origin_port, dest_port, rate)
        except PlaywrightTimeoutError:
            return ScrapeResult(origin_port, dest_port, None, error="timeout waiting for result")
        except Exception as e:  # noqa: BLE001 - surface any scraping failure to the caller
            return ScrapeResult(origin_port, dest_port, None, error=str(e))


def load_country_ports() -> list[dict]:
    with (APP_DIR / "data" / "countries.json").open("r", encoding="utf-8") as f:
        return json.load(f)["countries"]


def port_code(port_field: str) -> str:
    """"KRPUS (Busan)" -> "KRPUS" """
    return port_field.split(" ")[0].strip()


def build_all_routes() -> list[tuple[str, str, str, str]]:
    countries = load_country_ports()
    routes = []
    for origin in countries:
        for dest in countries:
            if origin["code"] == dest["code"]:
                continue
            routes.append(
                (origin["code"], dest["code"], port_code(origin["port"]), port_code(dest["port"]))
            )
    return routes


def scrape_all(headless: bool, delay_seconds: float) -> dict[str, int]:
    results: dict[str, int] = {}
    routes = build_all_routes()
    with CogoportScraper(headless=headless) as scraper:
        for i, (origin_code, dest_code, origin_port, dest_port) in enumerate(routes):
            result = scraper.search_rate(origin_port, dest_port)
            key = f"{origin_code}-{dest_code}"
            if result.rate is not None:
                results[key] = result.rate
                print(f"[ok] {key}: {result.rate}")
            else:
                print(f"[skip] {key}: {result.error}", file=sys.stderr)
            if i < len(routes) - 1:
                time.sleep(delay_seconds)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Cogoport ocean freight rate scraper")
    parser.add_argument("--origin", help="Origin port code, e.g. KRPUS")
    parser.add_argument("--dest", help="Destination port code, e.g. USCKV")
    parser.add_argument("--all", action="store_true", help="Scrape every configured country pair")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--show-browser", dest="headless", action="store_false")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds between requests in --all mode")
    parser.add_argument("--write", action="store_true", help="Write results into the app's freight rate store")
    args = parser.parse_args()

    if args.all:
        results = scrape_all(headless=args.headless, delay_seconds=args.delay)
        print(json.dumps(results, indent=2))
        if args.write and results:
            from app import storage  # local import so `--origin` mode has no FastAPI dependency

            count = storage.set_many(results, source="scraped", note="Cogoport RPA batch update")
            print(f"[write] {count}개 구간 갱신 완료")
        return

    if not (args.origin and args.dest):
        parser.error("--origin/--dest 또는 --all 중 하나는 지정해야 합니다")

    with CogoportScraper(headless=args.headless) as scraper:
        result = scraper.search_rate(args.origin, args.dest)
        print(json.dumps(result.__dict__, indent=2))


if __name__ == "__main__":
    main()
