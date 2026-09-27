import time
import os
import requests
import re

# Windows/Python certificate-store compatibility.
# Prefer the native Windows trust store via truststore when available.
try:
    import truststore
    truststore.inject_into_ssl()
    TRUSTSTORE_ENABLED = True
except Exception:
    TRUSTSTORE_ENABLED = False
import html
import sqlite3

from datetime import datetime, timedelta, timezone


# ============================================================
# STAKE RADAR V5.8
# ============================================================

VERSION = "V5.18"


# ============================================================
# TELEGRAM
# ============================================================

# ΒΑΛΕ ΕΔΩ ΤΟ ΝΕΟ BOT TOKEN ΑΠΟ @BotFather
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

TELEGRAM_API = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
)

# Το δικό σου Telegram USER ID
# Χρησιμοποιείται για admin commands
# και για τα instant bet updates.
ADMIN_ID = 5800306880

# ============================================================
# INSTANT BET UPDATE
# ============================================================

# False = instant updates μόνο στον ADMIN
# True  = instant updates σε όλους τους ενεργούς users
INSTANT_UPDATE_TO_ALL_USERS = False

# Telegram update offset
telegram_update_offset = 0


# ============================================================
# DATABASE
# ============================================================

DATABASE_FILE = "artistradar.db"


def init_database():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    connection.commit()
    connection.close()


def add_user(
    user_id,
    username="",
    first_name=""
):

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    now = datetime.now(
        timezone.utc
    ).isoformat()

    cursor.execute("""
        INSERT INTO users (
            user_id,
            username,
            first_name,
            active,
            created_at
        )
        VALUES (?, ?, ?, 1, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            active = 1
    """, (
        user_id,
        username,
        first_name,
        now,
    ))

    connection.commit()
    connection.close()


def remove_user(user_id):

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET active = 0
        WHERE user_id = ?
    """, (
        user_id,
    ))

    connection.commit()
    connection.close()


def get_active_users():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute("""
        SELECT user_id
        FROM users
        WHERE active = 1
    """)

    rows = cursor.fetchall()

    connection.close()

    return [
        row[0]
        for row in rows
    ]


def get_user_count():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE active = 1
    """)

    count = cursor.fetchone()[0]

    connection.close()

    return count


# ============================================================
# STAKE
# ============================================================

STAKE_GRAPHQL = "https://stake.com/_api/graphql"

# SSL verification for Stake. Keep verification ON by default.
# If Windows/Python cannot validate Stake's certificate, get_bets()
# retries once with verify=False so the radar can keep running.
STAKE_SSL_VERIFY = os.getenv("STAKE_SSL_VERIFY", "true").strip().lower() not in {
    "0", "false", "no", "off"
}

CHECK_EVERY = 5
STAKE_LIMIT = 20

MIN_AMOUNT_USDT = 3000

ALLOWED_CURRENCIES = {
    "usdt",
    "usdc",
}


# ============================================================
# HISTORY
# ============================================================

EVENT_HISTORY_MINUTES = 15
RECENT_BETS_MINUTES = 3

MAX_BETS_PER_SELECTION = 20
MAX_TELEGRAM_LENGTH = 3900


# ============================================================
# SMART 403 BACKOFF
# ============================================================

BLOCK_RETRY_INITIAL = 60
BLOCK_RETRY_MAX = 900


# ============================================================
# COMPETITION FILTER
# ============================================================

COMPETITION_FILTER = True

# ============================================================
# WHITELIST TEAMS
# ============================================================
# These teams bypass the normal competition filter and get
# a separate Telegram banner.
WHITELIST_TEAMS = {
    "pfc terdu",
    "sportivo san lorenzo",
    "aktobe reserve",
    "fc balti",
}

WHITELIST_BANNER = "🚨 WHITELIST ALERT 🚨"

# UEFA competitions that are always excluded.
EXCLUDED_TOURNAMENT_WORDS = (
    "champions league",
    "uefa champions league",
    "europa league",
    "uefa europa league",
    "conference league",
    "uefa conference league",
    "uefa europa conference league",
    "africa cup of nations qualification",
    "africa cup of nations qualifiers",
    "u21 euro qualification",
    "u21 euro qualifiers",
    "uefa u21 euro qualification",
    "uefa u21 euro qualifiers",
    "uefa nations league",
)

# Specific competition/category blocks requested by you.
# These remain excluded even inside the country allowlist.
EXCLUDED_SPECIFIC_COMPETITIONS = (
    # International football
    "africa cup of nations qualification",
    "africa cup of nations qualifiers",
    "u21 euro qualification",
    "u21 euro qualifiers",
    "uefa u21 euro qualification",
    "uefa u21 euro qualifiers",
    "uefa nations league",
    "nations league",

    # The exact categories shown in the screenshots
    "nbl",
    "national basketball league",
    "b.league",
    "b league",
    "usl championship",
    "kvindeligaen",
    "kvindeligaen women",
)

# Countries where you want ALL football competitions to be allowed,
# including first-tier/A' divisions. Specific exclusions above still win.
ALLOWED_COUNTRY_WORDS = (
    "argentina",
    "brazil",
    "brasil",
    "mexico",
    "indonesia",
    "vietnam",
    "viet nam",
    "kazakhstan",
    "thailand",
    "slovakia",
)

# Common names/slugs used by first-tier football competitions
# around the world. The filter also uses generic first-tier
# patterns below, so this is not limited to these names.
FIRST_TIER_NAMES = {
    "premier league",
    "super league",
    "superliga",
    "super lig",
    "süper lig",
    "bundesliga",
    "serie a",
    "ligue 1",
    "la liga",
    "laliga",
    "primeira liga",
    "eredivisie",
    "pro league",
    "jupiler pro league",
    "allsvenskan",
    "eliteserien",
    "superligaen",
    "ekstraklasa",
    "premiership",
    "premier division",
    "top league",
    "a-league",
    "a league",
    "j league",
    "j1 league",
    "k league 1",
    "k league",
    "super lig",
    "liga mx",
    "mls",
    "major league soccer",
    "brasileirao",
    "brasileirão",
    "primera división",
    "primera division",
    "liga profesional",
    "liga 1",
    "liga i",
    "super league 1",
    "super league greece",
    "super league 1 greece",
    "first league",
    "first division",
}

# Slug/name patterns which strongly indicate a first-tier league.
FIRST_TIER_PATTERNS = (
    "premier-league",
    "premier_league",
    "super-league",
    "super_league",
    "superliga",
    "bundesliga",
    "serie-a",
    "serie_a",
    "ligue-1",
    "ligue_1",
    "la-liga",
    "la_liga",
    "laliga",
    "primeira-liga",
    "primeira_liga",
    "eredivisie",
    "pro-league",
    "pro_league",
    "jupiler-pro-league",
    "allsvenskan",
    "eliteserien",
    "superligaen",
    "ekstraklasa",
    "premiership",
    "premier-division",
    "top-league",
    "j1-league",
    "j1",
    "k-league-1",
    "k1-league",
    "liga-mx",
    "mls",
    "major-league-soccer",
    "brasileirao",
    "brasileirao-serie-a",
    "serie-a-brazil",
    "primera-division",
    "primera-división",
    "liga-profesional",
)

