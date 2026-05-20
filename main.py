import requests
import os
from datetime import datetime, timedelta

# ── Configuration ────────────────────────────────────────────────────────────
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "964f29a8398e4668decf6f5b0454825f")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "7584426603:AAH0ODeQuPbkmR5NiP-K3YhV_0Q2rn06q5k")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6170016880")

# Direct API-Football headers (not RapidAPI)
HEADERS = {
    "x-apisports-key": API_FOOTBALL_KEY
}

BASE_URL = "https://v3.football.api-sports.io"

# Leagues to monitor
LEAGUE_IDS = [
    39,   # Premier League
    140,  # La Liga
    135,  # Serie A
    78,   # Bundesliga
    61,   # Ligue 1
    88,   # Eredivisie
    94,   # Primeira Liga
    203,  # Super Lig
    144,  # Jupiler Pro League
    71,   # Brasileirao Serie A
    72,   # Brasileirao Serie B
    128,  # Algerian Ligue 1
    233,  # Egyptian Premier League
    172,  # Parva Liga Bulgaria
    113,  # Allsvenskan
    103,  # Eliteserien Norway
    244,  # Veikkausliiga Finland
    286,  # Estonian Premium Liiga
    327,  # 1. CFL Montenegro
    270,  # Macedonian First League
    253,  # Chinese Super League
    188,  # Argentine Primera Division
]

CURRENT_SEASON = 2025


# ── API Calls ─────────────────────────────────────────────────────────────────

def check_api_status():
    """Check API key is valid and how many requests remain."""
    try:
        res = requests.get(f"{BASE_URL}/status", headers=HEADERS, timeout=10)
        data = res.json()
        response = data.get("response", {})
        requests_info = response.get("requests", {})
        remaining = requests_info.get("limit_day", 0) - requests_info.get("current", 0)
        plan = response.get("subscription", {}).get("plan", "Unknown")
        print(f"[INFO] API Status OK — Plan: {plan} | Requests remaining today: {remaining}")
        return remaining
    except Exception as e:
        print(f"[WARN] Could not check API status: {e}")
        return 100


def get_fixtures_for_date(date_str):
    """Fetch all fixtures for a given date across all monitored leagues."""
    print(f"[INFO] Fetching fixtures for {date_str}...")
    all_fixtures = []

    for league_id in LEAGUE_IDS:
        try:
            res = requests.get(
                f"{BASE_URL}/fixtures",
                headers=HEADERS,
                params={"league": league_id, "season": CURRENT_SEASON, "date": date_str},
                timeout=10
            )
            data = res.json()
            fixtures = data.get("response", [])
            if fixtures:
                print(f"  [INFO] League {league_id}: {len(fixtures)} fixtures")
            all_fixtures.extend(fixtures)
        except Exception as e:
            print(f"[WARN] Failed to fetch league {league_id}: {e}")

    print(f"[INFO] Total fixtures found: {len(all_fixtures)}")
    return all_fixtures


def get_h2h(home_id, away_id, last=5):
    """Fetch last N H2H results between two teams."""
    try:
        res = requests.get(
            f"{BASE_URL}/fixtures/headtohead",
            headers=HEADERS,
            params={"h2h": f"{home_id}-{away_id}", "last": last},
            timeout=10
        )
        data = res.json()
        return data.get("response", [])
    except Exception as e:
        print(f"[WARN] H2H fetch failed: {e}")
        return []


# ── Strategy Logic ────────────────────────────────────────────────────────────

def get_year(fixture):
    """Extract year from fixture date string."""
    try:
        date_str = fixture["fixture"]["date"]
        return int(date_str[:4])
    except:
        return None


