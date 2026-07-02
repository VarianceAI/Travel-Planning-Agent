"""SerpAPI adapter — Google Flights + Google Hotels with mock fallback."""
import os
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Optional
import httpx

from models import FlightOffer, HotelOffer

SERPAPI_BASE = "https://serpapi.com/search.json"

# City codes (used internally) → primary airport code (used by Google Flights)
CITY_TO_AIRPORT: dict[str, str] = {
    "NYC": "JFK", "LAX": "LAX", "CHI": "ORD", "SFO": "SFO",
    "MIA": "MIA", "SEA": "SEA", "BOS": "BOS", "DEN": "DEN",
    "LAS": "LAS", "MCO": "MCO", "ATL": "ATL", "DFW": "DFW",
    "IAH": "IAH", "PHX": "PHX", "TYO": "NRT", "LON": "LHR",
    "PAR": "CDG", "BCN": "BCN", "ROM": "FCO", "AMS": "AMS",
    "DXB": "DXB", "SIN": "SIN", "SYD": "SYD", "CUN": "CUN",
    "MEX": "MEX", "YYZ": "YYZ", "YUL": "YUL", "YVR": "YVR",
}

CITY_NAMES: dict[str, str] = {
    "MIA": "Miami", "NYC": "New York", "LAX": "Los Angeles",
    "CHI": "Chicago", "SFO": "San Francisco", "TYO": "Tokyo",
    "LON": "London", "PAR": "Paris", "SEA": "Seattle",
    "BOS": "Boston", "DEN": "Denver", "LAS": "Las Vegas",
    "MCO": "Orlando", "ATL": "Atlanta", "DFW": "Dallas",
}


def _api_key() -> Optional[str]:
    return os.getenv("SERPAPI_KEY")


def _airport(city_code: str) -> str:
    return CITY_TO_AIRPORT.get(city_code, city_code)


# ── Flights ───────────────────────────────────────────────────────────────────

async def fetch_flights(
    origin: str,
    destination: str,
    departure_date: date,
    return_date: Optional[date] = None,
    adults: int = 1,
    direct_only: bool = False,
) -> list[FlightOffer]:
    key = _api_key()
    if key:
        result = await _serpapi_flights(key, origin, destination, departure_date, return_date, direct_only)
        if result:
            return result
    return _mock_flights(origin, destination, departure_date, return_date, direct_only)


async def _serpapi_flights(
    key: str,
    origin: str,
    destination: str,
    departure_date: date,
    return_date: Optional[date],
    direct_only: bool,
) -> list[FlightOffer]:
    params = {
        "engine": "google_flights",
        "departure_id": _airport(origin),
        "arrival_id": _airport(destination),
        "outbound_date": departure_date.isoformat(),
        "currency": "USD",
        "hl": "en",
        "api_key": key,
    }
    if return_date:
        params["return_date"] = return_date.isoformat()
        params["type"] = "1"  # round trip
    else:
        params["type"] = "2"  # one way

    if direct_only:
        params["stops"] = "1"  # 0=any, 1=nonstop, 2=1stop, 3=2stops

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(SERPAPI_BASE, params=params, timeout=20)
        if resp.status_code != 200:
            return []

        data = resp.json()
        offers = []

        # SerpAPI returns best_flights and other_flights
        for bucket in ("best_flights", "other_flights"):
            for item in data.get(bucket, []):
                offer = _parse_flight_item(item, origin, destination, return_date)
                if offer:
                    offers.append(offer)

        return offers
    except Exception:
        return []


