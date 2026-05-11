# Installation & Usage Guide

A complete walkthrough — no prior experience required. Follow it top-to-bottom.

> If you get stuck on any step, the line number and the exact error message are usually all anyone needs to help you. Don't skip steps.

---

## Table of Contents

1. [What you'll end up with](#1-what-youll-end-up-with)
2. [Prerequisites](#2-prerequisites)
3. [Get the code](#3-get-the-code)
4. [Create your Telegram bot](#4-create-your-telegram-bot)
5. [Get your admin Telegram ID](#5-get-your-admin-telegram-id)
6. [Install Python dependencies](#6-install-python-dependencies)
7. [Install the browser engine](#7-install-the-browser-engine)
8. [Configure `.env`](#8-configure-env)
9. [Configure `accounts.json`](#9-configure-accountsjson)
10. [First-time VFS login](#10-first-time-vfs-login)
11. [Run the bot](#11-run-the-bot)
12. [Run the web dashboard](#12-run-the-web-dashboard)
13. [Using the bot day-to-day](#13-using-the-bot-day-to-day)
14. [Deploying with Docker](#14-deploying-with-docker)
15. [Deploying to a VPS for 24/7 operation](#15-deploying-to-a-vps-for-247-operation)
16. [Handling expired VFS sessions](#16-handling-expired-vfs-sessions)
17. [Updating the code](#17-updating-the-code)
18. [Troubleshooting](#18-troubleshooting)
19. [Uninstalling](#19-uninstalling)

---

## 1. What you'll end up with

- A Telegram bot that you and your friends can chat with (`/subscribe` to opt in)
- Background checks every 10 minutes against VFS Global Baku
- Instant Telegram notification when an Italy Schengen slot appears
- A web dashboard at `http://localhost:8000` showing live stats
- All running either on your own laptop or on a small VPS

---

## 2. Prerequisites

You need three things installed on your computer:

### Python 3.10 or newer
Check what you have:
```bash
python3 --version
```
If it prints `Python 3.10.x` or higher, you're set. Otherwise:
- **macOS**: `brew install python@3.11`
- **Ubuntu/Debian**: `sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip`
- **Windows**: Download from https://www.python.org/downloads/ — **check "Add Python to PATH"** during install

### Git
```bash
git --version
```
- **macOS**: comes with Xcode tools; if missing run `xcode-select --install`
- **Ubuntu/Debian**: `sudo apt install -y git`
- **Windows**: https://git-scm.com/download/win

### A Telegram account
On your phone or desktop. Free.

### Optional (only for production deployment)
- **Docker Desktop**: https://www.docker.com/products/docker-desktop/ — needed if you want section 14
- **A VPS** with SSH access (Hetzner, DigitalOcean, etc.) — needed for section 15

---

## 3. Get the code

### Option A — Download the zip
1. Download `shengen_bot.zip`
2. Unzip it somewhere you can find again, e.g. your home folder
3. Open a terminal in that folder:
   - **macOS/Linux**: `cd ~/shengen_bot`
   - **Windows (PowerShell)**: `cd $HOME\shengen_bot`

### Option B — Clone from GitHub (after you push to your repo)
```bash
git clone https://github.com/valehdba/shengen_bot.git
cd shengen_bot
```

Verify you're in the right place:
```bash
ls          # macOS/Linux
dir         # Windows
```
You should see `Dockerfile`, `README.md`, `src/`, `requirements.txt` and friends.

---

## 4. Create your Telegram bot

1. Open Telegram, search for **@BotFather**, start a chat
2. Send `/newbot`
3. Pick a **name** (e.g. "Italy Visa Slot Bot") — shown in chat header
4. Pick a **username** ending in `bot` (e.g. `italy_visa_slot_bot`) — must be unique
5. BotFather replies with a token that looks like this:
   ```
   7891234567:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
6. **Copy it. You'll paste it into `.env` shortly.** Don't share it publicly — anyone with this token controls your bot.

While you're here, optional but nice:
- `/setdescription` — what shows when someone opens your bot fresh
- `/setcommands` — paste this to populate the menu:
  ```
  subscribe - Get alerts when slots open
  unsubscribe - Stop alerts
  check - Check now (slow ~30s)
  status - Your subscription + last result
  help - Show commands
  ```

---

## 5. Get your admin Telegram ID

The bot uses this to know who can run admin commands (`/stats`, `/broadcast`) and where to send session-expired alerts.

1. In Telegram, find **@userinfobot**, start chat, send `/start`
2. It replies with your numeric ID, e.g. `123456789`
3. Save it — you'll paste it into `.env`

---

## 6. Install Python dependencies

In your terminal, inside the `shengen_bot` folder:

### Create a virtual environment (isolates dependencies)
```bash
# macOS/Linux:
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell):
python -m venv .venv
.venv\Scripts\Activate.ps1
```

You should see `(.venv)` appear at the start of your prompt. **Keep this terminal open** for the rest of setup; whenever you reopen it, re-run the activate line.

### Install the libraries
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This downloads about 80 MB and takes 1–3 minutes. When it finishes, run:
```bash
python -c "import telegram, playwright, fastapi; print('ok')"
```
If it prints `ok`, you're good.

---

## 7. Install the browser engine

The bot drives a real Chromium browser to bypass VFS's bot protection. One command installs it:

```bash
playwright install chromium
```

This downloads ~150 MB. On Linux you may also need:
```bash
playwright install-deps chromium
```
which uses `sudo` to install system libraries Chromium needs. macOS and Windows users skip this.

---

## 8. Configure `.env`

Copy the template:
```bash
# macOS/Linux:
cp .env.example .env

# Windows:
copy .env.example .env
```

Open `.env` in any text editor (VS Code, Notepad, nano, vim — anything). Fill in:

```env
# Paste the token from BotFather (section 4)
TELEGRAM_BOT_TOKEN=7891234567:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Paste your numeric ID from @userinfobot (section 5)
ADMIN_TELEGRAM_ID=123456789

# Leave this — it's the official Italy/Baku URL
VFS_URL=https://visa.vfsglobal.com/aze/en/ita/login

# How often to check. 10 is sensible. Don't go below 5.
CHECK_INTERVAL_MINUTES=10

# 'true' for servers, 'false' to watch the browser work (good for debugging)
HEADLESS=true

# Dashboard login — change these
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=pick-something-strong
```

Generate a strong dashboard secret (used to sign session cookies):
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Copy the output, paste it as `DASHBOARD_SECRET=...` in `.env`.

Save and close.

---

## 9. Configure `accounts.json`

This file tells the checker which VFS accounts to log into. Even if you only have one, you need to define it.

```bash
# macOS/Linux:
cp accounts.example.json accounts.json

# Windows:
copy accounts.example.json accounts.json
```

Open `accounts.json`. For a single account, simplify it to:

```json
[
  {
    "name": "primary",
    "email": "you@example.com",
    "session_path": "sessions/primary.json",
    "enabled": true,
    "notes": "Main account"
  }
]
```

If you have multiple VFS accounts, add more entries — each gets its own `session_path`. The `email` field is just a label; the bot doesn't use it to log in (you'll do that manually in the next step).

Save and close.

---

## 10. First-time VFS login

This is the one manual step. You log in once with a real browser; the bot saves the cookies and reuses them.

Make sure your virtual environment is still active (`(.venv)` in prompt), then:

```bash
python -m src.cli login --account primary
```

What happens:
1. A real Chromium window opens on your screen, loading `visa.vfsglobal.com/aze/en/ita/login`
2. Log in with your VFS email and password
3. Solve the CAPTCHA if shown
4. Click through to the booking page — go as far as the "Schedule Appointment" screen
5. **Switch back to your terminal and press Enter**
6. You'll see `Session saved → sessions/primary.json`

The browser closes. Your session is stored.

**If you have multiple accounts:** repeat with `--account backup`, `--account third`, etc.

### Verify the session works
```bash
python -m src.cli check
```

Possible outputs:
- `🔴 [primary] No slots (matched: '...')` → session works, no slots right now ✅
- `🟢 [primary] Possible slot — calendar visible` → session works, slots open ✅
- `🔴 [primary] Session expired for primary` → session didn't save properly; redo step 10
- Long error → see [Troubleshooting](#18-troubleshooting)

---

## 11. Run the bot

```bash
python -m src.bot
```

You should see logs like:
```
2026-05-11 12:30:00 [INFO] shengen_bot: DB ready
2026-05-11 12:30:00 [INFO] shengen_bot: Scheduler running every 10 min
2026-05-11 12:30:00 [INFO] shengen_bot: Bot starting…
2026-05-11 12:30:01 [INFO] shengen_bot: Scheduled check starting
```

The bot is now live on Telegram.

### Test it
1. Open Telegram, find your bot (search for the username you picked)
2. Send `/start` — should reply with the help text
3. Send `/subscribe` — confirms subscription
4. Send `/check` — runs a check manually (~30s, watch terminal for activity)

To stop the bot: `Ctrl+C` in the terminal.

---

## 12. Run the web dashboard

Open a **second** terminal (the bot stays running in the first one). Navigate to the project and activate the venv again:

```bash
cd path/to/shengen_bot
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
python -m src.dashboard
```

You'll see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Open http://localhost:8000 in a browser. You'll be prompted for the username and password you set in `.env`. After login, you see:

- Subscriber count, last check time, slot status
- Per-account session status (✅ saved / ❌ missing)
- Last 50 checks with timestamps
- 24-hour and 7-day statistics

The dashboard auto-refreshes every 30 seconds.

To stop the dashboard: `Ctrl+C` in its terminal.

---

## 13. Using the bot day-to-day

### Telegram commands

**Anyone can use:**
| Command | What it does |
|---|---|
| `/start`, `/help` | Show help |
| `/subscribe` | Get pinged when slots open |
| `/unsubscribe` | Stop notifications |
| `/check` | Force a check now (~30 seconds) |
| `/status` | Your subscription state + last check + 24h stats |

**Only `ADMIN_TELEGRAM_ID` can use:**
| Command | What it does |
|---|---|
| `/stats` | Subscriber count + 24h/7d check stats |
| `/accounts` | List configured accounts and session status |
| `/broadcast hello everyone` | Send a message to all subscribers |

### How notifications work
- Every 10 minutes (configurable), the bot checks each enabled account
- If any account finds slots, all subscribers receive a notification with a direct link to the VFS booking page
- The bot only notifies on the **transition** from "no slots" to "slots open" — you won't get spammed every 10 minutes if slots stay open

### Sharing the bot
Send your friends the bot's username (e.g. `@italy_visa_slot_bot`). They send `/subscribe` and they're in.

---

## 14. Deploying with Docker

Docker is the cleanest way to keep the bot running 24/7 on any machine.

### Prerequisites
- Docker Desktop installed and running
- You've completed steps 8, 9, and 10 above (`.env`, `accounts.json`, `sessions/primary.json` all exist)

### Start everything
From the project folder:
```bash
docker compose up -d
```

This builds the image and starts two containers:
- `shengen_bot` — the Telegram bot
- `shengen_dashboard` — the web dashboard at `http://localhost:8000`

### View logs
```bash
docker compose logs -f bot
# or
docker compose logs -f dashboard
```
Press `Ctrl+C` to stop tailing (the containers keep running).

### Stop everything
```bash
docker compose down
```

### Restart after a config change
```bash
docker compose restart
```

### Rebuild after pulling new code
```bash
docker compose up -d --build
```

The Docker setup mounts these as volumes:
- `./data` — SQLite database (subscribers, history)
- `./logs` — log files
- `./sessions` — VFS session files
- `./accounts.json` — read-only

Your data persists across container restarts.

---

## 15. Deploying to a VPS for 24/7 operation

A VPS keeps the bot running even when your laptop is off.

### Pick a VPS
The smallest tier of any provider works. Recommended:
- Hetzner CX22 — €4.50/month, 2 vCPU, 4 GB RAM
- DigitalOcean Basic — $6/month, 1 vCPU, 1 GB RAM
- Choose Ubuntu 24.04 LTS

### Setup on the VPS

```bash
# SSH in
ssh root@YOUR_VPS_IP

# Install Docker
curl -fsSL https://get.docker.com | sh

# Add yourself to docker group (optional, skip if running as root)
usermod -aG docker $USER && newgrp docker

# Get the code
git clone https://github.com/valehdba/shengen_bot.git
cd shengen_bot

# Configure
cp .env.example .env
nano .env                            # paste TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID etc.

cp accounts.example.json accounts.json
nano accounts.json                   # define your accounts
```

### Transfer your session files
The VPS has no GUI, so you can't run `python -m src.cli login` there. Instead, log in on your laptop (section 10), then upload the session files:

```bash
# From your laptop:
scp sessions/*.json root@YOUR_VPS_IP:/root/shengen_bot/sessions/
```

### Start the stack
```bash
# Back on the VPS:
docker compose up -d
docker compose logs -f bot           # watch it work
```

### Expose the dashboard (optional)
By default the dashboard listens on port 8000 of the VPS. To make it accessible from the internet:

**Quick way** — just allow the port:
```bash
ufw allow 8000/tcp
```
Then visit `http://YOUR_VPS_IP:8000`. Use a strong dashboard password.

**Proper way** — put it behind a domain with HTTPS (Caddy is easiest):
```bash
apt install -y caddy
echo "yourdomain.com {
    reverse_proxy localhost:8000
}" > /etc/caddy/Caddyfile
systemctl restart caddy
```
Caddy auto-provisions a Let's Encrypt cert.

---

## 16. Handling expired VFS sessions

VFS sessions expire periodically (usually after a few days or weeks). When this happens:

1. The bot detects it during the next scheduled check
2. You receive an admin notification on Telegram:
   > 🛠️ Session expired for: primary. Run `python -m src.cli login --account <name>` to re-login.
3. **On your laptop** (not the VPS), re-run the interactive login:
   ```bash
   python -m src.cli login --account primary
   ```
4. **If running on a VPS**, copy the new session up:
   ```bash
   scp sessions/primary.json root@YOUR_VPS_IP:/root/shengen_bot/sessions/
   ssh root@YOUR_VPS_IP "cd /root/shengen_bot && docker compose restart bot"
   ```

Tip: do this proactively every 2-3 weeks instead of waiting for the alert.

---

## 17. Updating the code

### If you got it via zip
Download the new zip, unzip somewhere fresh, copy over your `.env`, `accounts.json`, `data/`, and `sessions/`.

### If you cloned from Git
```bash
cd shengen_bot
git pull
```

Then:
```bash
# Local install
pip install -r requirements.txt --upgrade
# Restart the bot

# Docker
docker compose up -d --build
```

---

## 18. Troubleshooting

### "TELEGRAM_BOT_TOKEN missing"
You didn't fill in `.env`, or you're not running from the project folder. Verify `cat .env` shows your token (don't paste output anywhere public).

### "No saved session for primary"
You skipped section 10. Run:
```bash
python -m src.cli login --account primary
```

### Bot starts, but `/check` returns "Session expired"
Your VFS session no longer works. Re-run section 10.

### "Playwright executable doesn't exist"
You skipped `playwright install chromium`. Run it now.

### On Linux: "Host system is missing dependencies"
```bash
playwright install-deps chromium
```

### Bot replies "No slots" forever even though VFS shows slots manually
VFS changed their UI text. Open `src/checker.py` and update the `NO_SLOTS_PHRASES` and `CALENDAR_SELECTORS` lists with the new strings/selectors. Run `HEADLESS=false python -m src.cli check` to watch the browser in action.

### "ImportError: No module named 'src'"
Run from the project root, not from inside `src/`. Use `python -m src.bot`, not `python src/bot.py`.

### Dashboard shows 401
Username/password mismatch with `.env`. Double-check `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD`.

### Docker: "Cannot connect to the Docker daemon"
Docker Desktop isn't running (on macOS/Windows) or you're not in the `docker` group (on Linux — log out and back in after `usermod -aG docker`).

### Bot crashes immediately on startup
Check `logs/bot.log` for the full traceback. Most common: typo in `.env`, missing comma in `accounts.json`, expired Python virtual env.

### "Too many requests" / rate-limited by VFS
Increase `CHECK_INTERVAL_MINUTES` in `.env`. Don't go below 5.

---

## 19. Uninstalling

```bash
# Stop everything
docker compose down              # if using Docker
# or just Ctrl+C the running processes

# Remove the project folder
cd ..
rm -rf shengen_bot

# Optional: delete the bot on Telegram
# In Telegram → @BotFather → /deletebot
```

Your VFS account itself is untouched.

---

## Need help?

- Open an issue on the repo: https://github.com/valehdba/shengen_bot/issues
- Include: what you ran, what you expected, what happened (paste the exact error)
- **Never paste your `.env`, tokens, or session files publicly** — redact them first
