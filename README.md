# shengen_bot

> Telegram bot that monitors **VFS Global Baku** for open Italian Schengen visa appointment slots and alerts subscribers the moment one appears.

[![CI](https://github.com/valehdba/shengen_bot/actions/workflows/ci.yml/badge.svg)](https://github.com/valehdba/shengen_bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

> 📖 **New here?** Read **[INSTALL.md](INSTALL.md)** for a complete step-by-step setup walkthrough — no prior experience needed.

## Features

- 🤖 **Telegram bot** with `/subscribe`, `/check`, `/status`, `/help`
- 👥 **Multi-account** — round-robin checks across multiple VFS accounts
- 📊 **Web dashboard** — live stats, check history, account status (FastAPI + basic auth)
- 🛠️ **Admin commands** — `/stats`, `/accounts`, `/broadcast`
- 🐳 **Docker-ready** — one command to deploy bot + dashboard
- 🧪 **Tested** — CI runs pytest + ruff on every push
- 🔐 **Session-expired alerts** — get pinged on Telegram when re-login is needed
- 🤖 **Optional 2Captcha hook** — experimental auto-CAPTCHA solving

## Important caveats

1. **Sessions require manual login.** VFS Global uses Cloudflare + CAPTCHA. You log in once with a real browser; the bot reuses the cookies. When sessions expire, you get an admin alert on Telegram.
2. **Be respectful.** Keep `CHECK_INTERVAL_MINUTES >= 5`. Hammering VFS will get you blocked.
3. **Heuristic detection.** The checker looks for "no slots" phrases and visible calendars. VFS occasionally changes their UI — see [Tuning](#tuning) below.
4. **First-time tourist slots for Italy are scarce.** The bot improves your odds, but can't create slots that don't exist.

## Quickstart (Docker — recommended)

```bash
git clone https://github.com/valehdba/shengen_bot.git
cd shengen_bot

cp .env.example .env
# Edit .env — set TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID, DASHBOARD_PASSWORD, DASHBOARD_SECRET

cp accounts.example.json accounts.json
# Edit accounts.json with your VFS account names

# One-off login for each account (opens a real browser, not in Docker)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python -m src.cli login --account primary

# Start the stack
docker compose up -d

# Watch logs
docker compose logs -f bot
```

Dashboard: http://localhost:8000 (username/password from `.env`)

## Quickstart (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env                # edit it
cp accounts.example.json accounts.json   # edit it

python -m src.cli login --account primary   # interactive login

# In one terminal:
python -m src.bot

# In another (optional):
python -m src.dashboard
```

## Commands

### User
| Command | Description |
|---|---|
| `/start`, `/help` | Show help |
| `/subscribe` | Receive alerts when slots open |
| `/unsubscribe` | Stop alerts |
| `/check` | Run a check right now (~30s) |
| `/status` | Your subscription + last result + 24h stats |

### Admin (only `ADMIN_TELEGRAM_ID`)
| Command | Description |
|---|---|
| `/stats` | Subscriber counts + 24h/7d check stats |
| `/accounts` | List configured accounts and their session status |
| `/broadcast <msg>` | Send message to all subscribers |

## Multi-account setup

Edit `accounts.json`:

```json
[
  { "name": "primary",  "email": "you@example.com", "session_path": "sessions/primary.json", "enabled": true },
  { "name": "backup",   "email": "you+2@example.com", "session_path": "sessions/backup.json", "enabled": true }
]
```

Then log in to each:

```bash
python -m src.cli login --account primary
python -m src.cli login --account backup
```

The checker iterates accounts on every tick. If any one finds slots, all subscribers are notified.

## Dashboard

Lives at `http://<host>:8000`. Shows:
- Subscriber count, last check, current slot status
- Per-account session status (saved / missing)
- Last 50 checks with timestamps and durations
- 24h and 7d aggregate stats

Auto-refreshes every 30 seconds. Protected by HTTP basic auth.

## Tuning the checker

VFS changes its UI periodically. If you see false positives or negatives, edit `src/checker.py`:

- `NO_SLOTS_PHRASES` — strings VFS shows when no appointments exist
- `CALENDAR_SELECTORS` — CSS selectors for the date picker
- `APPOINTMENT_HINTS` — button text to click into the booking flow

To debug interactively, run with `HEADLESS=false` and watch the browser:

```bash
HEADLESS=false python -m src.cli check
```

## 2Captcha (experimental)

Set `TWOCAPTCHA_API_KEY` in `.env` to enable. The `src/captcha.py` module is a hook; integrating it with VFS's specific challenge requires inspecting their CAPTCHA implementation and calling `CaptchaSolver().solve_recaptcha_v2(...)` at the right point in the login flow. **The default flow (Telegram alert + manual re-login) is more reliable.**

## Project structure

```
shengen_bot/
├── .github/workflows/ci.yml      # lint + test + docker build
├── src/
│   ├── bot.py                    # Telegram handlers + scheduler
│   ├── checker.py                # Playwright VFS checker (multi-account)
│   ├── dashboard.py              # FastAPI dashboard
│   ├── database.py               # SQLite (subscribers, history, state)
│   ├── captcha.py                # Optional 2Captcha integration
│   ├── config.py                 # .env + accounts.json loader
│   └── cli.py                    # login / check / stats commands
├── tests/test_database.py
├── templates/dashboard.html
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── accounts.example.json
├── requirements.txt
└── README.md
```

## Production deployment (VPS)

```bash
# SSH to your VPS
git clone https://github.com/valehdba/shengen_bot.git
cd shengen_bot

# Set up env & accounts as above

# Do the login on your local machine (needs a GUI), then scp the session files:
scp sessions/*.json user@vps:/path/to/shengen_bot/sessions/

# On the VPS:
docker compose up -d
```

When sessions expire, you'll get a Telegram alert. SSH in, scp fresh sessions, and:

```bash
docker compose restart bot
```

## Privacy & legal

- The bot stores only chat IDs and (optional) usernames locally in SQLite.
- VFS Global's Terms of Service may prohibit automated access. Use at your own risk. This is a personal monitoring tool, not a commercial service.
- Never share `.env`, `accounts.json`, or `sessions/` — they contain credentials and cookies. `.gitignore` excludes them already.

## Contributing

PRs welcome. Run before committing:

```bash
pip install -r requirements-dev.txt
ruff check src/ tests/
pytest -q
```

## License

[MIT](LICENSE) © valehdba