# Exact first-tier names for leagues whose names are less obvious.
FIRST_TIER_EXACT = {
    # Greece
    "super league",
    "super league 1",
    "super league greece",

    # England / Scotland / Wales / Northern Ireland
    "premier league",
    "scottish premiership",
    "premiership",
    "cymru premier",
    "nifl premiership",

    # Spain / Portugal
    "la liga",
    "laliga",
    "primera división",
    "primera division",
    "primeira liga",

    # Italy / Germany / France
    "serie a",
    "bundesliga",
    "ligue 1",

    # Netherlands / Belgium / Austria / Switzerland
    "eredivisie",
    "jupiler pro league",
    "pro league",
    "austrian bundesliga",
    "austrian football bundesliga",
    "swiss super league",

    # Turkey / Greece / Cyprus
    "süper lig",
    "super lig",
    "cyprus first division",

    # Nordics
    "allsvenskan",
    "eliteserien",
    "danish superliga",
    "superliga",
    "veikkausliiga",
    "besta deild",
    "premier league iceland",

    # Poland / Czechia / Slovakia / Hungary / Romania / Croatia / Serbia
    "ekstraklasa",
    "1. liga",
    "czech first league",
    "fortuna liga",
    "slovak first football league",
    "niké liga",
    "nemzeti bajnokság i",
    "liga i",
    "superliga romania",
    "liga 1 romania",
    "croatian football league",
    "hrvatska nogometna liga",
    "serbian super liga",
    "superliga serbia",

    # Balkans
    "slovenian prva liga",
    "prva liga",
    "bosnian premier league",
    "premier league of bosnia and herzegovina",
    "montenegrin first league",
    "albanian superliga",
    "kosovo superleague",
    "north macedonia first football league",
    "bulgarian first league",

    # Americas
    "major league soccer",
    "mls",
    "liga mx",
    "liga profesional argentina",
    "primera división argentina",
    "brasileirão série a",
    "brasileirao serie a",
    "campeonato brasileiro série a",
    "liga colombiana",
    "primera división chile",
    "liga 1 peru",
    "liga ecuatoriana",
    "uruguayan primera división",
    "primera division paraguay",
    "liga panameña",
    "costa rica primera división",
    "liga betplay",

    # Asia / Middle East
    "j1 league",
    "k league 1",
    "chinese super league",
    "indian super league",
    "a-league men",
    "a league men",
    "saudi pro league",
    "uae pro league",
    "qatar stars league",
    "qatar stars league",
    "israeli premier league",
    "persian gulf pro league",
    "iranian pro league",
    "thai league 1",
    "malaysia super league",
    "indonesia liga 1",
    "vietnam v.league 1",

    # Africa
    "egyptian premier league",
    "south african premier division",
    "premier soccer league",
    "botola pro",
    "tunisian ligue 1",
    "algerian ligue 1",
    "ghana premier league",
    "nigerian premier league",
    "kenyan premier league",
}



# ============================================================
# TENNIS FILTER
# ============================================================

EXCLUDED_TENNIS_PATTERNS = (
    "grand slam", "australian open", "roland garros", "french open",
    "wimbledon", "us open", "usopen", "atp finals", "wta finals",
    "atp masters", "masters 1000", "atp 1000", "wta 1000",
    "atp 500", "wta 500", "atp 250", "wta 250",
    "davis cup", "billie jean king cup", "fed cup", "united cup",
    "laver cup", "olympic tennis", "olympics tennis", "olympic games tennis",
)

EXCLUDED_TENNIS_SLUG_PATTERNS = (
    "grand-slam", "australian-open", "roland-garros", "french-open",
    "wimbledon", "us-open", "atp-finals", "wta-finals",
    "atp-masters", "masters-1000", "atp-1000", "wta-1000",
    "atp-500", "wta-500", "atp-250", "wta-250", "davis-cup",
    "billie-jean-king-cup", "fed-cup", "united-cup", "laver-cup",
    "olympic",
)


def normalize_filter_text(value):
    """Normalize tournament/category text for reliable comparisons."""
    if not value:
        return ""

    value = str(value).strip().lower()
    value = value.replace("_", " ")
    value = value.replace("-", " ")
    value = " ".join(value.split())

    return value


def is_whitelist_team(*names):
    """
    Returns True when any supplied team/selection name matches
    one of the explicitly whitelisted teams.
    """
    for name in names:
        value = normalize_filter_text(name)
        if value in WHITELIST_TEAMS:
            return True
    return False


def is_excluded_competition(
    tournament_slug="",
    tournament_name="",
    category_slug="",
    category_name="",
    sport_slug="",
    sport_name=""
):
    """
    Blocks:
      - ALL identifiable first-tier/A' division football competitions
      - Champions League
      - Europa League
      - Conference League

    The check uses both tournament and category data.
    """

    if not COMPETITION_FILTER:
        return False

    sport = normalize_filter_text(sport_slug)
    sport_name_normalized = normalize_filter_text(sport_name)

    # HARD BLOCK: ALL TENNIS.
    # No tennis alert is allowed, regardless of tournament/category.
    is_tennis = (
        "tennis" in sport
        or "tennis" in sport_name_normalized
    )

    if is_tennis:
        return True

    # Football logic below.

    sport_name_normalized = normalize_filter_text(sport_name)

    # Only apply this A' division logic to football/soccer.
    is_football = (
        "football" in sport
        or "soccer" in sport
        or "football" in sport_name_normalized
        or "soccer" in sport_name_normalized
    )

    if not is_football:
        return False

    tournament = normalize_filter_text(tournament_name)
    tournament_slug_normalized = normalize_filter_text(tournament_slug)
    category = normalize_filter_text(category_name)
    category_slug_normalized = normalize_filter_text(category_slug)

    values = (
        tournament,
        tournament_slug_normalized,
        category,
        category_slug_normalized,
    )

    # Specific requested exclusions always win.
    for value in values:
        for blocked in EXCLUDED_SPECIFIC_COMPETITIONS:
            blocked_normalized = normalize_filter_text(blocked)
            if blocked_normalized and blocked_normalized in value:
                return True

    # UEFA competitions.
    for value in values:
        for word in EXCLUDED_TOURNAMENT_WORDS:
            if word in value:
                return True

    # Country allowlist: these football countries bypass the generic
    # A' / first-tier exclusion, but the specific blocks above remain active.
    combined_competition = " ".join(values)
    if any(country in combined_competition for country in ALLOWED_COUNTRY_WORDS):
        return False

    # Exact first-tier names.
    for value in values:
        if value in FIRST_TIER_NAMES or value in FIRST_TIER_EXACT:
            return True

    # Strong first-tier patterns.
    for raw_value in values:
        if not raw_value:
            continue

        # Check both normalized spaces and a compact slug-like version.
        compact = raw_value.replace(" ", "-")

        for pattern in FIRST_TIER_PATTERNS:
            pattern_normalized = pattern.replace("-", " ")

            if (
                pattern_normalized in raw_value
                or pattern in compact
            ):
                return True

    # Explicit "first division / first league" patterns.
    first_tier_generic = (
        "first division",
        "first league",
        "premier division",
        "premier league",
        "top division",
        "top flight",
        "division 1",
        "division i",
        "1st division",
        "1st league",
    )

    for value in values:
        for pattern in first_tier_generic:
            if pattern in value:
                return True

    return False



