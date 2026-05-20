# VenuePicks Bot — Deployment Guide

## What this does
Automatically fetches tomorrow's football fixtures every day, runs your venue occurrence strategy on H2H data, and sends qualifying picks to your Telegram.

---

## Step 1 — Upload to GitHub

1. Go to **github.com** and create a free account if you don't have one
2. Click **"New repository"**
3. Name it: `venuepicks-bot`
4. Set it to **Public**
5. Click **"Create repository"**
6. Upload these 4 files:
   - `main.py`
   - `scheduler.py`
   - `requirements.txt`
   - `Procfile`

---

## Step 2 — Deploy on Render

1. Go to **render.com** and create a free account
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub account
4. Select your `venuepicks-bot` repository
5. Fill in these settings:
   - **Name:** venuepicks-bot
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn scheduler:app --bind 0.0.0.0:$PORT`
6. Click **"Create Web Service"**

---

## Step 3 — Add Environment Variables on Render

In your Render dashboard, go to **Environment** and add:

| Key | Value |
|-----|-------|
| `RAPIDAPI_KEY` | Your RapidAPI key |
| `TELEGRAM_TOKEN` | Your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |

---

## Step 4 — Test it

Once deployed, visit your Render URL + `/run` to trigger it manually:
```
https://your-app-name.onrender.com/run
```

You should receive picks in Telegram within 1-2 minutes.

---

## Daily Schedule
Picks are sent automatically at **8:00 AM Nigeria time (WAT)** every day.

To change the time, edit `scheduler.py` line:
```python
hour=7,  # Change this (UTC hour — Nigeria is UTC+1)
```

---

## Manual Triggers
- `/run` — Run for tomorrow's fixtures
- `/run/2026-05-25` — Run for a specific date
- `/health` — Check if bot is alive

---

## Leagues Monitored
See `LEAGUE_IDS` in `main.py` to add or remove leagues.
Full league list: https://www.api-football.com/documentation-v3#tag/Leagues
