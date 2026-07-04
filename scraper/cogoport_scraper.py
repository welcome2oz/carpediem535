"""Cogoport ocean freight rate scraper (Playwright-based).

Cogoport's rate search does not require login, so this scraper only drives
the public search flow: type a city/port name in the origin/destination
box, pick the first autocomplete suggestion, submit, and read the quoted
rate. Every selector is a list of candidates tried in order (see
selectors.json) so small markup changes don't break the whole script.

If the real search flow turns out to differ from what's configured here,
run `python -m scraper.cogoport_scraper --discover` from a machine that can
actually reach cogoport.com - it dumps every input/button on the page
(placeholder, aria-label, text) so selectors.json can be corrected quickly.

Usage:
    python -m scraper.cogoport_scraper --origin "Busan, South Korea" --dest "Clarksville, United States"
    python -m scraper.cogoport_scraper --all --write
    python -m scraper.cogoport_scraper --discover
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

from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

SCRAPER_DIR = Path(__file__).parent
APP_DIR = SCRAPER_DIR.parent / "app"

sys.path.insert(0, str(SCRAPER_DIR.parent))


def load_selectors() -> dict:
    with (SCRAPER_DIR / "selectors.json").open("r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class ScrapeResult:
    origin_query: str
    dest_query: str
    rate: int | None
    error: str | None = None


def _first_matching(page: Page, candidates: list[str], timeout_ms: int = 3000) -> Locator:
    """Try each selector candidate in order, return the first one that appears."""
    last_error: Exception | None = None
    for selector in candidates:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator
        except PlaywrightTimeoutError as e:
            last_error = e
    raise PlaywrightTimeoutError(
        f"선택자 후보 중 어느 것도 찾지 못했습니다: {candidates}"
    ) from last_error


class CogoportScraper:
    """Reusable browser session for scraping one or many routes (no login required)."""

    def __init__(self, headless: bool = True, slow_mo_ms: int = 0):
        self.headless = headless
        self.slow_mo_ms = slow_mo_ms
        self.selectors = load_selectors()
        self._playwright = None
        self._browser = None
        self._page: Page | None = None

    def __enter__(self) -> "CogoportScraper":
        self._playwright = sync_playwright().start()
        launch_kwargs = {"headless": self.headless, "slow_mo": self.slow_mo_ms}
        executable_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
        self._browser = self._playwright.chromium.launch(**launch_kwargs)
        self._page = self._browser.new_page()
        self._page.goto(self.selectors["base_url"], wait_until="domcontentloaded", timeout=30000)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def _fill_and_select(self, field_candidates: list[str], query: str) -> None:
        page = self._page
        assert page is not None
        field = _first_matching(page, field_candidates)
        field.click()
        field.fill(query)
        try:
            option = _first_matching(page, self.selectors["search"]["autocomplete_option"], timeout_ms=4000)
            option.click()
        except PlaywrightTimeoutError:
            # Some search boxes accept free text without a dropdown - proceed as-is.
            pass

    def search_rate(self, origin_query: str, dest_query: str) -> ScrapeResult:
        s = self.selectors["search"]
        r = self.selectors["result"]
        page = self._page
        assert page is not None
        try:
            self._fill_and_select(s["origin_input"], origin_query)
            page.wait_for_timeout(500)
            self._fill_and_select(s["destination_input"], dest_query)
            page.wait_for_timeout(500)

            search_btn = _first_matching(page, s["search_button"])
            search_btn.click()

            price_el = _first_matching(page, r["price_element"], timeout_ms=r["result_timeout_ms"])
            raw_text = price_el.inner_text()
            rate = int(re.sub(r"[^0-9]", "", raw_text))
            return ScrapeResult(origin_query, dest_query, rate)
        except PlaywrightTimeoutError as e:
            return ScrapeResult(origin_query, dest_query, None, error=f"selector not found: {e}")
        except Exception as e:  # noqa: BLE001 - surface any scraping failure to the caller
            return ScrapeResult(origin_query, dest_query, None, error=str(e))


def load_countries() -> list[dict]:
    with (APP_DIR / "data" / "countries.json").open("r", encoding="utf-8") as f:
        return json.load(f)["countries"]


def search_query_for(country: dict) -> str:
    """"KRPUS (Busan)" + "South Korea" -> "Busan, South Korea" (matches how a real
    city/port autocomplete is searched, rather than raw UN/LOCODE codes)."""
    match = re.search(r"\(([^)]+)\)", country["port"])
    city = match.group(1) if match else country["port"]
    return f"{city}, {country['name']}"


def build_all_routes() -> list[tuple[str, str, str, str]]:
    countries = load_countries()
    routes = []
    for origin in countries:
        for dest in countries:
            if origin["code"] == dest["code"]:
                continue
            routes.append(
                (origin["code"], dest["code"], search_query_for(origin), search_query_for(dest))
            )
    return routes


def scrape_all(headless: bool, delay_seconds: float) -> dict[str, int]:
    results: dict[str, int] = {}
    routes = build_all_routes()
    with CogoportScraper(headless=headless) as scraper:
        for i, (origin_code, dest_code, origin_query, dest_query) in enumerate(routes):
            result = scraper.search_rate(origin_query, dest_query)
            key = f"{origin_code}-{dest_code}"
            if result.rate is not None:
                results[key] = result.rate
                print(f"[ok] {key}: {result.rate}")
            else:
                print(f"[skip] {key}: {result.error}", file=sys.stderr)
            if i < len(routes) - 1:
                time.sleep(delay_seconds)
    return results


def scrape_all_and_store(
    headless: bool, delay_seconds: float, note: str = "Cogoport RPA batch update"
) -> tuple[dict[str, int], int]:
    """Scrape every route and persist the results, shared by the API job,
    the daily scheduler, and the `--all --write` CLI path."""
    results = scrape_all(headless=headless, delay_seconds=delay_seconds)
    from app import storage

    count = storage.set_many(results, source="scraped", note=note)
    return results, count


def discover(headless: bool) -> None:
    """Dump every input/button on the search page so selectors.json can be calibrated.

    Run this from a machine with real internet access to cogoport.com - this
    sandbox's network policy blocks general web browsing, so the selectors
    shipped in selectors.json are best-effort guesses, not verified values.
    """
    selectors = load_selectors()
    with sync_playwright() as p:
        launch_kwargs = {"headless": headless}
        executable_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
        browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page()
        page.goto(selectors["base_url"], wait_until="load", timeout=30000)
        page.wait_for_timeout(2000)

        inputs = page.eval_on_selector_all(
            "input",
            "els => els.map(e => ({type: e.type, placeholder: e.placeholder, "
            "ariaLabel: e.getAttribute('aria-label'), name: e.name, id: e.id}))",
        )
        buttons = page.eval_on_selector_all(
            "button, a[role=button]",
            "els => els.map(e => ({text: e.innerText.trim().slice(0,40), "
            "ariaLabel: e.getAttribute('aria-label'), id: e.id}))",
        )

        print("=== INPUT FIELDS ===")
        print(json.dumps(inputs, indent=2, ensure_ascii=False))
        print("=== BUTTONS ===")
        print(json.dumps([b for b in buttons if b["text"] or b["ariaLabel"]], indent=2, ensure_ascii=False))

        out_path = SCRAPER_DIR / "discover_screenshot.png"
        page.screenshot(path=str(out_path), full_page=True)
        print(f"\n스크린샷 저장: {out_path}")
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cogoport ocean freight rate scraper")
    parser.add_argument("--origin", help="Origin search text, e.g. 'Busan, South Korea'")
    parser.add_argument("--dest", help="Destination search text, e.g. 'Clarksville, United States'")
    parser.add_argument("--all", action="store_true", help="Scrape every configured country pair")
    parser.add_argument("--discover", action="store_true", help="Dump page inputs/buttons for selector calibration")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--show-browser", dest="headless", action="store_false")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds between requests in --all mode")
    parser.add_argument("--write", action="store_true", help="Write results into the app's freight rate store")
    args = parser.parse_args()

    if args.discover:
        discover(headless=args.headless)
        return

    if args.all:
        if args.write:
            results, count = scrape_all_and_store(headless=args.headless, delay_seconds=args.delay)
            print(json.dumps(results, indent=2))
            print(f"[write] {count}개 구간 갱신 완료")
        else:
            results = scrape_all(headless=args.headless, delay_seconds=args.delay)
            print(json.dumps(results, indent=2))
        return

    if not (args.origin and args.dest):
        parser.error("--origin/--dest, --all, --discover 중 하나는 지정해야 합니다")

    with CogoportScraper(headless=args.headless) as scraper:
        result = scraper.search_rate(args.origin, args.dest)
        print(json.dumps(result.__dict__, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
