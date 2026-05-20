import requests
import os
from datetime import datetime, timedelta
import time

# ── Configuration ────────────────────────────────────────────────────────────
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "964f29a8398e4668decf6f5b0454825f")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "7584426603:AAH0ODeQuPbkmR5NiP-K3YhV_0Q2rn06q5k")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6170016880")

HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}
BASE_URL = "https://v3.football.api-sports.io"

# ── Leagues with CORRECT current seasons (verified May 2026) ─────────────────
# European Aug-May leagues are on season 2025 (Aug 2025 - May 2026)
# Jan-Dec leagues are on season 2026
LEAGUES = [
    # European Aug-May = season 2025
    (39, 2025),   # Premier League
    (140, 2025),  # La Liga
    (135, 2025),  # Serie A
    (78, 2025),   # Bundesliga
    (61, 2025),   # Ligue 1
    (2, 2025),    # Champions League
    (3, 2025),    # Europa League
    (848, 2025),  # Conference League
    (88, 2025),   # Eredivisie
    (94, 2025),   # Primeira Liga
    (203, 2025),  # Super Lig Turkey
    (144, 2025),  # Jupiler Pro League
    (40, 2025),   # Championship England
    (41, 2025),   # League One England
    (179, 2025),  # Scottish Premiership

    # Jan-Dec leagues = season 2026
    (71, 2026),   # Brasileirao Serie A
    (72, 2026),   # Brasileirao Serie B
    (188, 2026),  # Argentine Primera
    (13, 2026),   # Copa Libertadores
    (11, 2026),   # Copa Sudamericana
    (239, 2026),  # Colombian Liga
    (240, 2026),  # Chilean Primera
    (242, 2026),  # Ecuadorian Serie A
    (253, 2026),  # Chinese Super League
    (307, 2026),  # Saudi Pro League
    (262, 2026),  # MLS USA
    (322, 2026),  # Liga MX Mexico
    (113, 2026),  # Allsvenskan Sweden
    (103, 2026),  # Eliteserien Norway
    (244, 2026),  # Veikkausliiga Finland
    (172, 2026),  # Parva Liga Bulgaria
    (286, 2026),  # Estonian Premium Liiga

    # African Jan-Dec = season 2026
    (332, 2026),  # Nigeria Premier League
    (169, 2026),  # Ghana Premier League
    (288, 2026),  # South Africa PSL
    (128, 2026),  # Algerian Ligue 1
    (233, 2026),  # Egyptian Premier League
    (200, 2026),  # Morocco Botola Pro
    (202, 2026),  # Tunisia Ligue 1

    # K League Korea
    (292, 2026),  # K League 1
]


# ── API Calls ─────────────────────────────────────────────────────────────────

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
        print(f"[INFO] Plan: {plan} | Used: {used}/{limit} | Remaining: {remaining}")
        return remaining
    except Exception as e:
        print(f"[WARN] Status check failed: {e}")
        return 100


def get_fixtures_for_date(date_str, remaining_requests):
    """Query each league with correct season. Stop if budget runs low."""
    print(f"[INFO] Fetching fixtures for {date_str}...")
    all_fixtures = []
    seen_ids = set()
    calls_made = 0

    for league_id, season in LEAGUES:
        # Keep 40 requests spare for H2H calls
        if remaining_requests - calls_made < 40:
            print(f"[WARN] API budget low — stopping fixture fetch")
            break

        try:
            res = requests.get(
                f"{BASE_URL}/fixtures",
                headers=HEADERS,
                params={"league": league_id, "season": season, "date": date_str},
                timeout=10
            )
            data = res.json()
            calls_made += 1
            fixtures = data.get("response", [])

            for fix in fixtures:
                fix_id = fix["fixture"]["id"]
                if fix_id not in seen_ids:
                    seen_ids.add(fix_id)
                    all_fixtures.append(fix)

            if fixtures:
                name = fixtures[0].get("league", {}).get("name", "")
                print(f"  ✓ {name} (s{season}): {len(fixtures)} fixtures")

        except Exception as e:
            print(f"[WARN] League {league_id} s{season}: {e}")
            calls_made += 1

        time.sleep(0.1)

    print(f"[INFO] Total fixtures: {len(all_fixtures)} | Calls used: {calls_made}")
    return all_fixtures, calls_made


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


# ── Strategy Logic ────────────────────────────────────────────────────────────

def get_year(fixture):
    try:
        return int(fixture["fixture"]["date"][:4])
    except:
        return None


def analyze_h2h(fixture_name, h2h_games):
    if len(h2h_games) < 5:
        return None, f"Only {len(h2h_games)} H2H games — need 5"

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
        for pick in result["picks"]:
            emoji = "🟢" if pick["confidence"] == "HIGH" else "🟡"
            msg += f"{emoji} <b>{result['fixture']}</b>\n"
            msg += f"🏆 {result['league']}\n"
            msg += f"📌 {pick['type']}\n"
            msg += f"📊 {pick['occurrence']} | {pick['confidence']}\n\n"

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

    if remaining < 15:
        send_telegram(
            f"⚠️ <b>VenuePicks Bot</b>\n\n"
            f"API limit almost reached ({remaining} requests left).\n"
            f"Picks resume tomorrow when limit resets at midnight UTC."
        )
        return

    fixtures, calls_used = get_fixtures_for_date(target_date, remaining)

    if not fixtures:
        send_telegram(
            f"🎯 <b>VenuePicks Bot</b>\n\n"
            f"No fixtures found for {target_date}.\n"
            f"May be a rest day across monitored leagues."
        )
        return

    qualified = []
    skipped = []

    for fix in fixtures:
        home_team = fix["teams"]["home"]
        away_team = fix["teams"]["away"]
        fixture_name = f"{home_team['name']} vs {away_team['name']}"
        league_name = fix.get("league", {}).get("name", "Unknown")

        print(f"[INFO] {fixture_name} ({league_name})")

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

    print(f"\n[INFO] Qualified: {len(qualified)} | Skipped: {len(skipped)}")
    send_telegram(build_telegram_message(qualified, skipped, target_date))
    print("[INFO] Done.")


if __name__ == "__main__":
    run()