def _parse_flight_item(
    item: dict,
    origin: str,
    destination: str,
    return_date: Optional[date],
) -> Optional[FlightOffer]:
    try:
        price = float(item.get("price", 0))
        if price <= 0:
            return None

        flights = item.get("flights", [])
        if not flights:
            return None

        first_seg = flights[0]
        last_seg = flights[-1]

        dep_time = _parse_dt(first_seg["departure_airport"]["time"])
        arr_time = _parse_dt(last_seg["arrival_airport"]["time"])
        stops = len(flights) - 1
        airline = first_seg.get("airline", "")

        # Return leg
        ret_dep = ret_arr = None
        return_flights = item.get("return_flights", [])
        if return_flights:
            ret_dep = _parse_dt(return_flights[0]["departure_airport"]["time"])
            ret_arr = _parse_dt(return_flights[-1]["arrival_airport"]["time"])

        return FlightOffer(
            provider="google_flights",
            offer_id=str(uuid.uuid4()),
            origin=origin,
            destination=destination,
            departure_time=dep_time,
            arrival_time=arr_time,
            return_departure_time=ret_dep,
            return_arrival_time=ret_arr,
            total_price=price,
            stops=stops,
            airline=airline,
            is_round_trip=return_date is not None,
        )
    except Exception:
        return None


def _parse_dt(s: str) -> datetime:
    # SerpAPI format: "2026-05-10 06:00" or "2026-05-10 06:00 +1"
    s = re.sub(r"\s*[+-]\d+$", "", s.strip())
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


# ── Hotels ────────────────────────────────────────────────────────────────────

async def fetch_hotels(
    destination: str,
    check_in: date,
    check_out: date,
    adults: int = 1,
    min_star: Optional[float] = None,
    preferred_neighborhoods: Optional[list[str]] = None,
) -> list[HotelOffer]:
    key = _api_key()
    if key:
        result = await _serpapi_hotels(
            key, destination, check_in, check_out, adults, min_star, preferred_neighborhoods
        )
        if result:
            return result
    return _mock_hotels(destination, check_in, check_out, min_star, preferred_neighborhoods)


async def _serpapi_hotels(
    key: str,
    destination: str,
    check_in: date,
    check_out: date,
    adults: int,
    min_star: Optional[float],
    preferred_neighborhoods: Optional[list[str]],
) -> list[HotelOffer]:
    city = CITY_NAMES.get(destination, destination)

    # Add neighborhood to query if specified
    neighborhood = (preferred_neighborhoods or [None])[0]
    query = f"hotels in {neighborhood + ' ' if neighborhood else ''}{city}"

    params = {
        "engine": "google_hotels",
        "q": query,
        "check_in_date": check_in.isoformat(),
        "check_out_date": check_out.isoformat(),
        "adults": adults,
        "currency": "USD",
        "hl": "en",
        "api_key": key,
    }
    if min_star:
        # Google Hotels rating filter: 35=3.5+, 40=4+, 45=4.5+
        params["rating"] = "40" if min_star >= 4 else "35"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(SERPAPI_BASE, params=params, timeout=20)
        if resp.status_code != 200:
            return []

        data = resp.json()
        nights = max((check_out - check_in).days, 1)
        offers = []

        for prop in data.get("properties", []):
            offer = _parse_hotel_item(prop, check_in, check_out, nights, min_star)
            if offer:
                offers.append(offer)

        return offers
    except Exception:
        return []


def _parse_hotel_item(
    prop: dict,
    check_in: date,
    check_out: date,
    nights: int,
    min_star: Optional[float],
) -> Optional[HotelOffer]:
    try:
        name = prop.get("name", "")
        if not name:
            return None

        # Star rating
        hotel_class = prop.get("extracted_hotel_class")
        star = float(hotel_class) if hotel_class else None
        if min_star and star and star < min_star:
            return None

        # Price — prefer total_rate, fall back to rate_per_night
        total_rate = prop.get("total_rate", {})
        nightly_rate = prop.get("rate_per_night", {})

        total_price = float(total_rate.get("extracted_lowest") or 0)
        nightly_price = float(nightly_rate.get("extracted_lowest") or 0)

        if total_price <= 0 and nightly_price <= 0:
            return None

        if total_price <= 0:
            total_price = round(nightly_price * nights, 2)
        if nightly_price <= 0:
            nightly_price = round(total_price / nights, 2)

        neighborhood = None
        for place in prop.get("nearby_places", []):
            if place.get("transportation", []):
                neighborhood = place.get("name")
                break

        return HotelOffer(
            provider="google_hotels",
            offer_id=str(uuid.uuid4()),
            name=name,
            check_in=check_in,
            check_out=check_out,
            nightly_price=nightly_price,
            total_price=total_price,
            star_rating=star,
            neighborhood=neighborhood,
            address=None,
        )
    except Exception:
        return None


