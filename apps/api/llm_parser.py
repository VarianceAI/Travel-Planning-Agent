"""
LLM-powered trip parser with rule-based fallback when no API key is set.
"""
import json
import os
import re
from datetime import date, timedelta

from models import ParsedTrip, FlightConstraints, HotelConstraints

# ── City → IATA mapping ──────────────────────────────────────────────────────
CITY_TO_IATA: dict[str, str] = {
    "new york": "NYC", "nyc": "NYC", "new york city": "NYC",
    "miami": "MIA", "los angeles": "LAX", "la": "LAX",
    "chicago": "CHI", "san francisco": "SFO", "sf": "SFO",
    "tokyo": "TYO", "london": "LON", "paris": "PAR",
    "seattle": "SEA", "boston": "BOS", "denver": "DEN",
    "las vegas": "LAS", "orlando": "MCO", "atlanta": "ATL",
    "dallas": "DFW", "houston": "IAH", "phoenix": "PHX",
    "barcelona": "BCN", "rome": "ROM", "amsterdam": "AMS",
    "dubai": "DXB", "singapore": "SIN", "sydney": "SYD",
    "cancun": "CUN", "mexico city": "MEX", "toronto": "YYZ",
    "montreal": "YUL", "vancouver": "YVR", "miami beach": "MIA",
}

MONTH_MAP: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _resolve_city(text: str) -> str:
    t = text.lower().strip()
    for name, code in CITY_TO_IATA.items():
        if name in t:
            return code
    # uppercase 3-letter code already present
    m = re.search(r"\b([A-Z]{3})\b", text)
    if m:
        return m.group(1)
    return t[:3].upper()


def _parse_dates(text: str) -> tuple[date, date]:
    t = text.lower()
    today = date.today()
    year = today.year

    # extract explicit year
    ym = re.search(r"\b(202[5-9])\b", t)
    if ym:
        year = int(ym.group(1))

    # "early/mid/late <month>"
    for prefix, (day_start, day_end) in [
        ("early", (1, 10)), ("mid", (10, 20)), ("late", (20, -1))
    ]:
        for mname, mnum in MONTH_MAP.items():
            if f"{prefix} {mname}" in t:
                _, last = _month_range(year, mnum)
                end = date(year, mnum, last) if day_end == -1 else date(year, mnum, day_end)
                return date(year, mnum, day_start), end

    # bare month name
    for mname, mnum in MONTH_MAP.items():
        if re.search(rf"\b{mname}\b", t):
            start, last = _month_range(year, mnum)
            return date(year, mnum, 1), date(year, mnum, last)

    # fall back to next month
    nxt = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    _, last = _month_range(nxt.year, nxt.month)
    return nxt, date(nxt.year, nxt.month, last)


def _month_range(year: int, month: int) -> tuple[int, int]:
    import calendar
    _, last = calendar.monthrange(year, month)
    return 1, last


def _parse_trip_length(text: str) -> tuple[int, int]:
    t = text.lower()
    # "5-7 days" or "5 to 7 days"
    m = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*day", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    # "5 days" / "a week"
    m = re.search(r"(\d+)\s*day", t)
    if m:
        n = int(m.group(1))
        return n, n
    if "week" in t:
        return 7, 7
    return 5, 7  # default


def _parse_budget(text: str) -> float | None:
    m = re.search(r"\$\s*(\d[\d,]*)", text)
    if m:
        return float(m.group(1).replace(",", ""))
    m = re.search(r"under\s+(\d[\d,]+)", text.lower())
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def _parse_neighborhoods(text: str) -> list[str]:
    known = [
        "south beach", "mid-beach", "downtown", "brickell", "wynwood",
        "midtown", "upper east side", "tribeca", "soho", "brooklyn",
        "beverly hills", "santa monica", "hollywood", "venice",
        "old town", "city center", "harbor",
    ]
    t = text.lower()
    return [n.title() for n in known if n in t]


def _parse_min_star(text: str) -> float | None:
    m = re.search(r"(\d(?:\.\d)?)\s*[\-\s]*star", text.lower())
    if m:
        return float(m.group(1))
    if "luxury" in text.lower():
        return 4.0
    return None


