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
    "miami": "MIA", "miami beach": "MIA",
    "los angeles": "LAX", "la": "LAX",
    "chicago": "CHI", "san francisco": "SFO", "sf": "SFO",
    "tokyo": "TYO", "london": "LON", "paris": "PAR",
    "seattle": "SEA", "boston": "BOS", "denver": "DEN",
    "las vegas": "LAS", "orlando": "MCO", "atlanta": "ATL",
    "dallas": "DFW", "houston": "IAH", "phoenix": "PHX",
    "barcelona": "BCN", "rome": "ROM", "amsterdam": "AMS",
    "dubai": "DXB", "singapore": "SIN", "sydney": "SYD",
    "cancun": "CUN", "mexico city": "MEX", "toronto": "YYZ",
    "montreal": "YUL", "vancouver": "YVR",
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
    m = re.search(r"\b([A-Z]{3})\b", text)
    if m:
        return m.group(1)
    return t[:3].upper()


def _parse_dates(text: str) -> tuple[date, date]:
    t = text.lower()
    today = date.today()
    year = today.year

    ym = re.search(r"\b(202[5-9])\b", t)
    if ym:
        year = int(ym.group(1))

    for prefix, (day_start, day_end) in [
        ("early", (1, 10)), ("mid", (10, 20)), ("late", (20, -1))
    ]:
        for mname, mnum in MONTH_MAP.items():
            if f"{prefix} {mname}" in t:
                _, last = _month_range(year, mnum)
                end = date(year, mnum, last) if day_end == -1 else date(year, mnum, day_end)
                return date(year, mnum, day_start), end

    for mname, mnum in MONTH_MAP.items():
        if re.search(rf"\b{mname}\b", t):
            _, last = _month_range(year, mnum)
            return date(year, mnum, 1), date(year, mnum, last)

    nxt = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    _, last = _month_range(nxt.year, nxt.month)
    return nxt, date(nxt.year, nxt.month, last)


def _month_range(year: int, month: int) -> tuple[int, int]:
    import calendar
    _, last = calendar.monthrange(year, month)
    return 1, last


def _parse_trip_length(text: str) -> tuple[int, int]:
    t = text.lower()
    m = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*day", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+)\s*day", t)
    if m:
        n = int(m.group(1))
        return n, n
    if "week" in t:
        return 7, 7
    return 5, 7


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


def _parse_hotel_level(text: str) -> str | None:
    t = text.lower()
    if any(w in t for w in ["luxury", "5-star", "5 star", "high-end", "upscale resort"]):
        return "luxury"
    if any(w in t for w in ["upscale", "4-star", "4 star", "nice hotel", "good hotel"]):
        return "upscale"
    if any(w in t for w in ["budget", "cheap", "hostel", "affordable", "backpacker"]):
        return "budget"
    if any(w in t for w in ["mid-range", "moderate", "3-star", "3 star"]):
        return "mid"
    return None


def _parse_cabin_class(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["first class", "first-class"]):
        return "first"
    if any(w in t for w in ["business class", "business-class"]):
        return "business"
    if any(w in t for w in ["premium economy", "premium-economy"]):
        return "premium_economy"
    return "economy"


def _parse_amenities(text: str) -> list[str]:
    known = {
        "pool": ["pool", "swimming"],
        "gym": ["gym", "fitness", "workout"],
        "breakfast": ["breakfast included", "breakfast"],
        "spa": ["spa"],
        "parking": ["parking", "self-park"],
        "pet friendly": ["pet friendly", "pet-friendly", "pets allowed"],
        "wifi": ["free wifi", "free internet"],
        "airport shuttle": ["airport shuttle", "shuttle"],
        "beachfront": ["beachfront", "beach front", "on the beach"],
    }
    t = text.lower()
    return [amenity for amenity, keywords in known.items() if any(k in t for k in keywords)]


def _parse_travelers(text: str) -> int:
    t = text.lower()
    m = re.search(r"(\d+)\s*(?:people|persons?|adults?|travelers?|passengers?|guests?|pax)", t)
    if m:
        return int(m.group(1))
    if "couple" in t or "two of us" in t or "the two" in t:
        return 2
    if "family" in t:
        return 4
    if "solo" in t or "just me" in t or "myself" in t:
        return 1
    return 1


def _parse_round_trip(text: str) -> bool:
    t = text.lower()
    if any(w in t for w in ["one way", "one-way", "oneway"]):
        return False
    return True  # default to round trip


def _parse_special_requirements(text: str) -> list[str]:
    known = [
        "wheelchair accessible", "wheelchair", "accessible",
        "pet friendly", "pet-friendly",
        "child friendly", "family friendly",
        "vegan", "vegetarian", "halal", "kosher",
        "no resort fees", "all-inclusive", "all inclusive",
    ]
    t = text.lower()
    return [r for r in known if r in t]