# ============================================================
# GRAPHQL QUERY
# ============================================================

QUERY = """
query BetsBoard_HighrollerSportBetsBase($limit: Int!) {
  highrollerSportBets(limit: $limit) {
    __typename
    id
    iid

    bet {
      __typename

      ... on SportBet {
        __typename
        id
        customBet
        status
        updatedAt
        createdAt
        potentialMultiplier
        payout
        payoutMultiplier
        amount
        currency

        user {
          __typename
          name
          preferenceHideBets

          flags {
            __typename
            flag
            rank
            createdAt
          }
        }

        outcomes {
          __typename
          id
          odds
          status
          fixtureAbreviation
          fixtureName

          market {
            __typename
            id
            name
          }

          fixture {
            __typename
            id

            data {
              __typename

              ... on SportFixtureDataMatch {
                __typename

                competitors {
                  __typename
                  name
                  abbreviation
                }
              }

              ... on SportFixtureDataOutright {
                __typename
                name
                startTime
                endTime
              }
            }

            tournament {
              __typename
              id
              name
              slug

              category {
                __typename
                id
                name
                slug

                sport {
                  __typename
                  id
                  name
                  slug
                }
              }
            }
          }

          outcome {
            __typename
            id
            name
          }
        }
      }
    }
  }
}
"""


# ============================================================
# SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",

    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),

    "Origin": "https://stake.com",
    "Referer": "https://stake.com/",
})


# ============================================================
# GLOBAL STATE
# ============================================================

seen_bet_ids = set()
result_notified_bet_ids = set()
event_groups = {}


# ============================================================
# BASIC HELPERS
# ============================================================

def safe_float(value, default=0.0):

    try:
        return float(value)

    except Exception:
        return default


def clean_text(value):

    if value is None:
        return ""

    return str(value).strip()


def escape_html(value):

    return html.escape(
        clean_text(value)
    )


def format_money(amount):

    try:
        return f"{float(amount):,.2f}".replace(
            ",",
            ""
        )

    except Exception:
        return "0.00"


def parse_datetime(value):

    if not value:
        return None

    try:

        text = str(value).strip()

        if text.endswith("Z"):
            text = (
                text[:-1]
                + "+00:00"
            )

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt

    except Exception:
        return None


def format_time(value):

    dt = parse_datetime(value)

    if not dt:
        return "--:--"

    try:

        return dt.astimezone().strftime(
            "%H:%M"
        )

    except Exception:
        return dt.strftime("%H:%M")


def bet_datetime(bet):

    dt = parse_datetime(
        bet.get("created_at")
    )

    if dt is None:
        dt = parse_datetime(
            bet.get("updated_at")
        )

    if dt is None:
        dt = datetime.now(
            timezone.utc
        )

    return dt


# ============================================================
# HASHTAGS
# ============================================================

def make_hashtag(value):

    value = clean_text(value)

    if not value:
        return ""

    value = re.sub(
        r"[_/]+",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    ).strip()

    value = re.sub(
        r"[^\w\s-]",
        "",
        value,
        flags=re.UNICODE
    )

    if not value:
        return ""

    value = value.replace(
        " ",
        "_"
    )

    value = value.replace(
        "-",
        "_"
    )

    return "#" + value


def name_hashtags(names):

    result = []

    for name in names:

        tag = make_hashtag(name)

        if tag:
            result.append(tag)

    return " ".join(result)



def is_whitelist_bet(bet):
    teams = bet.get("teams", [])
    if isinstance(teams, (list, tuple)):
        return any(is_whitelist_team(x) for x in teams)
    return is_whitelist_team(
        bet.get("home_team"),
        bet.get("away_team"),
        bet.get("selection_name"),
        bet.get("fixture_name"),
    )



def whitelist_banner_for_bet(bet):
    return WHITELIST_BANNER if is_whitelist_bet(bet) else ""


# ============================================================
# GRAPHQL
# ============================================================

def get_bets():

    payload = {
        "operationName":
            "BetsBoard_HighrollerSportBetsBase",

        "variables": {
            "limit": STAKE_LIMIT
        },

        "query": QUERY,
    }

    try:

        try:
            response = session.post(
                STAKE_GRAPHQL,
                json=payload,
                timeout=20,
                verify=STAKE_SSL_VERIFY,
            )
        except requests.exceptions.SSLError as ssl_error:
            # Some Windows/Python installations fail to build the issuer
            # chain even though the browser trusts the site. If truststore
            # is unavailable or the local chain is still broken, retry once
            # without certificate verification as a compatibility fallback.
            print(f"[STAKE] SSL verification failed: {ssl_error}")
            print("[STAKE] Retrying Stake request with certificate verification OFF.")
            response = session.post(
                STAKE_GRAPHQL,
                json=payload,
                timeout=20,
                verify=False,
            )

    except requests.exceptions.Timeout:

        return {
            "status": "network",
            "error": "Timeout",
            "bets": [],
        }

    except requests.exceptions.RequestException as e:

        return {
            "status": "network",
            "error": str(e),
            "bets": [],
        }

    if response.status_code == 403:

        return {
            "status": "blocked",
            "error": "HTTP 403",
            "bets": [],
        }

    if response.status_code != 200:

        return {
            "status": "http",
            "error": (
                f"HTTP {response.status_code}"
            ),
            "bets": [],
        }

    try:

        data = response.json()

    except Exception:

        return {
            "status": "json",
            "error": "Invalid JSON",
            "bets": [],
        }

    if data.get("errors"):

        return {
            "status": "graphql",
            "error": str(
                data.get("errors")
            ),
            "bets": [],
        }

    try:

        bets = (
            data
            .get("data", {})
            .get(
                "highrollerSportBets",
                []
            )
        )

        if bets is None:
            bets = []

        return {
            "status": "ok",
            "error": None,
            "bets": bets,
        }

    except Exception as e:

        return {
            "status": "nodata",
            "error": str(e),
            "bets": [],
        }


# ============================================================
# EXTRACT MATCH
# ============================================================

def extract_competitors(fixture):

    data = fixture.get(
        "data"
    ) or {}

    competitors = data.get(
        "competitors"
    ) or []

    names = []

    for competitor in competitors:

        if not isinstance(
            competitor,
            dict
        ):
            continue

        name = clean_text(
            competitor.get("name")
        )

        if name:
            names.append(name)

    return names