# ── Rule-based parser ─────────────────────────────────────────────────────────
def _rule_based_parse(raw: str) -> ParsedTrip:
    t = raw.lower()

    # Destination: look for "in <city>", "to <city>", "visiting <city>"
    dest = "NYC"
    for pattern in [r"(?:in|to|visit(?:ing)?)\s+([a-z\s]+?)(?:,|\.|for|\bfrom\b|during|$)"]:
        m = re.search(pattern, t)
        if m:
            candidate = _resolve_city(m.group(1).strip())
            if candidate != "NYC":  # don't use default
                dest = candidate
                break

    # Origin: look for "from <city>"
    origin = "NYC"
    m = re.search(r"from\s+([a-z\s]+?)(?:,|\.|during|in\b|$)", t)
    if m:
        origin = _resolve_city(m.group(1).strip())

    # Swap if origin == dest (parsing error)
    if origin == dest:
        origin = "NYC"

    date_start, date_end = _parse_dates(raw)
    length_min, length_max = _parse_trip_length(raw)
    budget = _parse_budget(raw)
    neighborhoods = _parse_neighborhoods(raw)
    min_star = _parse_min_star(raw)
    direct_only = any(w in t for w in ["direct", "nonstop", "non-stop", "no stop"])

    return ParsedTrip(
        origin=origin,
        destination=dest,
        date_range_start=date_start,
        date_range_end=date_end,
        trip_length_min=length_min,
        trip_length_max=length_max,
        budget=budget,
        flight_constraints=FlightConstraints(direct_only=direct_only),
        hotel_constraints=HotelConstraints(
            min_star=min_star,
            preferred_neighborhoods=neighborhoods,
        ),
    )


# ── LLM parser ────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a travel planning assistant. Extract structured trip constraints from the user's natural language request.

Return ONLY a valid JSON object with these fields:
{
  "origin": "IATA city code (e.g. NYC, LAX)",
  "destination": "IATA city code (e.g. MIA, TYO)",
  "date_range_start": "YYYY-MM-DD",
  "date_range_end": "YYYY-MM-DD",
  "trip_length_min": integer (days),
  "trip_length_max": integer (days),
  "budget": float or null (total trip budget in USD),
  "flight_constraints": {
    "direct_only": boolean,
    "max_stops": integer or null,
    "preferred_airlines": []
  },
  "hotel_constraints": {
    "min_star": float or null,
    "max_star": float or null,
    "preferred_neighborhoods": ["list of neighborhood names mentioned"]
  }
}

Rules:
- For vague dates like "May 2026", use the full month: date_range_start=2026-05-01, date_range_end=2026-05-31
- For "late May", use 2026-05-20 to 2026-05-31
- For "early May", use 2026-05-01 to 2026-05-15
- For a fixed trip length like "5 days", set both min and max to 5
- For "5-7 days", set min=5, max=7
- Map city names to IATA codes: New York/NYC→NYC, Miami→MIA, Los Angeles→LAX, Tokyo→TYO, London→LON, Paris→PAR, Chicago→CHI, etc.
- "prefer south beach" → hotel_constraints.preferred_neighborhoods=["South Beach"]
- "direct flights only" → flight_constraints.direct_only=true
- If budget is not mentioned, set to null"""


def _llm_parse(raw: str) -> ParsedTrip:
    import anthropic
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": raw}],
    )
    text = message.content[0].text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if m:
        text = m.group(1)

    data = json.loads(text)
    data["date_range_start"] = date.fromisoformat(data["date_range_start"])
    data["date_range_end"] = date.fromisoformat(data["date_range_end"])

    return ParsedTrip(
        origin=data["origin"],
        destination=data["destination"],
        date_range_start=data["date_range_start"],
        date_range_end=data["date_range_end"],
        trip_length_min=int(data["trip_length_min"]),
        trip_length_max=int(data["trip_length_max"]),
        budget=data.get("budget"),
        flight_constraints=FlightConstraints(**data.get("flight_constraints", {})),
        hotel_constraints=HotelConstraints(**data.get("hotel_constraints", {})),
    )


def parse_trip(raw_query: str) -> ParsedTrip:
    """Parse free-form trip request. Uses Claude if API key is set, else rule-based parser."""
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return _llm_parse(raw_query)
        except Exception:
            pass  # fall through to rule-based
    return _rule_based_parse(raw_query)
