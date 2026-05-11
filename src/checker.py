"""
VFS slot checker — supports multiple accounts.

Iterates through configured accounts, returns on first success.
Records each attempt to check_history for the dashboard.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import (
    BrowserContext,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PWTimeout,
)

from . import database as db
from .config import HEADLESS, SESSIONS_DIR, VFS_URL, Account, load_accounts

log = logging.getLogger(__name__)


NO_SLOTS_PHRASES = [
    "no appointment slots are currently available",
    "no slots available",
    "no dates are available",
    "no appointments available",
    "currently, there are no slots open",
    "appointment slots are not available",
    "no appointment is available",
]

LOGIN_INDICATORS = ["password", "sign in", "log in"]

APPOINTMENT_HINTS = [
    "Schedule Appointment",
    "Book Appointment",
    "New Appointment",
    "Start New Application",
]

CALENDAR_SELECTORS = [
    ".calendar",
    "[class*='calendar']",
    "[class*='date-picker']",
    "input[type='date']",
    "[class*='appointment-slot']",
    "[class*='available-date']",
]


@dataclass
class CheckResult:
    account: str
    available: bool
    message: str
    duration_ms: int
    session_expired: bool = False


async def _save_session(context: BrowserContext, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    await context.storage_state(path=path)


async def interactive_login(account_name: str = "primary") -> None:
    """One-off: open a real browser, user logs in manually, session saved."""
    session_path = f"{SESSIONS_DIR}/{account_name}.json"
    Path(SESSIONS_DIR).mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(VFS_URL)
        print("\n" + "=" * 70)
        print(f"Account: {account_name}")
        print("Log in manually in the opened browser. Solve any CAPTCHA.")
        print("Click around enough to reach the booking page (so cookies set).")
        print("Then return here and press Enter to save the session.")
        print("=" * 70 + "\n")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, input, "Press Enter once logged in: ")
        await _save_session(context, session_path)
        print(f"Session saved → {session_path}")
        await browser.close()


async def _check_one(account: Account) -> CheckResult:
    start = time.monotonic()
    session_path = Path(account.session_path)
    if not session_path.exists():
        return CheckResult(
            account.name, False,
            f"No saved session for {account.name} — run `python -m src.cli login --account {account.name}`",
            int((time.monotonic() - start) * 1000),
            session_expired=True,
        )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(storage_state=str(session_path))
        page = await context.new_page()
        try:
            await page.goto(VFS_URL, wait_until="networkidle", timeout=60_000)
            await page.wait_for_timeout(3_000)

            content = (await page.content()).lower()
            url = page.url.lower()

            if "login" in url and any(s in content for s in LOGIN_INDICATORS):
                return CheckResult(
                    account.name, False,
                    f"Session expired for {account.name} — re-login needed",
                    int((time.monotonic() - start) * 1000),
                    session_expired=True,
                )

            # Try to click into appointment booking
            for hint in APPOINTMENT_HINTS:
                try:
                    btn = page.get_by_text(hint, exact=False).first
                    if await btn.is_visible(timeout=2_000):
                        await btn.click()
                        await page.wait_for_load_state("networkidle", timeout=30_000)
                        break
                except (PWTimeout, Exception):
                    continue

            await page.wait_for_timeout(2_000)
            content = (await page.content()).lower()

            for phrase in NO_SLOTS_PHRASES:
                if phrase in content:
                    return CheckResult(
                        account.name, False,
                        f"No slots (matched: '{phrase}')",
                        int((time.monotonic() - start) * 1000),
                    )

            for sel in CALENDAR_SELECTORS:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        return CheckResult(
                            account.name, True,
                            f"Possible slot — calendar visible ({sel})",
                            int((time.monotonic() - start) * 1000),
                        )
                except Exception:
                    continue

            return CheckResult(
                account.name, False,
                "Ambiguous: no 'no slots' text and no calendar found",
                int((time.monotonic() - start) * 1000),
            )

        except PWTimeout as e:
            return CheckResult(
                account.name, False,
                f"Timeout: {e}",
                int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            log.exception("Checker crashed for %s", account.name)
            return CheckResult(
                account.name, False,
                f"Error: {e}",
                int((time.monotonic() - start) * 1000),
            )
        finally:
            await context.close()
            await browser.close()


async def check_all_accounts() -> tuple[CheckResult | None, list[CheckResult]]:
    """
    Check every enabled account. Returns (winner, all_results) where winner is
    the first result that found slots, or None.
    """
    accounts = load_accounts()
    if not accounts:
        # Fall back to single anonymous account using legacy session path
        accounts = [
            Account(name="default", email="", session_path="vfs_session.json", enabled=True)
        ]

    results: list[CheckResult] = []
    winner: CheckResult | None = None

    for account in accounts:
        result = await _check_one(account)
        results.append(result)
        await db.record_check(
            account_name=result.account,
            available=result.available,
            message=result.message,
            duration_ms=result.duration_ms,
        )
        if result.available and winner is None:
            winner = result
            # Don't break — finish recording all accounts for visibility,
            # but we won't double-notify because we use the winner.

    return winner, results
