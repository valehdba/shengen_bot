"""
Telegram bot for Italy Schengen visa slot monitoring.

Commands (user):
  /start, /help, /subscribe, /unsubscribe, /status, /check
Commands (admin only):
  /stats, /broadcast <msg>, /accounts
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from . import config
from . import database as db
from .checker import check_all_accounts

log = logging.getLogger("shengen_bot")

HELP_TEXT = (
    "🇮🇹 *Italy Schengen Visa Slot Bot — Baku*\n\n"
    "I monitor VFS Global Baku for open Italy visa appointment slots.\n\n"
    "*Commands*\n"
    "/subscribe — get alerts when slots open\n"
    "/unsubscribe — stop alerts\n"
    "/check — manual check now (slow, ~30s)\n"
    "/status — your subscription + last result\n"
    "/help — this message\n\n"
    "_Unofficial helper. Confirm and book on the_ "
    "[official VFS site](https://visa.vfsglobal.com/aze/en/ita)."
)


def _is_admin(update: Update) -> bool:
    if not config.ADMIN_TELEGRAM_ID:
        return False
    user = update.effective_user
    return bool(user and str(user.id) == config.ADMIN_TELEGRAM_ID)


# ---------- user commands ----------

async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        HELP_TEXT, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
    )


async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        HELP_TEXT, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
    )


async def cmd_subscribe(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else None
    added = await db.add_subscriber(chat_id, username)
    total = await db.count_active()
    msg = (
        f"✅ Subscribed. I'll ping you when slots open.\nActive subscribers: {total}"
        if added
        else "You're already subscribed."
    )
    await update.message.reply_text(msg)


async def cmd_unsubscribe(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await db.remove_subscriber(update.effective_chat.id)
    await update.message.reply_text("🔕 Unsubscribed. Send /subscribe to re-enable.")


async def cmd_status(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    active = await db.get_active_subscribers()
    is_sub = chat_id in active
    last_check = await db.get_state("last_check_at") or "never"
    last_msg = await db.get_state("last_check_message") or "—"
    stats = await db.check_stats(24)
    await update.message.reply_text(
        f"You: {'✅ subscribed' if is_sub else '❌ not subscribed'}\n"
        f"Subscribers: {len(active)}\n"
        f"Last check: {last_check}\n"
        f"Last result: {last_msg}\n\n"
        f"📊 24h: {stats['total']} checks, {stats['hits']} hits, "
        f"avg {stats['avg_ms']}ms"
    )


async def cmd_check(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔍 Checking now…")
    winner, all_results = await check_all_accounts()
    lines = []
    for r in all_results:
        icon = "🟢" if r.available else "🔴"
        lines.append(f"{icon} [{r.account}] {r.message} ({r.duration_ms}ms)")
    summary = "\n".join(lines) or "No accounts configured."
    if winner:
        summary = "🟢 *SLOTS POSSIBLY OPEN*\n\n" + summary
    await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN)


# ---------- admin commands ----------

async def cmd_stats(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    total = await db.count_active()
    s24 = await db.check_stats(24)
    s7d = await db.check_stats(24 * 7)
    await update.message.reply_text(
        "*Admin stats*\n"
        f"Active subscribers: {total}\n\n"
        f"*Last 24h*: {s24['total']} checks, {s24['hits']} hits, avg {s24['avg_ms']}ms\n"
        f"*Last 7d*: {s7d['total']} checks, {s7d['hits']} hits, avg {s7d['avg_ms']}ms",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_accounts(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    from pathlib import Path

    from .config import load_accounts
    accounts = load_accounts()
    if not accounts:
        await update.message.reply_text("No accounts configured (using default fallback).")
        return
    lines = ["*Accounts:*"]
    for a in accounts:
        exists = "✅" if Path(a.session_path).exists() else "❌"
        lines.append(f"{exists} `{a.name}` — {a.email or '(no email)'}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    msg = " ".join(ctx.args) if ctx.args else ""
    if not msg:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    subs = await db.get_active_subscribers()
    sent = 0
    for cid in subs:
        try:
            await ctx.bot.send_message(cid, f"📢 {msg}")
            sent += 1
        except Exception as e:
            log.warning("Broadcast to %s failed: %s", cid, e)
    await update.message.reply_text(f"Sent to {sent}/{len(subs)} subscribers.")


# ---------- background work ----------

async def _notify_subscribers(app: Application, detail: str) -> None:
    chat_ids = await db.get_active_subscribers()
    log.info("Broadcasting slot alert to %d subscribers", len(chat_ids))
    text = (
        "🟢 *Italy visa slot likely available!*\n\n"
        f"{detail}\n\n"
        "👉 Book NOW: https://visa.vfsglobal.com/aze/en/ita\n"
        "_Slots disappear in minutes._"
    )
    for cid in chat_ids:
        try:
            await app.bot.send_message(cid, text, parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.05)  # gentle rate-limit
        except Exception as e:
            log.warning("Notify %s failed: %s", cid, e)


async def _notify_admin(app: Application, text: str) -> None:
    if not config.ADMIN_TELEGRAM_ID:
        return
    try:
        await app.bot.send_message(int(config.ADMIN_TELEGRAM_ID), f"🛠️ {text}")
    except Exception as e:
        log.warning("Admin notify failed: %s", e)


async def scheduled_check(app: Application) -> None:
    log.info("Scheduled check starting")
    try:
        winner, all_results = await check_all_accounts()
    except Exception as e:
        log.exception("Checker crashed")
        await _notify_admin(app, f"Checker crashed: {e}")
        return

    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    summary = "; ".join(f"[{r.account}] {r.message}" for r in all_results) or "no accounts"
    await db.set_state("last_check_at", now)
    await db.set_state("last_check_message", summary[:500])

    # Session-expired alerts (admin only, once per state change)
    expired_accounts = [r for r in all_results if r.session_expired]
    last_expired = await db.get_state("last_expired_accounts") or ""
    cur_expired = ",".join(sorted(r.account for r in expired_accounts))
    if cur_expired and cur_expired != last_expired:
        await _notify_admin(
            app,
            f"Session expired for: {cur_expired}. "
            f"Run `python -m src.cli login --account <name>` to re-login.",
        )
    await db.set_state("last_expired_accounts", cur_expired)

    # Slot transition notify
    prev = await db.get_state("last_available") or "0"
    cur = "1" if winner else "0"
    await db.set_state("last_available", cur)
    if winner and prev != "1":
        await _notify_subscribers(app, winner.message)
    else:
        log.info("Result: available=%s | %s", bool(winner), summary)


async def post_init(app: Application) -> None:
    config.configure_logging()
    await db.init_db()
    log.info("DB ready")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_check, "interval",
        minutes=config.CHECK_INTERVAL_MINUTES,
        args=[app],
        next_run_time=datetime.now(),
    )
    scheduler.start()
    app.bot_data["scheduler"] = scheduler
    log.info("Scheduler running every %s min", config.CHECK_INTERVAL_MINUTES)
    await _notify_admin(app, "Bot started ✅")


def build_app() -> Application:
    config.validate()
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    # user
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("check", cmd_check))
    # admin
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("accounts", cmd_accounts))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    return app


def main() -> None:
    config.configure_logging()
    app = build_app()
    log.info("Bot starting…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