# ── Rule-based parser ─────────────────────────────────────────────────────────
def _rule_based_parse(raw: str) -> ParsedTrip:
    t = raw.lower()

    # Origin: "from <city>"
    origin = "NYC"
    origin_span = None
    m = re.search(r"from\s+([a-z][a-z\s]+?)(?:\s*,|\s*\.|\s+during|\s+in\b|\s+for\b|$)", t)
    if m:
        origin = _resolve_city(m.group(1).strip())
        origin_span = m.span()

    # Destination: try multiple patterns in priority order
    dest = None
    dest_patterns = [
        r"(?:staying|trip|vacation|travel|going|fly)\s+(?:in|to)\s+([a-z][a-z\s]+?)(?:\s*,|\s*\.|\s+for\b|\s+from\b|\s+during|$)",
        r"(?:^|price\s+for\s+|best\s+(?:price\s+)?for\s+)([a-z][a-z\s]+?)\s+(?:\d+\s*day|for\s+\d)",
        r"(?:in|to|visit(?:ing)?)\s+([a-z][a-z\s]+?)(?:\s*,|\s*\.|\s+for\b|\s+from\b|\s+during|$)",
    ]
    for pattern in dest_patterns:
        for m in re.finditer(pattern, t):
            if origin_span and m.start(1) >= origin_span[0] and m.start(1) <= origin_span[1]:
                continue
            candidate = _resolve_city(m.group(1).strip())
            if candidate and candidate != origin:
                dest = candidate
                break
        if dest:
            break

    if not dest:
        for name, code in CITY_TO_IATA.items():
            if name in t and code != origin:
                dest = code
                break

    dest = dest or "MIA"

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
        is_round_trip=_parse_round_trip(raw),
        travelers=_parse_travelers(raw),
        budget=budget,
        flight_constraints=FlightConstraints(
            direct_only=direct_only,
            cabin_class=_parse_cabin_class(raw),
        ),
        hotel_constraints=HotelConstraints(
            min_star=min_star,
            level=_parse_hotel_level(raw),
            preferred_neighborhoods=neighborhoods,
            required_amenities=_parse_amenities(raw),
        ),
        special_requirements=_parse_special_requirements(raw),
    )


# ── LLM parser ────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a travel planning assistant. Extract structured trip constraints from the user's natural language request.

Return ONLY a valid JSON object with exactly these fields:
{
  "origin": "IATA city code (e.g. NYC, LAX)",
  "destination": "IATA city code (e.g. MIA, TYO)",
  "date_range_start": "YYYY-MM-DD",
  "date_range_end": "YYYY-MM-DD",
  "trip_length_min": integer (days),
  "trip_length_max": integer (days),
  "is_round_trip": boolean,
  "travelers": integer (number of adult travelers, default 1),
  "budget": float or null (total trip budget in USD, for all travelers),
  "budget_per_person": float or null (per-person budget if explicitly stated),
  "flight_constraints": {
    "direct_only": boolean,
    "max_stops": integer or null,
    "cabin_class": "economy" | "premium_economy" | "business" | "first",
    "preferred_airlines": [],
    "excluded_airlines": [],
    "max_duration_hours": float or null
  },
  "hotel_constraints": {
    "min_star": float or null,
    "max_star": float or null,
    "level": "budget" | "mid" | "upscale" | "luxury" | null,
    "preferred_neighborhoods": [],
    "required_amenities": [],
    "preferred_brands": [],
    "max_nightly_rate": float or null
  },
  "special_requirements": []
}

Rules:
- Dates: "May 2026"→full month 2026-05-01/2026-05-31; "late May"→2026-05-20/2026-05-31; "early May"→2026-05-01/2026-05-15
- Trip length: "5 days"→min=max=5; "5-7 days"→min=5,max=7; "a week"→min=max=7
- City → IATA: New York/NYC→NYC, Miami→MIA, LA→LAX, Chicago→CHI, SF→SFO, Tokyo→TYO, London→LON, Paris→PAR
- is_round_trip: false only if user says "one way" / "one-way"
- travelers: "couple"→2, "family"→4, "solo"→1, default 1
- cabin_class: default "economy" unless stated
- level: infer from keywords — "luxury"/"5-star"→luxury, "4-star"/"upscale"→upscale, "budget"/"cheap"→budget, "3-star"/"moderate"→mid
- required_amenities: extract ["pool","gym","breakfast","spa","parking","beachfront","pet friendly","wifi"] if mentioned
- special_requirements: capture anything else not covered above (e.g. "wheelchair accessible", "all-inclusive", "halal food")
- budget: null if not mentioned; if user says "under $2000 each" with 2 travelers → budget=4000, budget_per_person=2000
- preferred_neighborhoods: extract specific neighborhoods or areas mentioned (e.g. "South Beach", "Downtown", "near Times Square")"""


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
        is_round_trip=data.get("is_round_trip", True),
        travelers=int(data.get("travelers", 1)),
        budget=data.get("budget"),
        budget_per_person=data.get("budget_per_person"),
        flight_constraints=FlightConstraints(**data.get("flight_constraints", {})),
        hotel_constraints=HotelConstraints(**data.get("hotel_constraints", {})),
        special_requirements=data.get("special_requirements", []),
    )


def parse_trip(raw_query: str) -> ParsedTrip:
    """Parse free-form trip request. Uses Claude if API key is set, else rule-based parser."""
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return _llm_parse(raw_query)
        except Exception:
            pass
    return _rule_based_parse(raw_query)
