from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

BASE_URL = "https://gunsarizona.com"
CATEGORY_URL = "https://gunsarizona.com/classifieds-search?se=1&se_cats=23&days_l=1"
DEFAULT_INTERVAL_MINUTES = 5
REQUEST_TIMEOUT_SECONDS = 30
MAX_DESCRIPTION_LENGTH = 700
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_KEYWORDS = [
    "Daniel Defense",
    "DDM4",
    "MK18",
    "Glock 19",
    "Glock 43X",
    "Sig P365",
    "P365X",
    "P365XL",
    "XMacro",
]


@dataclass(frozen=True)
class SearchListing:
    ad_id: str
    title: str
    url: str
    price: str = "N/A"
    location: str = "Unknown"
    relative_time: str = "Unknown"
    snippet: str = ""


@dataclass(frozen=True)
class ListingDetails:
    title: str
    price: str
    location: str
    added: str
    description: str
    contact: str = ""


@dataclass
class ScanSummary:
    started_at: datetime = field(default_factory=datetime.now)
    listings_checked: int = 0
    skipped_seen: int = 0
    matched: int = 0
    delivered: int = 0
    previewed: int = 0
    errors: list[str] = field(default_factory=list)
    notifications_enabled: bool = False
    dry_run: bool = False


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def clean_text(node: Any) -> str:
    if node is None:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def trim_text(value: str, limit: int = MAX_DESCRIPTION_LENGTH) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def extract_ad_id(url: str) -> str:
    match = re.search(r"(\d+)(?:/)?$", url)
    if match:
        return match.group(1)
    return url.rstrip("/").split("-")[-1]


def normalize_keywords(raw_keywords: list[Any]) -> list[str]:
    keywords = [str(value).strip() for value in raw_keywords if str(value).strip()]
    return dedupe_preserve_order(keywords)


