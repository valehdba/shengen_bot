"""
Optional 2Captcha integration for auto-relogin.

Status: experimental. Cloudflare's bot detection looks at many signals beyond
just CAPTCHA, so even a solved CAPTCHA may not get you logged in. The bot's
default behavior is to alert you on Telegram when a session expires so you can
re-login manually. Use this only if you understand the risks.

API docs: https://2captcha.com/2captcha-api
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from .config import TWOCAPTCHA_API_KEY

log = logging.getLogger(__name__)

API_BASE = "https://2captcha.com"


class CaptchaSolver:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or TWOCAPTCHA_API_KEY
        self.enabled = bool(self.api_key)

    async def solve_recaptcha_v2(self, site_key: str, page_url: str) -> str | None:
        """Returns g-recaptcha-response token, or None on failure."""
        if not self.enabled:
            log.debug("2Captcha not configured — skipping CAPTCHA solve")
            return None

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{API_BASE}/in.php",
                data={
                    "key": self.api_key,
                    "method": "userrecaptcha",
                    "googlekey": site_key,
                    "pageurl": page_url,
                    "json": 1,
                },
            )
            data = r.json()
            if data.get("status") != 1:
                log.error("2Captcha submit failed: %s", data)
                return None
            captcha_id = data["request"]

            # Poll for result (typical solve time 15-60s)
            for _ in range(40):  # up to ~2 minutes
                await asyncio.sleep(3)
                r = await client.get(
                    f"{API_BASE}/res.php",
                    params={
                        "key": self.api_key,
                        "action": "get",
                        "id": captcha_id,
                        "json": 1,
                    },
                )
                d = r.json()
                if d.get("status") == 1:
                    log.info("2Captcha solved CAPTCHA %s", captcha_id)
                    return d["request"]
                if d.get("request") != "CAPCHA_NOT_READY":
                    log.error("2Captcha failed: %s", d)
                    return None
            log.error("2Captcha timed out for %s", captcha_id)
            return None

    async def balance(self) -> float | None:
        if not self.enabled:
            return None
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{API_BASE}/res.php",
                params={"key": self.api_key, "action": "getbalance", "json": 1},
            )
            data = r.json()
            if data.get("status") == 1:
                return float(data["request"])
            return None
