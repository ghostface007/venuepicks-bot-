import requests
import os
from datetime import datetime, timedelta

# ── Configuration ────────────────────────────────────────────────────────────
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "964f29a8398e4668decf6f5b0454825f")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "7584426603:AAH0ODeQuPbkmR5NiP-K3YhV_0Q2rn06q5k")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6170016880")

HEADERS = {
    "x-apisports-key": API_FOOTBALL_KEY
}

BASE_URL = "https://v3.football.api-sports.io"

# ── Approved Leagues ─────────────────────────────────────────────────────────
APPROVED_LEAGUES = {
    39, 140, 135, 78, 61,
    2, 3, 848,
    88, 94, 203, 144,
    40, 41, 179,
    332, 169, 288, 128,
    233, 760, 357, 200,
    202,
    71, 72, 188, 13,
    11, 239, 240, 242,
    253, 307, 262, 322,
    113, 103, 244, 172,
    286, 292, 327, 391,
}


# ── API Status ───────────────────────────────────────────────────────────────

def check_api_status():
    try:
        res = requests.get(f"{BASE_URL}/status", headers=HEADERS, timeout=10)
        data = res.json()
        response = data.get("response", {})
        requests_info = response.get("requests", {})
        used = requests_info.get("current", 0)
        limit = requests_info.get("limit_day", 100)
        remaining = limit - used
        plan = response.get("subscription", {}).get("plan", "Unknown")
        print(f"[INFO] Plan: {plan}")
        print(f"[INFO] API Usage: {used}/{limit}")
        print(f"[INFO] Remaining Requests: {remaining}")
        return remaining
    except Exception as e:
        print(f"[WARN] Failed to check API status: {e}")
        return 100


# ── Fixture Fetch ────────────────────────────────────────────────────────────

def get_all_fixtures_for_date(date_str):
    print(f"[INFO] Fetching fixtures for {date_str}...")

    try:
        res = requests.get(
            f"{BASE_URL}/fixtures",
            headers=HEADERS,
            params={
                "date": date_str,
                "timezone": "Africa/Lagos"
            },
            timeout=20
        )

        data = res.json()

        print("\n[DEBUG] API Response Keys:", data.keys())
        print("[DEBUG] Results Count:", data.get("results"))
        print("[DEBUG] Errors:", data.get("errors"))

        all_fixtures = data.get("response", [])

        print(f"[INFO] Total Fixtures Returned: {len(all_fixtures)}")

        if all_fixtures:
            print("\n[DEBUG] Sample Fixture:")
            print(all_fixtures[0]["teams"])

        # Show all returned league IDs
        league_ids = set()
        for fixture in all_fixtures:
            league_ids.add(fixture.get("league", {}).get("id"))
        print("\n[DEBUG] Returned League IDs:")
        print(sorted([x for x in league_ids if x]))

        # Filter approved leagues
        filtered = [
            f for f in all_fixtures
            if f.get("league", {}).get("id") in APPROVED_LEAGUES
        ]

        print(f"\n[INFO] Approved League Fixtures: {len(filtered)}")

        # Fallback — if nothing matched approved list, return all
        if not filtered and all_fixtures:
            print("\n[WARN] No fixtures matched approved leagues — returning all for debug")
            return all_fixtures

        return filtered

    except Exception as e:
        print(f"[ERROR] Failed to fetch fixtures: {e}")
        return []


# ── H2H ──────────────────────────────────────────────────────────────────────

def get_h2h(home_id, away_id, last=5):
    try:
        res = requests.get(
            f"{BASE_URL}/fixtures/headtohead",
            headers=HEADERS,
            params={"h2h": f"{home_id}-{away_id}", "last": last},
            timeout=10
        )
        return res.json().get("response", [])
    except Exception as e:
        print(f"[WARN] H2H failed: {e}")
        return []


# ── Strategy ─────────────────────────────────────────────────────────────────

def get_year(fixture):
    try:
        return int(fixture["fixture"]["date"][:4])
    except:
        return None


