from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os
from main import run

app = Flask(__name__)

# ── Schedule ──────────────────────────────────────────────────────────────────
# Runs every day at 08:00 AM UTC (adjust hour to your timezone)
# UTC+1 (Nigeria WAT) = set hour=7 for 8AM Nigeria time

def scheduled_job():
    print(f"[SCHEDULER] Running at {datetime.utcnow()} UTC")
    run()

scheduler = BackgroundScheduler()
scheduler.add_job(
    scheduled_job,
    trigger="cron",
    hour=7,        # 7 AM UTC = 8 AM Nigeria (WAT)
    minute=0,
    id="daily_picks"
)
scheduler.start()
print("[SCHEDULER] Daily picks scheduled for 08:00 AM Nigeria time")


# ── Web Routes ────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return jsonify({
        "status": "VenuePicks Bot is running",
        "next_run": "08:00 AM Nigeria time (WAT) daily",
        "trigger": "GET /run to trigger manually"
    })

@app.route("/run")
def manual_run():
    """Manually trigger the picks — useful for testing."""
    try:
        run()
        return jsonify({"status": "success", "message": "Picks sent to Telegram"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/run/<date>")
def run_for_date(date):
    """Run for a specific date — format: YYYY-MM-DD"""
    try:
        run(target_date=date)
        return jsonify({"status": "success", "date": date, "message": "Picks sent to Telegram"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": str(datetime.utcnow())})


# ── Start ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