def extract_event_name(
    first_outcome,
    fixture
):

    competitors = extract_competitors(
        fixture
    )

    if len(competitors) >= 2:

        return " - ".join(
            competitors
        ), competitors

    fixture_name = clean_text(
        first_outcome.get(
            "fixtureName"
        )
    )

    if fixture_name:
        return fixture_name, []

    abbreviation = clean_text(
        first_outcome.get(
            "fixtureAbreviation"
        )
    )

    if abbreviation:
        return abbreviation, []

    return "Unknown Event", []


# ============================================================
# NORMALIZE BET
# ============================================================

def normalize_bet(raw):

    if not isinstance(
        raw,
        dict
    ):
        return None

    bet = raw.get(
        "bet"
    )

    if not isinstance(
        bet,
        dict
    ):
        return None

    if bet.get(
        "__typename"
    ) != "SportBet":

        return None

    bet_id = clean_text(
        raw.get("id")
        or bet.get("id")
    )

    if not bet_id:
        return None

    amount = safe_float(
        bet.get("amount")
    )

    if amount < MIN_AMOUNT_USDT:
        return None

    currency = clean_text(
        bet.get("currency")
    ).lower()

    if currency not in ALLOWED_CURRENCIES:
        return None

    outcomes = bet.get(
        "outcomes"
    ) or []

    if not outcomes:
        return None

    first = outcomes[0] or {}

    fixture = first.get(
        "fixture"
    ) or {}

    tournament_obj = fixture.get(
        "tournament"
    ) or {}

    category = tournament_obj.get(
        "category"
    ) or {}

    sport_obj = category.get(
        "sport"
    ) or {}

    tournament_slug = clean_text(
        tournament_obj.get(
            "slug"
        )
    )

    tournament_name = clean_text(
        tournament_obj.get(
            "name"
        )
    )

    category_name = clean_text(
        category.get("name")
    )

    category_slug = clean_text(
        category.get("slug")
    )

    sport_name = clean_text(
        sport_obj.get("name")
    )

    sport_slug = clean_text(
        sport_obj.get("slug")
    )

    # ========================================================
    # HARD BLOCKED SPORTS
    # ========================================================
    # American football must never generate alerts.
    # This is checked before the whitelist/competition logic so
    # even a whitelisted team cannot bypass the sport block.
    sport_filter = normalize_filter_text(sport_name or sport_slug)

    # NEVER ALERT: tennis, baseball, cricket, American football.
    # These blocks run BEFORE whitelist/competition logic.
    HARD_BLOCKED_SPORTS = {
        "tennis",
        "baseball",
        "cricket",
        "american football",
        "american football league",
        "nfl",
    }

    if sport_filter in HARD_BLOCKED_SPORTS:
        return None

    if (
        "american football" in sport_filter
        or "baseball" in sport_filter
        or "cricket" in sport_filter
        or "tennis" in sport_filter
    ):
        return None

    # NEVER ALERT: ALL esports, including titles Stake may expose
    # without the literal word "esports" in the sport name.
    esports_terms = (
        "esport", "e-sport", "cs2", "counter-strike", "counter strike",
        "counterstrike", "dota 2", "dota2", "league of legends",
        "valorant", "rainbow six", "rocket league", "overwatch",
        "starcraft", "call of duty", "pubg", "mobile legends",
        "arena of valor", "king of glory", "efootball", "fifa esports",
        "ea sports fc", "nba 2k", "nba2k", "madden",
    )

    if any(term in sport_filter for term in esports_terms):
        return None

    # ========================================================
    # BLOCK FIRST-TIER / A' DIVISION FOOTBALL
    # ========================================================
    # Build the team/fixture names before the whitelist check.
    # The previous version referenced these variables before they
    # were defined, causing:
    #     NameError: name 'home_team' is not defined

    competitors_for_filter = extract_competitors(fixture)

    home_team = (
        competitors_for_filter[0]
        if len(competitors_for_filter) >= 1
        else ""
    )

    away_team = (
        competitors_for_filter[1]
        if len(competitors_for_filter) >= 2
        else ""
    )

    fixture_name = clean_text(
        first.get("fixtureName")
    )

    selection_name = clean_text(
        (first.get("outcome") or {}).get("name")
    )

    if not is_whitelist_team(
        home_team,
        away_team,
        selection_name,
        fixture_name,
    ):
        if is_excluded_competition(
            tournament_slug=tournament_slug,
            tournament_name=tournament_name,
            category_slug=category_slug,
            category_name=category_name,
            sport_slug=sport_slug,
            sport_name=sport_name,
        ):
            return None

    sport = (
        sport_name
        or sport_slug
        or "Unknown"
    )

    event_name, competitors = (
        extract_event_name(
            first,
            fixture
        )
    )

    outcome_obj = first.get(
        "outcome"
    ) or {}

    selection = clean_text(
        outcome_obj.get("name")
        or "Unknown"
    )

    market_obj = first.get(
        "market"
    ) or {}

    market = clean_text(
        market_obj.get("name")
        or "Unknown market"
    )

    odds = safe_float(
        first.get("odds"),
        0
    )

    # Stake can expose settlement on the SportBet itself and/or
    # on each outcome. The SportBet status is authoritative when
    # it is a terminal status; otherwise fall back to outcome status.
    bet_status = clean_text(
        bet.get("status")
    ).lower()

    outcome_status = clean_text(
        first.get("status")
    ).lower()

    terminal_won = {
        "won", "win", "winner", "settled_won", "success"
    }
    terminal_lost = {
        "lost", "loss", "loser", "settled_lost", "failed"
    }
    terminal_cancelled = {
        "cancelled", "canceled", "void", "refunded", "push"
    }

    if bet_status in terminal_won:
        outcome_status = "won"
    elif bet_status in terminal_lost:
        outcome_status = "lost"
    elif bet_status in terminal_cancelled:
        outcome_status = "cancelled"
    elif not outcome_status:
        outcome_status = bet_status

    username = ""

    user_obj = bet.get(
        "user"
    )

    if isinstance(
        user_obj,
        dict
    ):

        username = clean_text(
            user_obj.get("name")
        )

    created_at = bet.get(
        "createdAt"
    )

    updated_at = bet.get(
        "updatedAt"
    )

    timestamp = bet_datetime({
        "created_at": created_at,
        "updated_at": updated_at,
    })

    return {

        "id": bet_id,

        "amount": amount,

        "currency": currency.upper(),

        "sport": sport,

        "sport_slug": sport_slug,

        "category_name": (
            category_name
            or category_slug
        ),

        "tournament": (
            tournament_name
            or tournament_slug
        ),

        "tournament_slug":
            tournament_slug,

        "event": event_name,

        "competitors":
            competitors,

        "selection":
            selection,

        "market":
            market,

        "odds":
            odds,

        "outcome_status":
            outcome_status,

        "bet_status":
            bet_status,

        "payout":
            safe_float(bet.get("payout"), 0),

        "payout_multiplier":
            safe_float(bet.get("payoutMultiplier"), 0),

        "username":
            username,

        "created_at":
            created_at,

        "updated_at":
            updated_at,

        "timestamp":
            timestamp,
    }


