"""
Social Blade scraping for fake-follower-deteksjon (spec seksjon 7.3 kriterium 9).

Henter ukentlige follower-snapshots fra Social Blade's offentlige sider.
Returnerer en liste {date, follower_delta} som filteret bruker.

Bruker Playwright (headless Chromium) - tregere enn API men nodvendig
fordi Social Blade ikke har offentlig API.
"""
from __future__ import annotations

import logging
import random
import re
import time
from datetime import datetime, timezone

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from .config import load_config

log = logging.getLogger(__name__)

SOCIALBLADE_URLS = {
    "instagram": "https://socialblade.com/instagram/user/{handle}",
    "tiktok": "https://socialblade.com/tiktok/user/{handle}",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
)


def _polite_delay() -> None:
    time.sleep(random.uniform(3.0, 7.0))


def _parse_int(text: str) -> int | None:
    cleaned = re.sub(r"[^0-9\-+]", "", text)
    if not cleaned or cleaned in {"-", "+"}:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def scrape_weekly_growth(handle: str, platform: str = "instagram") -> list[dict]:
    """Hent ukentlige follower-deltas for én creator.

    Returnerer: [{"date": datetime, "follower_delta": int}, ...]
    Nyeste først. Returnerer tom liste hvis siden ikke kan leses.
    """
    handle = handle.lstrip("@")
    url = SOCIALBLADE_URLS[platform].format(handle=handle)
    data: list[dict] = []

    cfg = load_config()
    proxy_url = cfg.get("proxy", "").strip()

    with sync_playwright() as pw:
        launch_kwargs = {"headless": True}
        if proxy_url:
            launch_kwargs["proxy"] = {"server": proxy_url}
            log.info("Bruker proxy for Social Blade-scraping")
        browser = pw.chromium.launch(**launch_kwargs)
        context = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1280, "height": 800})
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(2000)

            rows = page.locator("div#socialblade-user-content table tbody tr").all()
            for row in rows:
                cells = row.locator("td").all_inner_texts()
                if len(cells) < 4:
                    continue
                date_text = cells[0].strip()
                delta_text = cells[2].strip() if len(cells) > 2 else ""

                try:
                    dt = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                delta = _parse_int(delta_text)
                if delta is None:
                    continue
                data.append({"date": dt, "follower_delta": delta})
        except PlaywrightTimeout:
            log.warning("Social Blade timeout for @%s (%s)", handle, platform)
        except Exception as e:
            log.warning("Social Blade scraping feilet for @%s: %s", handle, e)
        finally:
            context.close()
            browser.close()

    _polite_delay()
    data.sort(key=lambda d: d["date"], reverse=True)
    return data
