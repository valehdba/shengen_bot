"""
Web dashboard — FastAPI + Jinja2 + basic auth.

Shows: subscriber count, last check, recent check history, per-account status.
Auto-refreshes every 30s.
"""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config
from . import database as db

app = FastAPI(title="Italy Visa Slot Bot")
security = HTTPBasic()

# Templates and static both relative to project root
ROOT = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))
static_dir = ROOT / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def _auth(creds: Annotated[HTTPBasicCredentials, Depends(security)]) -> str:
    u_ok = secrets.compare_digest(creds.username, config.DASHBOARD_USERNAME)
    p_ok = secrets.compare_digest(creds.password, config.DASHBOARD_PASSWORD)
    if not (u_ok and p_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return creds.username


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user: Annotated[str, Depends(_auth)]):
    total = await db.count_active()
    last_check = await db.get_state("last_check_at") or "never"
    last_msg = await db.get_state("last_check_message") or "—"
    last_avail = (await db.get_state("last_available")) == "1"
    stats_24h = await db.check_stats(24)
    stats_7d = await db.check_stats(24 * 7)
    history = await db.recent_checks(50)
    subscribers = await db.list_subscribers(50)
    accounts = config.load_accounts()
    account_status = []
    for a in accounts:
        account_status.append({
            "name": a.name,
            "email": a.email,
            "session_exists": Path(a.session_path).exists(),
            "enabled": a.enabled,
        })

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "total": total,
            "last_check": last_check,
            "last_msg": last_msg,
            "last_avail": last_avail,
            "stats_24h": stats_24h,
            "stats_7d": stats_7d,
            "history": history,
            "subscribers": subscribers,
            "accounts": account_status,
            "interval": config.CHECK_INTERVAL_MINUTES,
        },
    )


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/api/stats")
async def api_stats(user: Annotated[str, Depends(_auth)]):
    return {
        "subscribers": await db.count_active(),
        "last_check": await db.get_state("last_check_at"),
        "last_message": await db.get_state("last_check_message"),
        "slots_available": (await db.get_state("last_available")) == "1",
        "stats_24h": await db.check_stats(24),
        "stats_7d": await db.check_stats(24 * 7),
    }


def run() -> None:
    import uvicorn
    config.configure_logging()
    uvicorn.run(
        "src.dashboard:app",
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        reload=False,
    )


if __name__ == "__main__":
    run()
