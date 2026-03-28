from __future__ import annotations

import logging
import time
from typing import Iterable, Optional

import cloudscraper
import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import ScraperConfig

LOGGER = logging.getLogger(__name__)


def build_session(config: ScraperConfig) -> Session:
    headers = {
        "User-Agent": config.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9,bg;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    session = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True,
        }
    )
    session.headers.update(headers)

    if config.proxy:
        session.proxies = {"http": config.proxy, "https": config.proxy}

    retry = Retry(
        total=config.request_retry_attempts,
        read=config.request_retry_attempts,
        connect=config.request_retry_attempts,
        backoff_factor=config.request_backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
        raise_on_redirect=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def _request_json(session: Session, url: str, *, timeout: float, referer: Optional[str] = None) -> list[dict]:
    LOGGER.debug("GET %s", url)
    headers = {"Accept": "application/json"}
    if referer:
        headers["Referer"] = referer
    response = session.get(url, timeout=timeout, headers=headers)
    _ensure_success(response)
    return response.json()  # type: ignore[return-value]


def _request_html(session: Session, url: str, *, timeout: float) -> str:
    LOGGER.debug("GET %s", url)
    response = session.get(url, timeout=timeout)
    _ensure_success(response)
    return response.text


def _ensure_success(response: Response) -> None:
    if response.ok:
        return
    LOGGER.error("Request to %s failed with status %s", response.url, response.status_code)
    response.raise_for_status()


def fetch_configurator_markup(session: Session, config: ScraperConfig) -> str:
    # Use Selenium to get the rendered HTML since the page may be JS-rendered
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(config.base_url)
        # Wait for elements with data-subcat to be present (up to 30 seconds)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-subcat]"))
        )
        time.sleep(2)  # Additional wait for JS to fully load
        html = driver.page_source
        # Debug: save HTML to file
        import os
        os.makedirs("output", exist_ok=True)
        with open("output/debug_configurator.html", "w", encoding="utf-8") as f:
            f.write(html)
        return html
    finally:
        driver.quit()


def iter_subcategory_products(
    driver: webdriver.Chrome,
    config: ScraperConfig,
    subcat_ids: Iterable[int],
    *,
    limit: Optional[int] = None,
) -> dict[int, list[dict]]:
    endpoint_template = f"{config.base_url}?loadSubcatProducts&term=&subcat={{subcat}}"
    results: dict[int, list[dict]] = {}
    for subcat in subcat_ids:
        url = endpoint_template.format(subcat=subcat)
        try:
            LOGGER.debug("GET %s via Selenium", url)
            driver.get(url)
            # Parse HTML and extract JSON from body
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            json_str = soup.body.get_text() if soup.body else driver.page_source
            payload = json.loads(json_str)
        except json.JSONDecodeError as e:
            LOGGER.warning("Subcategory %s returned non-JSON response: %s", subcat, driver.page_source[:500])
            continue
        except Exception as e:
            LOGGER.warning("Failed to load subcategory %s: %s", subcat, e)
            continue

        if not isinstance(payload, list):
            LOGGER.debug("Unexpected payload structure for %s: %s", subcat, type(payload))
            continue

        if limit is not None:
            results[subcat] = payload[:limit]
        else:
            results[subcat] = payload
        # Add delay to avoid rate limiting
        time.sleep(1)
    return results


__all__ = [
    "build_session",
    "fetch_configurator_markup",
    "iter_subcategory_products",
]