def load_config(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    config: dict[str, Any] = {}

    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise RuntimeError(f"{path} must contain a JSON object.")
        config.update(data)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    env_keywords = os.getenv("GUN_BOT_KEYWORDS")
    env_interval = os.getenv("CHECK_INTERVAL_MINUTES")

    if token:
        config["telegram_bot_token"] = token
    if chat_id:
        config["telegram_chat_id"] = chat_id
    if env_keywords:
        config["keywords"] = [item.strip() for item in env_keywords.split(",")]
    if env_interval:
        config["check_interval_minutes"] = env_interval

    config["keywords"] = normalize_keywords(config.get("keywords") or DEFAULT_KEYWORDS)

    try:
        interval = int(config.get("check_interval_minutes", DEFAULT_INTERVAL_MINUTES))
    except (TypeError, ValueError):
        interval = DEFAULT_INTERVAL_MINUTES

    config["check_interval_minutes"] = max(1, interval)
    return config


def load_seen_ads(seen_path: str | Path) -> list[str]:
    path = Path(seen_path)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    cleaned = [str(item) for item in data if str(item).strip()]
    return dedupe_preserve_order(cleaned)


def save_seen_ads(seen_path: str | Path, seen_ids: list[str]) -> None:
    path = Path(seen_path)
    path.write_text(json.dumps(seen_ids, indent=2) + "\n", encoding="utf-8")


def has_telegram_config(config: dict[str, Any]) -> bool:
    return bool(config.get("telegram_bot_token") and config.get("telegram_chat_id"))


def fetch_html(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Request to {url} failed with HTTP {exc.code}: {body[:250]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request to {url} failed: {exc.reason}") from exc


def parse_search_results(html_text: str) -> list[SearchListing]:
    soup = BeautifulSoup(html_text, "html.parser")
    rows = soup.select("#dj-classifieds .dj-items .item_row") or soup.select(".item_row")

    listings: list[SearchListing] = []
    seen_ids: set[str] = set()

    for row in rows:
        title_node = row.select_one(".item_title a")
        if title_node is None:
            continue

        title = clean_text(title_node)
        href = title_node.get("href")
        if not title or not href:
            continue

        url = urljoin(BASE_URL, href)
        ad_id = extract_ad_id(url)
        if ad_id in seen_ids:
            continue

        price_value = clean_text(row.select_one(".item_price .price_val"))
        price_unit = clean_text(row.select_one(".item_price .price_unit"))
        price = " ".join(part for part in [price_value, price_unit] if part) or "N/A"

        location = clean_text(row.select_one(".item_region a")) or clean_text(
            row.select_one(".item_region")
        ) or "Unknown"
        relative_time = clean_text(row.select_one(".item_date_start")) or "Unknown"
        snippet = clean_text(row.select_one(".item_desc a")) or clean_text(
            row.select_one(".item_desc")
        )

        listings.append(
            SearchListing(
                ad_id=ad_id,
                title=title,
                url=url,
                price=price,
                location=location,
                relative_time=relative_time,
                snippet=snippet,
            )
        )
        seen_ids.add(ad_id)

    return listings


def parse_listing_details(html_text: str, listing: SearchListing) -> ListingDetails:
    soup = BeautifulSoup(html_text, "html.parser")

    title = clean_text(soup.select_one(".dj-item .title_top h2")) or listing.title

    price_value = clean_text(soup.select_one(".dj-item .general_det .price_val"))
    price_unit = clean_text(soup.select_one(".dj-item .general_det .price_unit"))
    price = " ".join(part for part in [price_value, price_unit] if part) or listing.price

    location = clean_text(soup.select_one(".dj-item .localization_det .row_value")) or listing.location
    added = clean_text(soup.select_one(".dj-item .general_det .row_gd.added .row_value")) or (
        listing.relative_time
    )
    description = clean_text(soup.select_one(".dj-item .description .desc_content"))
    if not description:
        meta_description = soup.select_one('meta[name="description"]')
        if meta_description is not None:
            description = (meta_description.get("content") or "").strip()
    if not description:
        description = listing.snippet or "No description available."

    contact = clean_text(soup.select_one(".dj-item .general_det .djcf_contact .row_value"))

    return ListingDetails(
        title=title,
        price=price,
        location=location or "Unknown",
        added=added or "Unknown",
        description=trim_text(description),
        contact=contact,
    )


def listing_matches_keywords(listing: SearchListing, keywords: list[str]) -> bool:
    haystack = f"{listing.title} {listing.snippet}".lower()
    normalized_haystack = normalize_text(haystack)

    for keyword in keywords:
        raw_keyword = keyword.lower()
        normalized_keyword = normalize_text(keyword)
        if raw_keyword in haystack or normalized_keyword in normalized_haystack:
            return True
    return False


def build_listing_details(listing: SearchListing) -> ListingDetails:
    try:
        return parse_listing_details(fetch_html(listing.url), listing)
    except Exception:
        return ListingDetails(
            title=listing.title,
            price=listing.price,
            location=listing.location,
            added=listing.relative_time,
            description=trim_text(listing.snippet or "No description available."),
            contact="",
        )


def format_telegram_message(listing: SearchListing, details: ListingDetails) -> str:
    title = html.escape(details.title)
    price = html.escape(details.price)
    location = html.escape(details.location)
    added = html.escape(details.added)
    url = html.escape(listing.url, quote=True)

    def compose_message(description_text: str) -> str:
        lines = [
            "<b>Gun Match</b>",
            f"<b>Title:</b> {title}",
            f"<b>Price:</b> {price}",
            f"<b>Location:</b> {location}",
            f"<b>Added:</b> {added}",
        ]

        if details.contact:
            lines.append(f"<b>Contact:</b> {html.escape(details.contact)}")

        lines.extend(
            [
                "",
                f"<b>Description:</b> {html.escape(description_text)}",
                "",
                f'<a href="{url}">Open ad</a>',
            ]
        )
        return "\n".join(lines)

    message = compose_message(details.description)
    if len(message) <= 4096:
        return message

    overflow = len(message) - 4096
    shortened = trim_text(details.description, max(100, MAX_DESCRIPTION_LENGTH - overflow - 25))
    message = compose_message(shortened)
    if len(message) <= 4096:
        return message

    return message[:4093].rstrip() + "..."


def send_telegram_message(message: str, config: dict[str, Any]) -> None:
    token = config.get("telegram_bot_token")
    chat_id = config.get("telegram_chat_id")
    if not token or not chat_id:
        raise RuntimeError("Telegram is not configured.")

    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": "false",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram returned HTTP {exc.code}: {body[:250]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Telegram request failed: {exc.reason}") from exc


def print_match_preview(listing: SearchListing, details: ListingDetails) -> None:
    print(f"[match] {details.title}")
    print(f"        Price: {details.price}")
    print(f"        Location: {details.location}")
    print(f"        Added: {details.added}")
    if details.contact:
        print(f"        Contact: {details.contact}")
    print(f"        URL: {listing.url}")
    print(f"        Description: {details.description}")


def scan_once(
    config_path: str | Path,
    seen_path: str | Path,
    dry_run: bool = False,
) -> ScanSummary:
    config = load_config(config_path)
    summary = ScanSummary(
        notifications_enabled=has_telegram_config(config),
        dry_run=dry_run,
    )
    keywords = config["keywords"]

    seen_ids = load_seen_ads(seen_path)
    seen_set = set(seen_ids)

    listings = parse_search_results(fetch_html(CATEGORY_URL))
    summary.listings_checked = len(listings)
    if not listings:
        summary.errors.append(
            "Search page returned 0 listings. The page markup may have changed or the request was blocked."
        )
        return summary

    warned_about_console_delivery = False

    for listing in listings:
        if listing.ad_id in seen_set:
            summary.skipped_seen += 1
            continue

        if not listing_matches_keywords(listing, keywords):
            continue

        summary.matched += 1

        try:
            details = build_listing_details(listing)
        except Exception as exc:
            summary.errors.append(f"{listing.url}: {exc}")
            details = ListingDetails(
                title=listing.title,
                price=listing.price,
                location=listing.location,
                added=listing.relative_time,
                description=trim_text(listing.snippet or "No description available."),
                contact="",
            )

        if dry_run or not summary.notifications_enabled:
            if not warned_about_console_delivery and not dry_run and not summary.notifications_enabled:
                print("[!] Telegram is not configured. Printing matches without marking them as seen.")
                warned_about_console_delivery = True
            print_match_preview(listing, details)
            summary.previewed += 1
            continue

        try:
            send_telegram_message(format_telegram_message(listing, details), config)
        except Exception as exc:
            summary.errors.append(f"{listing.url}: {exc}")
            continue

        seen_ids.append(listing.ad_id)
        seen_set.add(listing.ad_id)
        summary.delivered += 1
        print(f"[+] Sent alert for {details.title}")

    if summary.delivered:
        save_seen_ads(seen_path, seen_ids)

    return summary


def print_summary(summary: ScanSummary) -> None:
    timestamp = summary.started_at.strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"[*] Scan finished at {timestamp} | checked={summary.listings_checked} "
        f"matched={summary.matched} sent={summary.delivered} "
        f"previewed={summary.previewed} seen={summary.skipped_seen} "
        f"errors={len(summary.errors)}"
    )
    for error in summary.errors:
        print(f"[-] {error}")


def run_once(
    config_path: str | Path = "config.json",
    seen_path: str | Path = "seen_ads.json",
    dry_run: bool = False,
) -> int:
    try:
        summary = scan_once(config_path=config_path, seen_path=seen_path, dry_run=dry_run)
    except Exception as exc:
        print(f"[-] Scan failed: {exc}")
        return 1

    print_summary(summary)
    return 1 if summary.errors else 0


def run_forever(
    config_path: str | Path = "config.json",
    seen_path: str | Path = "seen_ads.json",
    interval_override: int | None = None,
    dry_run: bool = False,
) -> int:
    print("[*] Starting GunsArizona bot loop.")
    while True:
        exit_code = run_once(config_path=config_path, seen_path=seen_path, dry_run=dry_run)
        try:
            config = load_config(config_path)
        except Exception as exc:
            print(f"[-] Failed to reload config: {exc}")
            return 1

        interval = interval_override or config["check_interval_minutes"]
        print(f"[*] Sleeping for {interval} minute(s).")
        if exit_code:
            print("[!] Previous scan had errors.")
        time.sleep(interval * 60)
