import requests
import os
from datetime import datetime, timedelta

# ── Configuration ────────────────────────────────────────────────────────────
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "964f29a8398e4668decf6f5b0454825f")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "7584426603:AAH0ODeQuPbkmR5NiP-K3YhV_0Q2rn06q5k")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6170016880")

HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}
BASE_URL = "https://v3.football.api-sports.io"

# ── Approved Leagues (SportyBet focus) ───────────────────────────────────────
# Only fixtures from these leagues will be processed
APPROVED_LEAGUES = {
    # Top European
    39,   # Premier League - England
    140,  # La Liga - Spain
    135,  # Serie A - Italy
    78,   # Bundesliga - Germany
    61,   # Ligue 1 - France
    2,    # UEFA Champions League
    3,    # UEFA Europa League
    848,  # UEFA Conference League
    88,   # Eredivisie - Netherlands
    94,   # Primeira Liga - Portugal
    203,  # Super Lig - Turkey
    144,  # Jupiler Pro League - Belgium
    40,   # Championship - England
    41,   # League One - England
    179,  # Scottish Premiership

    # African
    332,  # Nigeria Premier League
    169,  # Ghana Premier League
    288,  # South Africa PSL
    128,  # Algerian Ligue 1
    233,  # Egyptian Premier League
    760,  # Zambia Super League
    357,  # Kenya Premier League
    200,  # Morocco Botola Pro
    202,  # Tunisia Ligue 1

    # South American
    71,   # Brasileirao Serie A
    72,   # Brasileirao Serie B
    188,  # Argentine Primera Division
    13,   # Copa Libertadores
    11,   # Copa Sudamericana
    239,  # Colombian Liga BetPlay
    240,  # Chilean Primera Division
    242,  # Ecuadorian Serie A

    # Others
    253,  # Chinese Super League
    307,  # Saudi Pro League
    262,  # MLS - USA
    322,  # Liga MX - Mexico
    113,  # Allsvenskan - Sweden
    103,  # Eliteserien - Norway
    244,  # Veikkausliiga - Finland
    172,  # Parva Liga - Bulgaria
    286,  # Estonian Premium Liiga
}


# ── API Calls ─────────────────────────────────────────────────────────────────

def check_api_status():
    """Check API key status and requests remaining."""
    try:
        res = requests.get(f"{BASE_URL}/status", headers=HEADERS, timeout=10)
        data = res.json()
        response = data.get("response", {})
        requests_info = response.get("requests", {})
        used = requests_info.get("current", 0)
        limit = requests_info.get("limit_day", 100)
        remaining = limit - used
        plan = response.get("subscription", {}).get("plan", "Unknown")
        print(f"[INFO] Plan: {plan} | Used: {used}/{limit} | Remaining: {remaining}")
        return remaining
    except Exception as e:
        print(f"[WARN] Status check failed: {e}")
        return 100


def get_all_fixtures_for_date(date_str):
    """
    Fetch ALL fixtures for a date in ONE API call.
    Then filter to only approved leagues.
    This saves ~89 API calls vs querying each league individually.
    """
    print(f"[INFO] Fetching all fixtures for {date_str} in one call...")
    all_fixtures = []

    try:
        res = requests.get(
            f"{BASE_URL}/fixtures",
            headers=HEADERS,
            params={"date": date_str},
            timeout=15
        )
        data = res.json()
        all_fixtures = data.get("response", [])
        print(f"[INFO] Total fixtures returned by API: {len(all_fixtures)}")
    except Exception as e:
        print(f"[ERROR] Fixture fetch failed: {e}")
        return []

    # Filter to approved leagues only
    filtered = [
        f for f in all_fixtures
        if f.get("league", {}).get("id") in APPROVED_LEAGUES
    ]

    print(f"[INFO] Fixtures in approved leagues: {len(filtered)}")
    return filtered


def get_h2h(home_id, away_id, last=5):
    """Fetch last N H2H results between two teams."""
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


# ── Strategy Logic ────────────────────────────────────────────────────────────

def get_year(fixture):
    try:
        return int(fixture["fixture"]["date"][:4])
    except:
        return None


def analyze_h2h(fixture_name, h2h_games):
    """Apply venue occurrence strategy."""
    if len(h2h_games) < 5:
        return None, f"Only {len(h2h_games)} H2H games — need 5"

    last5 = h2h_games[:5]

    # Date range filter — skip if span exceeds 5 years
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

    # Over 0.5 picks (favoured)
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

    # Under 0.5 picks (boosters only)
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
        return None, f"No threshold met (Home: {home_scored}/5, Away: {away_scored}/5)"

    return picks, None


# ── Telegram ──────────────────────────────────────────────────────────────────

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
            print("[INFO] Telegram sent successfully")
        else:
            print(f"[ERROR] Telegram: {data.get('description')}")
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")


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
        league = result.get("league", "")
        for pick in result["picks"]:
            emoji = "🟢" if pick["confidence"] == "HIGH" else "🟡"
            msg += f"{emoji} <b>{result['fixture']}</b>\n"
            if league:
                msg += f"   🏆 {league}\n"
            msg += f"   📌 {pick['type']}\n"
            msg += f"   📊 {pick['occurrence']} | {pick['confidence']}\n\n"

    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🟢 HIGH: {len(high_picks)}  🟡 MODERATE: {len(mod_picks)}\n"
    msg += f"📋 Fixtures checked: {len(qualified) + len(skipped)}\n"
    msg += f"\n⚡ VenuePicks Bot"

    return msg


# ── Main Runner ───────────────────────────────────────────────────────────────

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
            f"API limit almost reached ({remaining} requests left today).\n"
            f"Picks will resume tomorrow."
        )
        return

    # ONE call to get all fixtures for the date
    fixtures = get_all_fixtures_for_date(target_date)

    if not fixtures:
        send_telegram(
            f"🎯 <b>VenuePicks Bot</b>\n\n"
            f"No fixtures found for {target_date} in monitored leagues.\n"
            f"May be a rest day."
        )
        return

    qualified = []
    skipped = []

    for fix in fixtures:
        home_team = fix["teams"]["home"]
        away_team = fix["teams"]["away"]
        league_name = fix.get("league", {}).get("name", "")
        fixture_name = f"{home_team['name']} vs {away_team['name']}"
        home_id = home_team["id"]
        away_id = away_team["id"]

        print(f"[INFO] {fixture_name} ({league_name})")

        h2h = get_h2h(home_id, away_id, last=5)
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

    print(f"\n[INFO] Qualified: {len(qualified)} | Skipped: {len(skipped)}")
    send_telegram(build_telegram_message(qualified, skipped, target_date))
    print("[INFO] Done.")


if __name__ == "__main__":
    run()