# ============================================================
# EVENT KEY
# ============================================================

def get_event_key(bet):

    return (
        bet["sport"].lower(),
        bet["event"].lower(),
    )


# ============================================================
# CREATE EMPTY EVENT GROUP
# ============================================================

def create_event_group(bet):

    return {

        "sport":
            bet["sport"],

        "category_name":
            bet["category_name"],

        "tournament":
            bet["tournament"],

        "tournament_slug":
            bet["tournament_slug"],

        "event":
            bet["event"],

        "competitors":
            bet["competitors"],

        "bets":
            [],

        # Different message ID for every user
        "telegram_message_ids":
            {},
    }


# ============================================================
# ADD BET TO EVENT GROUP
# ============================================================

def add_bet_to_group(
    group,
    bet
):

    existing_ids = {

        x["id"]

        for x in group.get(
            "bets",
            []
        )
    }

    if bet["id"] in existing_ids:
        return False

    group["bets"].append(
        bet
    )

    group["bets"].sort(
        key=lambda x:
            x["timestamp"]
    )

    now = datetime.now(
        timezone.utc
    )

    cutoff = (
        now
        - timedelta(
            minutes=EVENT_HISTORY_MINUTES
        )
    )

    group["bets"] = [

        x

        for x in group["bets"]

        if x["timestamp"]
        >= cutoff
    ]

    return True


# ============================================================
# EVENT GROUP CLEANUP
# ============================================================

def cleanup_all_events():

    now = datetime.now(
        timezone.utc
    )

    cutoff = (
        now
        - timedelta(
            minutes=EVENT_HISTORY_MINUTES
        )
    )

    empty_events = []

    for event_key, group in (
        event_groups.items()
    ):

        group["bets"] = [

            bet

            for bet in group.get(
                "bets",
                []
            )

            if bet["timestamp"]
            >= cutoff
        ]

        if not group["bets"]:

            empty_events.append(
                event_key
            )

    for event_key in empty_events:

        del event_groups[
            event_key
        ]


# ============================================================
# SEED EXISTING EVENTS
# ============================================================

def seed_existing_events(
    bets
):

    """
    Loads existing bets into event_groups silently.

    This does NOT send Telegram messages.

    It allows V5.8 to understand that an event already
    existed when the bot started, so a later bet on that
    same event can trigger NEW BET UPDATE.
    """

    seeded_events = 0
    seeded_bets = 0

    for bet in bets:

        event_key = get_event_key(
            bet
        )

        if event_key not in event_groups:

            event_groups[
                event_key
            ] = create_event_group(
                bet
            )

            seeded_events += 1

        group = event_groups[
            event_key
        ]

        if add_bet_to_group(
            group,
            bet
        ):

            seeded_bets += 1

    return (
        seeded_events,
        seeded_bets
    )


# ============================================================
# RECENT BETS
# ============================================================

def get_recent_bets(bets):

    now = datetime.now(
        timezone.utc
    )

    cutoff = (
        now
        - timedelta(
            minutes=RECENT_BETS_MINUTES
        )
    )

    return [

        bet

        for bet in bets

        if bet["timestamp"]
        >= cutoff
    ]


# ============================================================
# GROUP BY SELECTION
# ============================================================

def group_by_selection(
    bets
):

    grouped = {}

    for bet in bets:

        selection = bet[
            "selection"
        ]

        if selection not in grouped:

            grouped[
                selection
            ] = []

        grouped[
            selection
        ].append(
            bet
        )

    for selection in grouped:

        grouped[
            selection
        ].sort(
            key=lambda x:
                x["timestamp"]
        )

    return grouped


# ============================================================
# FORMAT ODDS
# ============================================================

def format_odds(odds):

    if not odds:
        return "-"

    return f"{odds:.2f}"


# ============================================================
# BET RESULT STATUS
# ============================================================

def result_icon(status):

    status = clean_text(status).lower()

    if status in {
        "won", "win", "winner", "settled_won", "success",
    }:
        return "✅"

    if status in {
        "lost", "loss", "loser", "settled_lost", "failed",
    }:
        return "❌"

    if status in {
        "cancelled", "canceled", "void", "refunded", "push",
    }:
        return "↩️"

    return "⏳"


def is_settled_status(status):

    return clean_text(status).lower() in {
        "won", "win", "winner", "settled_won", "success",
        "lost", "loss", "loser", "settled_lost", "failed",
        "cancelled", "canceled", "void", "refunded", "push",
    }


# ============================================================
# CREATE TELEGRAM MESSAGE
# ============================================================

