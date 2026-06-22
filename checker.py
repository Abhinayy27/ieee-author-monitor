#!/usr/bin/env python3
"""
IEEE Author Profile Monitor

Monitors an IEEE Xplore author profile for new publications
and sends an email notification when the publication count increases.
"""

import json
import logging
import os
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# Configuration
TARGET_URL = "https://ieeexplore.ieee.org/author/113479857928040"
STATE_FILE = "state.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SUBJECT = "New IEEE Publication Detected"
RECIPIENT_EMAIL = "babhinay27@gmail.com"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning(
        "Playwright not available. JavaScript-rendered content may not load properly."
    )


def load_state() -> Dict:
    """Load state from state.json file."""
    state_file = Path(STATE_FILE)
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                if "publication_count" in state:
                    return state
                logger.info("Migrating from old state format; will re-baseline on next run.")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error reading state file: {e}. Will create new state.")

    return {}


def save_state(state: Dict) -> None:
    """Save state to state.json file."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        logger.info(
            f"State saved: publication_count={state.get('publication_count', 'unknown')}"
        )
    except IOError as e:
        logger.error(f"Error saving state file: {e}")
        raise


def fetch_page(url: str) -> Optional[str]:
    """Fetch the target page, using Playwright if available for JS-rendered content."""
    if PLAYWRIGHT_AVAILABLE:
        try:
            logger.info(f"Fetching page with Playwright: {url}")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=USER_AGENT,
                    locale="en-US",
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                try:
                    page.wait_for_selector(
                        "div.publications.col-12 div.pub-citation-count",
                        timeout=15000,
                    )
                except Exception:
                    logger.warning("Timeout waiting for publication count, continuing")
                page.wait_for_timeout(3000)
                html_content = page.content()
                browser.close()
            logger.info(f"Fetched page with Playwright ({len(html_content)} bytes)")
            return html_content
        except Exception as e:
            logger.warning(f"Playwright fetch failed: {e}. Falling back to requests.")

    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://ieeexplore.ieee.org/",
        }
        logger.info(f"Fetching page with requests: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching page: {e}")
        return None


def parse_publication_count(html_content: str) -> Optional[int]:
    """Extract the publication count from the author profile page."""
    soup = BeautifulSoup(html_content, "html.parser")
    pub_div = soup.select_one("div.publications.col-12")
    if not pub_div:
        logger.warning("Could not find publications section on page")
        return None

    count_el = pub_div.select_one("div.pub-citation-count")
    if not count_el:
        logger.warning("Could not find publication count element")
        return None

    try:
        return int(count_el.get_text(strip=True))
    except ValueError:
        logger.warning(f"Invalid publication count: {count_el.get_text(strip=True)!r}")
        return None


def parse_publication_titles(html_content: str) -> List[str]:
    """Extract publication titles from document links on the author page."""
    soup = BeautifulSoup(html_content, "html.parser")
    titles: List[str] = []
    seen = set()

    for link in soup.select('a[href*="document"]'):
        title = link.get_text(strip=True)
        if len(title) < 30:
            continue
        key = title.lower()
        if key not in seen:
            seen.add(key)
            titles.append(title)

    return titles


def send_notification(
    previous_count: int,
    current_count: int,
    new_titles: List[str],
    all_titles: List[str],
) -> bool:
    """Send email notification via Gmail SMTP."""
    email_address = os.getenv("EMAIL_ADDRESS")
    email_password = os.getenv("EMAIL_APP_PASSWORD")

    if not email_address or not email_password:
        logger.error("Email credentials not found in environment variables")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = email_address
        msg["To"] = RECIPIENT_EMAIL
        msg["Subject"] = EMAIL_SUBJECT

        new_titles_text = (
            "\n".join(f"- {title}" for title in new_titles)
            if new_titles
            else "- (title could not be determined automatically)"
        )
        all_titles_text = (
            "\n".join(f"- {title}" for title in all_titles)
            if all_titles
            else "- (none found)"
        )

        body = f"""A new publication was detected on the monitored IEEE author profile.

Author profile: {TARGET_URL}

Publication count: {previous_count} -> {current_count}

New publication(s):
{new_titles_text}

All publications currently listed:
{all_titles_text}

---
This is an automated notification from the IEEE author profile monitoring agent.
"""

        msg.attach(MIMEText(body, "plain"))

        logger.info(f"Sending email to {RECIPIENT_EMAIL}")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)

        logger.info("Email sent successfully")
        return True

    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False


def main() -> int:
    """Main function to orchestrate the monitoring process."""
    try:
        state = load_state()
        html_content = fetch_page(TARGET_URL)
        if not html_content:
            logger.error("Failed to fetch page. Exiting.")
            return 1

        current_count = parse_publication_count(html_content)
        if current_count is None:
            logger.error("Failed to parse publication count. Exiting.")
            return 1

        current_titles = parse_publication_titles(html_content)
        logger.info(f"Current publication count: {current_count}")
        for i, title in enumerate(current_titles, 1):
            logger.info(f"  Publication {i}: {title[:120]}")

        stored_count = state.get("publication_count")
        stored_titles = state.get("publication_titles", [])

        if stored_count is None:
            state = {
                "publication_count": current_count,
                "publication_titles": current_titles,
            }
            save_state(state)
            logger.info(
                f"Initialized baseline with {current_count} publication(s). "
                "You will be notified when the count increases."
            )
            return 0

        if current_count > stored_count:
            stored_title_keys = {title.lower() for title in stored_titles}
            new_titles = [
                title
                for title in current_titles
                if title.lower() not in stored_title_keys
            ]
            logger.info(
                f"Publication count increased: {stored_count} -> {current_count}"
            )

            email_sent = send_notification(
                stored_count, current_count, new_titles, current_titles
            )
            state["publication_count"] = current_count
            state["publication_titles"] = current_titles
            save_state(state)

            if email_sent:
                logger.info("Notification sent and state updated")
                return 0

            logger.error("Email failed but state was updated to avoid duplicate alerts")
            return 1

        if current_count < stored_count:
            logger.warning(
                f"Publication count decreased ({stored_count} -> {current_count}). "
                "Updating state without sending notification."
            )
            state["publication_count"] = current_count
            state["publication_titles"] = current_titles
            save_state(state)
            return 0

        logger.info(f"No change in publication count ({current_count})")
        return 0

    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
