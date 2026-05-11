"""CLI: python -m src.cli login --account primary | check | stats"""
from __future__ import annotations

import argparse
import asyncio

from . import config
from . import database as db
from .checker import check_all_accounts, interactive_login


async def cmd_login(account: str) -> None:
    config.ensure_dirs()
    await interactive_login(account)


async def cmd_check() -> None:
    config.ensure_dirs()
    await db.init_db()
    winner, results = await check_all_accounts()
    for r in results:
        icon = "🟢" if r.available else "🔴"
        print(f"{icon} [{r.account}] {r.message} ({r.duration_ms}ms)")
    print("→ slots available" if winner else "→ no slots")


async def cmd_stats() -> None:
    await db.init_db()
    s24 = await db.check_stats(24)
    s7d = await db.check_stats(24 * 7)
    n = await db.count_active()
    print(f"Subscribers: {n}")
    print(f"24h: {s24}")
    print(f"7d:  {s7d}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="shengen-bot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_login = sub.add_parser("login", help="Interactive VFS login")
    p_login.add_argument("--account", default="primary")

    sub.add_parser("check", help="Run a single slot check now")
    sub.add_parser("stats", help="Show subscriber + check stats")

    args = parser.parse_args()
    config.configure_logging()

    if args.cmd == "login":
        asyncio.run(cmd_login(args.account))
    elif args.cmd == "check":
        asyncio.run(cmd_check())
    elif args.cmd == "stats":
        asyncio.run(cmd_stats())


if __name__ == "__main__":
    main()