def create_event_message(
    group
):

    bets = list(
        group.get(
            "bets",
            []
        )
    )

    if not bets:
        return None

    bets.sort(
        key=lambda x:
            x["timestamp"]
    )

    sport = clean_text(
        group.get(
            "sport"
        )
    )

    category = clean_text(
        group.get(
            "category_name"
        )
    )

    tournament = clean_text(
        group.get(
            "tournament"
        )
    )

    event = clean_text(
        group.get(
            "event"
        )
    )

    competitors = (
        group.get(
            "competitors"
        )
        or []
    )

    total_volume = sum(
        bet["amount"]
        for bet in bets
    )

    recent_bets = get_recent_bets(
        bets
    )

    lines = []

    sport_tag = make_hashtag(
        sport
    )

    category_tag = make_hashtag(
        category
    )

    tournament_tag = make_hashtag(
        tournament
    )

    competition_parts = []

    if category_tag:

        competition_parts.append(
            category_tag
        )

    if (
        tournament_tag
        and tournament_tag.lower()
        != category_tag.lower()
    ):

        competition_parts.append(
            tournament_tag
        )

    if sport_tag:

        if competition_parts:

            lines.append(
                f"{sport_tag} "
                f"{' '.join(competition_parts)}"
            )

        else:

            lines.append(
                sport_tag
            )

    elif competition_parts:

        lines.append(
            " ".join(
                competition_parts
            )
        )

    if competitors:

        event_tags = name_hashtags(
            competitors
        )

    else:

        parts = re.split(
            r"\s+(?:vs?\.?|v\.?)\s+"
            r"|\s*[-–—@]\s*",
            event,
            flags=re.IGNORECASE
        )

        parts = [
            p.strip()
            for p in parts
            if p.strip()
        ]

        if len(parts) >= 2:

            event_tags = name_hashtags(
                parts[:4]
            )

        else:

            event_tags = make_hashtag(
                event
            )

    if event_tags:

        lines.append(
            f"⚡ {event_tags}"
        )

    lines.append("")

    lines.append(
        f"💰 Volume: "
        f"{format_money(total_volume)}$"
    )

    lines.append(
        f"⚔️ Total: "
        f"{len(bets)} bets / "
        f"{len(recent_bets)} bets in "
        f"{RECENT_BETS_MINUTES} min"
    )

    lines.append("")

    last_bet = bets[-1]

    lines.append(
        "⚔️ <b>Last bet:</b>"
    )

    lines.append(
        f"🎯 "
        f"{escape_html(last_bet['selection'])}"
    )

    lines.append(
        f"📌 "
        f"{escape_html(last_bet.get('market', 'Unknown market'))}"
    )

    lines.append(
        f"💵 ${format_money(last_bet['amount'])} "
        f"x {format_odds(last_bet['odds'])} "
        f"| 🕐 "
        f"{format_time(last_bet.get('created_at')
                      or last_bet.get('updated_at'))}"
    )

    lines.append("")

    lines.append(
        "⚔️ <b>All bets:</b>"
    )

    selection_groups = (
        group_by_selection(
            bets
        )
    )

    selection_items = sorted(
        selection_groups.items(),
        key=lambda item:
            max(
                bet["timestamp"]
                for bet in item[1]
            )
    )

    selection_number = 0

    for selection, selection_bets in (
        selection_items
    ):

        selection_number += 1

        selection_total = sum(
            bet["amount"]
            for bet in selection_bets
        )

        lines.append("")

        lines.append(
            f"<b>{selection_number}. "
            f"🎯 "
            f"{escape_html(selection)} "
            f"| "
            f"{format_money(selection_total)}$</b>"
        )

        display_bets = list(
            reversed(
                selection_bets
            )
        )

        display_bets = display_bets[
            :MAX_BETS_PER_SELECTION
        ]

        for bet in display_bets:

            amount = format_money(
                bet["amount"]
            )

            odds = format_odds(
                bet["odds"]
            )

            bet_time = format_time(
                bet.get("created_at")
                or bet.get("updated_at")
            )

            status_icon = result_icon(
                bet.get("outcome_status", "")
            )

            lines.append(
                f"   {status_icon} 📌 {escape_html(bet.get('market', 'Unknown market'))}"
            )

            lines.append(
                f"   └─ ${amount} "
                f"x {odds} "
                f"| 🕐 {bet_time}"
            )

    message = "\n".join(
        lines
    )

    if len(message) > MAX_TELEGRAM_LENGTH:

        message = (
            message[
                :MAX_TELEGRAM_LENGTH
            ]
            + "\n\n"
            + "<i>…older bets omitted</i>"
        )

    return message


# ============================================================
# TELEGRAM REQUEST
# ============================================================