def analyze_h2h(fixture_name, h2h_games):
    """
    Apply venue occurrence strategy to H2H games.
    Returns list of qualifying picks or skip reason.
    """
    if len(h2h_games) < 5:
        return None, f"Only {len(h2h_games)} H2H games available — need 5"

    last5 = h2h_games[:5]

    # Date range check — skip if older than 5 years
    years = [get_year(g) for g in last5 if get_year(g)]
    if years:
        date_range = max(years) - min(years)
        if date_range > 5:
            return None, f"Date range too wide ({date_range} years)"

    # Count home and away scoring occurrences
    home_scored = 0
    away_scored = 0

    for game in last5:
        goals = game.get("goals", {})
        home_goals = goals.get("home", 0) or 0
        away_goals = goals.get("away", 0) or 0

        if home_goals > 0:
            home_scored += 1
        if away_goals > 0:
            away_scored += 1

    picks = []

    # Home Over 0.5
    if home_scored >= 4:
        picks.append({
            "type": "Home Over 0.5",
            "occurrence": f"{home_scored}/5",
            "confidence": "HIGH" if home_scored == 5 else "MODERATE"
        })

    # Home Under 0.5
    if home_scored <= 1:
        picks.append({
            "type": "Home Under 0.5",
            "occurrence": f"{home_scored}/5",
            "confidence": "HIGH" if home_scored == 0 else "MODERATE"
        })

    # Away Over 0.5
    if away_scored >= 4:
        picks.append({
            "type": "Away Over 0.5",
            "occurrence": f"{away_scored}/5",
            "confidence": "HIGH" if away_scored == 5 else "MODERATE"
        })

    # Away Under 0.5
    if away_scored <= 1:
        picks.append({
            "type": "Away Under 0.5",
            "occurrence": f"{away_scored}/5",
            "confidence": "HIGH" if away_scored == 0 else "MODERATE"
        })

    if not picks:
        return None, f"No side meets threshold (Home: {home_scored}/5, Away: {away_scored}/5)"

    return picks, None


# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(message):
    """Send message to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        res = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        data = res.json()
        if data.get("ok"):
            print("[INFO] Telegram message sent successfully")
        else:
            print(f"[ERROR] Telegram failed: {data.get('description')}")
    except Exception as e:
        print(f"[ERROR] Telegram error: {e}")


def build_telegram_message(qualified, skipped, target_date):
    """Build formatted Telegram message."""
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
            msg += f"   📌 {pick['type']}\n"
            msg += f"   📊 {pick['occurrence']} | {pick['confidence']}\n\n"

    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🟢 HIGH: {len(high_picks)}  🟡 MODERATE: {len(mod_picks)}\n"
    msg += f"📋 Fixtures checked: {len(qualified) + len(skipped)}\n"
    msg += f"\n⚡ VenuePicks Bot"

    return msg


# ── Main Runner ───────────────────────────────────────────────────────────────

def run(target_date=None):
    """Main function — fetch fixtures, analyse, send to Telegram."""

    if target_date is None:
        target_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"\n{'='*50}")
    print(f"VenuePicks Bot — Target date: {target_date}")
    print(f"{'='*50}\n")

    # Check API status first
    check_api_status()

    # Step 1: Get fixtures
    fixtures = get_fixtures_for_date(target_date)

    if not fixtures:
        msg = f"🎯 VenuePicks Bot\n\nNo fixtures found for {target_date}."
        send_telegram(msg)
        return

    qualified = []
    skipped = []

    # Step 2: For each fixture fetch H2H and analyse
    for fix in fixtures:
        home_team = fix["teams"]["home"]
        away_team = fix["teams"]["away"]
        fixture_name = f"{home_team['name']} vs {away_team['name']}"
        home_id = home_team["id"]
        away_id = away_team["id"]

        print(f"[INFO] Analysing: {fixture_name}")

        h2h = get_h2h(home_id, away_id, last=5)
        picks, reason = analyze_h2h(fixture_name, h2h)

        if picks:
            qualified.append({"fixture": fixture_name, "picks": picks})
            print(f"  ✅ Qualified: {[p['type'] for p in picks]}")
        else:
            skipped.append({"fixture": fixture_name, "reason": reason})
            print(f"  ❌ Skipped: {reason}")

    # Step 3: Send to Telegram
    print(f"\n[INFO] Qualified: {len(qualified)} | Skipped: {len(skipped)}")
    message = build_telegram_message(qualified, skipped, target_date)
    send_telegram(message)
    print("\n[INFO] Done.")


if __name__ == "__main__":
    run()