# ── Mock fallback ─────────────────────────────────────────────────────────────

def _mock_flights(
    origin: str,
    destination: str,
    departure_date: date,
    return_date: Optional[date],
    direct_only: bool,
) -> list[FlightOffer]:
    import random
    rng = random.Random(str(departure_date) + origin + destination)
    options = [
        {"airline": "AA", "base": 220, "stops": 0, "duration_h": 3.5},
        {"airline": "DL", "base": 195, "stops": 0, "duration_h": 3.0},
        {"airline": "UA", "base": 175, "stops": 1, "duration_h": 5.5},
        {"airline": "B6", "base": 160, "stops": 0, "duration_h": 3.2},
        {"airline": "WN", "base": 140, "stops": 1, "duration_h": 6.0},
    ]
    offers = []
    for opt in options:
        if direct_only and opt["stops"] > 0:
            continue
        price = round(opt["base"] * rng.uniform(0.85, 1.15) * 2, 2)
        dep_hour = rng.choice([6, 9, 12, 15, 18])
        dep_time = datetime(departure_date.year, departure_date.month, departure_date.day, dep_hour)
        arr_time = dep_time + timedelta(hours=opt["duration_h"])
        ret_dep = ret_arr = None
        if return_date:
            rh = rng.choice([8, 11, 14, 17, 20])
            ret_dep = datetime(return_date.year, return_date.month, return_date.day, rh)
            ret_arr = ret_dep + timedelta(hours=opt["duration_h"])
        offers.append(FlightOffer(
            provider="mock", offer_id=str(uuid.uuid4()),
            origin=origin, destination=destination,
            departure_time=dep_time, arrival_time=arr_time,
            return_departure_time=ret_dep, return_arrival_time=ret_arr,
            total_price=price, stops=opt["stops"], airline=opt["airline"],
            is_round_trip=return_date is not None,
        ))
    return offers


def _mock_hotels(
    destination: str,
    check_in: date,
    check_out: date,
    min_star: Optional[float],
    preferred_neighborhoods: Optional[list[str]],
) -> list[HotelOffer]:
    import random
    rng = random.Random(str(check_in) + destination)
    nights = max((check_out - check_in).days, 1)
    templates = {
        "MIA": [
            {"name": "The Setai Miami Beach", "nightly": 420, "stars": 5.0, "neighborhood": "South Beach"},
            {"name": "1 Hotel South Beach", "nightly": 380, "stars": 4.5, "neighborhood": "South Beach"},
            {"name": "Loews Miami Beach Hotel", "nightly": 280, "stars": 4.0, "neighborhood": "South Beach"},
            {"name": "Marriott Biscayne Bay", "nightly": 220, "stars": 4.0, "neighborhood": "Downtown"},
            {"name": "citizenM Miami Worldcenter", "nightly": 160, "stars": 3.5, "neighborhood": "Downtown"},
            {"name": "Hampton Inn Miami Airport", "nightly": 120, "stars": 3.0, "neighborhood": "Airport"},
        ],
    }.get(destination, [
        {"name": f"{destination} Grand Hotel", "nightly": 200, "stars": 4.0, "neighborhood": "City Center"},
        {"name": f"{destination} Budget Inn", "nightly": 90, "stars": 2.5, "neighborhood": "Suburbs"},
        {"name": f"Boutique {destination}", "nightly": 170, "stars": 3.5, "neighborhood": "Old Town"},
    ])
    offers = []
    for t in templates:
        if min_star and t["stars"] < min_star:
            continue
        nightly = round(t["nightly"] * rng.uniform(0.9, 1.1), 2)
        offers.append(HotelOffer(
            provider="mock", offer_id=str(uuid.uuid4()),
            name=t["name"], check_in=check_in, check_out=check_out,
            nightly_price=nightly, total_price=round(nightly * nights, 2),
            star_rating=t["stars"], neighborhood=t.get("neighborhood"),
        ))
    return offers