def telegram_request(
    method,
    payload
):

    url = (
        f"{TELEGRAM_API}/{method}"
    )

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=20,
        )

        if response.status_code != 200:

            print(
                f"[TELEGRAM] "
                f"HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

            return None

        data = response.json()

        if not data.get("ok"):

            print(
                f"[TELEGRAM] API error: "
                f"{data}"
            )

            return None

        return data

    except requests.exceptions.RequestException as e:

        print(
            f"[TELEGRAM] Network error: "
            f"{e}"
        )

        return None

    except Exception as e:

        print(
            f"[TELEGRAM] Error: "
            f"{e}"
        )

        return None


# ============================================================
# TELEGRAM SEND TO ONE USER
# ============================================================

def send_to_user(
    user_id,
    text
):

    payload = {

        "chat_id":
            user_id,

        "text":
            text,

        "parse_mode":
            "HTML",

        "disable_web_page_preview":
            True,
    }

    result = telegram_request(
        "sendMessage",
        payload
    )

    if not result:
        return None

    try:

        return result[
            "result"
        ][
            "message_id"
        ]

    except Exception:

        return None


# ============================================================
# INSTANT NEW BET UPDATE
# ============================================================

def send_instant_bet_update(
    bet
):

    """
    Sends a simple notification when an existing
    match receives a new bet.

    No amount, odds, selection or market are shown.
    """

    if INSTANT_UPDATE_TO_ALL_USERS:

        recipients = get_active_users()

    else:

        recipients = [
            ADMIN_ID
        ]

    if not recipients:
        return

    competitors = (
        bet.get("competitors")
        or []
    )

    if len(competitors) >= 2:

        match_name = " - ".join(
            competitors[:2]
        )

    else:

        match_name = bet.get(
            "event",
            "Unknown Match"
        )

    message = (

        "🚨 <b>ΝΕΟ BET</b>\n\n"

        f"⚽ <b>{escape_html(match_name)}</b>\n\n"

        "💰 Νέο μεγάλο στοίχημα παίχτηκε "
        "στο συγκεκριμένο match."
    )

    for user_id in recipients:

        message_id = send_to_user(
            user_id,
            message
        )

        if message_id:

            print(
                "[INSTANT UPDATE] "
                f"Sent to {user_id}: "
                f"{match_name}"
            )

        else:

            print(
                "[INSTANT UPDATE] "
                f"Failed for {user_id}: "
                f"{match_name}"
            )


# ============================================================
# SEND ALERT TO ALL USERS
# ============================================================

def send_telegram_message(
    text
):

    users = get_active_users()

    if not users:

        print(
            "[TELEGRAM] "
            "No active users."
        )

        return {}

    message_ids = {}

    for user_id in users:

        message_id = send_to_user(
            user_id,
            text
        )

        if message_id:

            message_ids[
                user_id
            ] = message_id

        else:

            print(
                "[TELEGRAM] "
                f"Could not send to "
                f"{user_id}"
            )

    return message_ids


# ============================================================
# EDIT ONE USER MESSAGE
# ============================================================

def edit_user_message(
    user_id,
    message_id,
    text
):

    payload = {

        "chat_id":
            user_id,

        "message_id":
            message_id,

        "text":
            text,

        "parse_mode":
            "HTML",

        "disable_web_page_preview":
            True,
    }

    result = telegram_request(
        "editMessageText",
        payload
    )

    return result is not None


# ============================================================
# PROCESS TELEGRAM UPDATES
# ============================================================

def process_telegram_updates():

    global telegram_update_offset

    payload = {
        "timeout": 1,
        "allowed_updates": [
            "message"
        ],
    }

    if telegram_update_offset:

        payload["offset"] = (
            telegram_update_offset
        )

    result = telegram_request(
        "getUpdates",
        payload
    )

    if not result:
        return

    updates = result.get(
        "result",
        []
    )

    for update in updates:

        telegram_update_offset = (
            update["update_id"] + 1
        )

        message = update.get(
            "message"
        )

        if not message:
            continue

        user = message.get(
            "from"
        ) or {}

        user_id = user.get(
            "id"
        )

        if not user_id:
            continue

        username = clean_text(
            user.get("username")
        )

        first_name = clean_text(
            user.get("first_name")
        )

        text = clean_text(
            message.get("text")
        )

        # ----------------------------------------------------
        # /START
        # ----------------------------------------------------

        if text == "/start":

            add_user(
                user_id,
                username,
                first_name
            )

            send_to_user(
                user_id,

                "✅ <b>ArtistRadar ενεργοποιήθηκε!</b>\n\n"

                "Από εδώ και πέρα θα λαμβάνεις "
                "αυτόματα ειδοποιήσεις για μεγάλα "
                "sports bets που εντοπίζει το Radar.\n\n"

                "💰 Minimum bet: "
                f"${MIN_AMOUNT_USDT}\n"

                "⚡ Live monitoring: ON\n\n"

                "Για διακοπή ειδοποιήσεων γράψε "
                "/stop"
            )

            print(
                "[USER] Added: "
                f"{user_id} "
                f"@{username}"
            )

        # ----------------------------------------------------
        # /STOP
        # ----------------------------------------------------

        elif text == "/stop":

            remove_user(
                user_id
            )

            send_to_user(
                user_id,

                "🔕 <b>Οι ειδοποιήσεις "
                "απενεργοποιήθηκαν.</b>\n\n"

                "Για να τις ενεργοποιήσεις ξανά, "
                "πάτησε /start"
            )

            print(
                "[USER] Deactivated: "
                f"{user_id}"
            )

        # ----------------------------------------------------
        # /USERS ADMIN
        # ----------------------------------------------------

        elif text == "/users":

            if user_id != ADMIN_ID:
                continue

            count = get_user_count()

            send_to_user(
                user_id,

                "👥 <b>ArtistRadar Users</b>\n\n"

                f"Active users: <b>{count}</b>"
            )


# ============================================================
# SEND SETTLED RESULT NOTIFICATION
# ============================================================

def send_result_notification(bet):

    bet_id = bet.get("id")
    if not bet_id or bet_id in result_notified_bet_ids:
        return

    status = clean_text(bet.get("outcome_status", "")).lower()
    if not is_settled_status(status):
        return

    if status in {"won", "win", "winner", "settled_won", "success"}:
        title = "✅ <b>ΚΕΡΔΙΣΕ</b>"
    elif status in {"lost", "loss", "loser", "settled_lost", "failed"}:
        title = "❌ <b>ΧΑΘΗΚΕ</b>"
    else:
        title = "↩️ <b>ΑΚΥΡΩΘΗΚΕ / VOID</b>"

    competitors = bet.get("competitors") or []
    event = " - ".join(competitors[:2]) if len(competitors) >= 2 else bet.get("event", "Unknown Match")

    payout = safe_float(bet.get("payout"), 0)
    payout_line = f"\n💵 Payout: ${format_money(payout)}" if payout > 0 else ""

    message = (
        f"{title}\n\n"
        f"⚡ <b>{escape_html(event)}</b>\n"
        f"🎯 {escape_html(bet.get('selection', 'Unknown'))}\n"
        f"📌 {escape_html(bet.get('market', 'Unknown market'))}\n"
        f"💰 Bet: ${format_money(bet.get('amount', 0))} x {format_odds(bet.get('odds', 0))}"
        f"{payout_line}"
    )

    recipients = get_active_users()
    for user_id in recipients:
        send_to_user(user_id, message)

    result_notified_bet_ids.add(bet_id)
    print(f"[RESULT NOTIFICATION] {event} | {status}")


# ============================================================
# PROCESS BET
# ============================================================

def process_bet(
    bet
):

    event_key = get_event_key(
        bet
    )

    # --------------------------------------------------------
    # CHECK IF EVENT ALREADY EXISTS
    # --------------------------------------------------------

    event_already_exists = (
        event_key in event_groups
    )

    # --------------------------------------------------------
    # CREATE EVENT
    # --------------------------------------------------------

    if not event_already_exists:

        event_groups[event_key] = (
            create_event_group(
                bet
            )
        )

    group = event_groups[
        event_key
    ]

    # --------------------------------------------------------
    # CHECK DUPLICATE BET
    # --------------------------------------------------------

    existing_ids = {

        x["id"]

        for x in group.get(
            "bets",
            []
        )
    }

    if bet["id"] in existing_ids:

        # Το ίδιο bet μπορεί να επιστρέψει αργότερα με
        # ενημερωμένο status (won/lost).
        for existing_bet in group.get("bets", []):

            if existing_bet.get("id") != bet["id"]:
                continue

            old_status = clean_text(
                existing_bet.get("outcome_status", "")
            ).lower()

            new_status = clean_text(
                bet.get("outcome_status", "")
            ).lower()

            if new_status and new_status != old_status:

                existing_bet.update(bet)

                # Send a separate result notification AND update the
                # original event message with the new icon.
                send_result_notification(bet)

                message = create_event_message(group)

                if message:

                    message_ids = group.get(
                        "telegram_message_ids",
                        {}
                    )

                    for user_id, message_id in message_ids.items():
                        edit_user_message(
                            user_id,
                            message_id,
                            message
                        )

                    print(
                        "[RESULT] "
                        f"{bet['event']} | "
                        f"{bet['selection']} | "
                        f"{old_status or 'pending'} -> {new_status}"
                    )

            break

        return

    # If a newly observed bet is already settled, notify it too.
    if is_settled_status(bet.get("outcome_status", "")):
        send_result_notification(bet)

    # --------------------------------------------------------
    # NEW BET ON EXISTING EVENT
    # --------------------------------------------------------

    if event_already_exists:

        send_instant_bet_update(
            bet
        )

    # --------------------------------------------------------
    # ADD BET
    # --------------------------------------------------------

    added = add_bet_to_group(
        group,
        bet
    )

    if not added:
        return

    # --------------------------------------------------------
    # CREATE UPDATED MESSAGE
    # --------------------------------------------------------

    message = create_event_message(
        group
    )

    if not message:
        return

    # ========================================================
    # USERS
    # ========================================================

    users = get_active_users()

    if not users:

        print(
            "[TELEGRAM] "
            "No active users."
        )

        return

    # ========================================================
    # SEND / EDIT FOR EACH USER
    # ========================================================

    message_ids = group.get(
        "telegram_message_ids",
        {}
    )

    for user_id in users:

        old_message_id = (
            message_ids.get(
                user_id
            )
        )

        # ----------------------------------------------------
        # NEW USER / NEW EVENT
        # ----------------------------------------------------

        if not old_message_id:

            new_message_id = (
                send_to_user(
                    user_id,
                    message
                )
            )

            if new_message_id:

                message_ids[
                    user_id
                ] = new_message_id

                print(
                    "[TELEGRAM] "
                    f"New event sent to "
                    f"{user_id}: "
                    f"{group['event']}"
                )

            continue

        # ----------------------------------------------------
        # UPDATE EXISTING EVENT
        # ----------------------------------------------------

        success = (
            edit_user_message(
                user_id,
                old_message_id,
                message
            )
        )

        if success:

            print(
                "[TELEGRAM] "
                f"Updated for "
                f"{user_id}: "
                f"{group['event']}"
            )

    group[
        "telegram_message_ids"
    ] = message_ids


# ============================================================
# SMART BACKOFF
# ============================================================

class SmartBackoff:

    def __init__(self):

        self.current = (
            BLOCK_RETRY_INITIAL
        )

    def wait(self):

        seconds = self.current

        print("")
        print(
            "[STAKE] 403 BLOCKED"
        )

        print(
            f"[STAKE] Waiting "
            f"{seconds} seconds..."
        )

        for remaining in range(
            seconds,
            0,
            -1
        ):

            print(
                f"\r[STAKE] Retry in "
                f"{remaining:4d}s",
                end="",
                flush=True
            )

            time.sleep(1)

        print("")

        self.current = min(
            self.current * 2,
            BLOCK_RETRY_MAX
        )

    def reset(self):

        self.current = (
            BLOCK_RETRY_INITIAL
        )


# ============================================================
# BANNER
# ============================================================

def print_banner():

    print("")
    print("=" * 65)

    print(
        f"STAKE RADAR {VERSION}"
    )

    print("=" * 65)

    print(
        f"Minimum bet: "
        f"${MIN_AMOUNT_USDT}"
    )

    print(
        "Currencies: USDT / USDC"
    )

    print(
        "SSL truststore: "
        + ("ON" if TRUSTSTORE_ENABLED else "system/default")
    )

    print(
        f"Polling: "
        f"{CHECK_EVERY}s"
    )

    print(
        f"Event history: "
        f"{EVENT_HISTORY_MINUTES} min"
    )

    print(
        f"Recent window: "
        f"{RECENT_BETS_MINUTES} min"
    )

    print(
        "Country filter: OFF"
    )

    print(
        "Competition filter: ON"
    )

    print(
        "Excluded: A' division except allowed countries + specified categories + "
        "Champions / Europa / Conference + tennis + baseball + cricket + "
        "American football + ALL esports"
    )

    print(
        "Bet result: ON (SportBet status + outcome status)"
    )

    print(
        "Whitelist: ON"
    )

    print(
        "Whitelist teams: PFC_Terdu / Sportivo_San_Lorenzo / Aktobe_Reserve / FC_Balti"
    )

    print(
        f"Whitelist banner: {WHITELIST_BANNER}"
    )

    print(
        "Telegram: MULTI USER"
    )

    print(
        "Instant bet updates: "
        + (
            "ALL USERS"
            if INSTANT_UPDATE_TO_ALL_USERS
            else "ADMIN ONLY"
        )
    )

    print(
        f"Active users: "
        f"{get_user_count()}"
    )

    print("=" * 65)
    print("")


# ============================================================
# MAIN
# ============================================================

def main():

    init_database()

    print_banner()

    if (
        not TELEGRAM_BOT_TOKEN
        or TELEGRAM_BOT_TOKEN
        == "PUT_YOUR_NEW_BOT_TOKEN_HERE"
    ):

        print(
            "[WARNING] Το TELEGRAM_BOT_TOKEN δεν έχει οριστεί."
        )
        print(
            '[WARNING] PowerShell: $env:TELEGRAM_BOT_TOKEN="YOUR_NEW_TOKEN"'
        )

        return

    backoff = SmartBackoff()

    first_run = True

    while True:

        try:

            # =================================================
            # TELEGRAM USERS
            # =================================================

            process_telegram_updates()

            # =================================================
            # STAKE
            # =================================================

            result = get_bets()

            status = result[
                "status"
            ]

            # =================================================
            # 403
            # =================================================

            if status == "blocked":

                backoff.wait()

                continue

            # =================================================
            # SUCCESS
            # =================================================

            if status == "ok":

                backoff.reset()

                raw_bets = result.get(
                    "bets",
                    []
                )

                normalized = []

                for raw in raw_bets:

                    bet = normalize_bet(
                        raw
                    )

                    if bet:

                        normalized.append(
                            bet
                        )

                print(
                    "[STAKE] Received: "
                    f"{len(raw_bets)} | "
                    f"Valid: "
                    f"{len(normalized)} | "
                    f"Events: "
                    f"{len(event_groups)} | "
                    f"Users: "
                    f"{get_user_count()}"
                )

                # =================================================
                # FIRST RUN
                # =================================================

                if first_run:

                    # Mark all currently visible bets as seen
                    for bet in normalized:

                        seen_bet_ids.add(
                            bet["id"]
                        )

                    # Build event groups silently.
                    # No Telegram messages are sent.
                    seeded_events, seeded_bets = (
                        seed_existing_events(
                            normalized
                        )
                    )

                    first_run = False

                    print(
                        "[STARTUP] Marked "
                        f"{len(normalized)} "
                        "existing bets as seen."
                    )

                    print(
                        "[STARTUP] Seeded "
                        f"{seeded_bets} bets "
                        f"across "
                        f"{seeded_events} events."
                    )

                # =================================================
                # NEW BETS
                # =================================================

                else:

                    new_count = 0

                    for bet in normalized:

                        if (
                            bet["id"]
                            in seen_bet_ids
                        ):

                            # Check whether an already-seen bet has
                            # been settled as WON/LOST.
                            if is_settled_status(
                                bet.get("outcome_status", "")
                            ):
                                process_bet(bet)

                            continue

                        seen_bet_ids.add(
                            bet["id"]
                        )

                        new_count += 1

                        print(
                            "[NEW BET] "
                            f"{bet['sport']} | "
                            f"{bet['event']} | "
                            f"{bet['selection']} | "
                            f"${format_money(bet['amount'])}"
                        )

                        process_bet(
                            bet
                        )

                    if new_count:

                        print(
                            f"[NEW] "
                            f"{new_count} "
                            "new bet(s)"
                        )

                # =================================================
                # CLEAN OLD EVENTS
                # =================================================

                cleanup_all_events()

            # =================================================
            # NETWORK
            # =================================================

            elif status == "network":

                print(
                    "[STAKE] Network error: "
                    f"{result.get('error')}"
                )

            # =================================================
            # HTTP
            # =================================================

            elif status == "http":

                print(
                    "[STAKE] HTTP error: "
                    f"{result.get('error')}"
                )

            # =================================================
            # GRAPHQL
            # =================================================

            elif status == "graphql":

                print(
                    "[STAKE] GraphQL error:"
                )

                print(
                    result.get(
                        "error"
                    )
                )

            # =================================================
            # JSON
            # =================================================

            elif status == "json":

                print(
                    "[STAKE] Invalid JSON"
                )

            # =================================================
            # OTHER
            # =================================================

            else:

                print(
                    "[STAKE] Error: "
                    f"{result.get('error')}"
                )

            # =================================================
            # NORMAL POLLING
            # =================================================

            time.sleep(
                CHECK_EVERY
            )

        except KeyboardInterrupt:

            print("")
            print(
                "Stake Radar stopped."
            )

            break

        except Exception as e:

            print("")
            print(
                f"[MAIN ERROR] "
                f"{type(e).__name__}: {e}"
            )

            time.sleep(
                CHECK_EVERY
            )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()