def analyze_h2h(fixture_name, h2h_games):
    if len(h2h_games) < 5:
        return None, f"Only {len(h2h_games)} H2H games"

    last5 = h2h_games[:5]
    years = [get_year(g) for g in last5 if get_year(g)]

    if years:
        date_range = max(years) - min(years)
        if date_range > 5:
            return None, f"Date range too wide ({date_range} years)"

    home_scored = 0
    away_scored = 0

    for game in last5:
        goals = game.get("goals", {})
        if (goals.get("home") or 0) > 0:
            home_scored += 1
        if (goals.get("away") or 0) > 0:
            away_scored += 1

    picks = []

    if home_scored >= 4:
        picks.append({
            "type": "Home Over 0.5",
            "occurrence": f"{home_scored}/5",
            "confidence": "HIGH" if home_scored == 5 else "MODERATE"
        })
    if away_scored >= 4:
        picks.append({
            "type": "Away Over 0.5",
            "occurrence": f"{away_scored}/5",
            "confidence": "HIGH" if away_scored == 5 else "MODERATE"
        })
    if home_scored <= 1:
        picks.append({
            "type": "Home Under 0.5",
            "occurrence": f"{home_scored}/5",
            "confidence": "HIGH" if home_scored == 0 else "MODERATE"
        })
    if away_scored <= 1:
        picks.append({
            "type": "Away Under 0.5",
            "occurrence": f"{away_scored}/5",
            "confidence": "HIGH" if away_scored == 0 else "MODERATE"
        })

    if not picks:
        return None, "No threshold met"

    return picks, None


# ── Telegram ─────────────────────────────────────────────────────────────────

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        res = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        data = res.json()
        if data.get("ok"):
            print("[INFO] Telegram sent")
        else:
            print(f"[ERROR] Telegram: {data.get('description')}")
    except Exception as e:
        print(f"[ERROR] Telegram Error: {e}")


def build_telegram_message(qualified, skipped, target_date):
    date_formatted = datetime.strptime(target_date, "%Y-%m-%d").strftime("%d %b %Y")

    if not qualified:
        return (
            f"🎯 <b>VENUE PICKS — {date_formatted}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"No qualifying picks today.\n"
            f"Fixtures analysed: {len(skipped)}\n\n"
            f"⚡ VenuePicks Bot"
        )

    high_picks = [p for f in qualified for p in f["picks"] if p["confidence"] == "HIGH"]
    mod_picks = [p for f in qualified for p in f["picks"] if p["confidence"] == "MODERATE"]

    msg = f"🎯 <b>VENUE PICKS — {date_formatted}</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    for result in qualified:
        for pick in result["picks"]:
            emoji = "🟢" if pick["confidence"] == "HIGH" else "🟡"
            msg += f"{emoji} <b>{result['fixture']}</b>\n"
            msg += f"🏆 {result['league']}\n"
            msg += f"📌 {pick['type']}\n"
            msg += f"📊 {pick['occurrence']} | {pick['confidence']}\n\n"

    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🟢 HIGH: {len(high_picks)}  🟡 MODERATE: {len(mod_picks)}\n"
    msg += f"📋 Fixtures Checked: {len(qualified) + len(skipped)}\n"
    msg += f"⚡ VenuePicks Bot"

    return msg


# ── Main Runner ──────────────────────────────────────────────────────────────

def run(target_date=None):
    if target_date is None:
        target_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"\n{'='*50}")
    print(f"VenuePicks Bot — {target_date}")
    print(f"{'='*50}\n")

    remaining = check_api_status()

    if remaining < 10:
        send_telegram(
            f"⚠️ <b>VenuePicks Bot</b>\n\n"
            f"Low API balance detected ({remaining} remaining)."
        )
        return

    fixtures = get_all_fixtures_for_date(target_date)

    if not fixtures:
        send_telegram(
            f"🎯 <b>VenuePicks Bot</b>\n\n"
            f"No fixtures found for {target_date}."
        )
        return

    qualified = []
    skipped = []

    for fix in fixtures:
        home_team = fix["teams"]["home"]
        away_team = fix["teams"]["away"]
        fixture_name = f"{home_team['name']} vs {away_team['name']}"
        league_name = fix.get("league", {}).get("name", "Unknown League")
        league_id = fix.get("league", {}).get("id")

        print(f"[INFO] [{league_id}] {fixture_name} ({league_name})")

        h2h = get_h2h(home_team["id"], away_team["id"], last=5)
        picks, reason = analyze_h2h(fixture_name, h2h)

        if picks:
            qualified.append({
                "fixture": fixture_name,
                "league": league_name,
                "picks": picks
            })
            print(f"  ✅ {[p['type'] for p in picks]}")
        else:
            skipped.append({"fixture": fixture_name, "reason": reason})
            print(f"  ❌ {reason}")

    print(f"\n[INFO] Qualified: {len(qualified)}")
    print(f"[INFO] Skipped: {len(skipped)}")

    send_telegram(build_telegram_message(qualified, skipped, target_date))
    print("\n[INFO] Run Complete")


if __name__ == "__main__":
    run()
