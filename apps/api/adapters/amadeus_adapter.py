"""Amadeus flight search adapter (real API + mock fallback)."""
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Optional
import httpx

from models import FlightOffer, HotelOffer

AMADEUS_AUTH_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
AMADEUS_FLIGHT_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"
AMADEUS_HOTEL_SEARCH_URL = "https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city"
AMADEUS_HOTEL_OFFERS_URL = "https://test.api.amadeus.com/v3/shopping/hotel-offers"

_token_cache: dict = {}


async def _get_token(client: httpx.AsyncClient) -> Optional[str]:
    key = os.getenv("AMADEUS_API_KEY")
    secret = os.getenv("AMADEUS_API_SECRET")
    if not key or not secret:
        return None
    cached = _token_cache.get("token")
    if cached and _token_cache.get("expires_at", 0) > datetime.utcnow().timestamp():
        return cached
    resp = await client.post(
        AMADEUS_AUTH_URL,
        data={"grant_type": "client_credentials", "client_id": key, "client_secret": secret},
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    body = resp.json()
    _token_cache["token"] = body["access_token"]
    _token_cache["expires_at"] = datetime.utcnow().timestamp() + body.get("expires_in", 1799)
    return body["access_token"]


async def fetch_flights(
    origin: str,
    destination: str,
    departure_date: date,
    return_date: Optional[date] = None,
    adults: int = 1,
    direct_only: bool = False,
) -> list[FlightOffer]:
    async with httpx.AsyncClient() as client:
        token = await _get_token(client)
        if token:
            return await _fetch_amadeus_flights(
                client, token, origin, destination, departure_date, return_date, adults, direct_only
            )
    return _mock_flights(origin, destination, departure_date, return_date, direct_only)


async def _fetch_amadeus_flights(
    client: httpx.AsyncClient,
    token: str,
    origin: str,
    destination: str,
    departure_date: date,
    return_date: Optional[date],
    adults: int,
    direct_only: bool,
) -> list[FlightOffer]:
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": departure_date.isoformat(),
        "adults": adults,
        "max": 10,
        "currencyCode": "USD",
    }
    if return_date:
        params["returnDate"] = return_date.isoformat()
    if direct_only:
        params["nonStop"] = "true"

    try:
        resp = await client.get(
            AMADEUS_FLIGHT_URL,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=15,
        )
        if resp.status_code != 200:
            return _mock_flights(origin, destination, departure_date, return_date, direct_only)

        offers = []
        for item in resp.json().get("data", []):
            price = float(item["price"]["grandTotal"])
            itineraries = item.get("itineraries", [])
            if not itineraries:
                continue
            out = itineraries[0]
            out_segs = out["segments"]
            dep = datetime.fromisoformat(out_segs[0]["departure"]["at"])
            arr = datetime.fromisoformat(out_segs[-1]["arrival"]["at"])
            stops = len(out_segs) - 1
            airline = out_segs[0].get("carrierCode", "")

            ret_dep = ret_arr = None
            if len(itineraries) > 1:
                ret_segs = itineraries[1]["segments"]
                ret_dep = datetime.fromisoformat(ret_segs[0]["departure"]["at"])
                ret_arr = datetime.fromisoformat(ret_segs[-1]["arrival"]["at"])

            offers.append(
                FlightOffer(
                    provider="amadeus",
                    offer_id=item["id"],
                    origin=origin,
                    destination=destination,
                    departure_time=dep,
                    arrival_time=arr,
                    return_departure_time=ret_dep,
                    return_arrival_time=ret_arr,
                    total_price=price,
                    stops=stops,
                    airline=airline,
                    is_round_trip=return_date is not None,
                )
            )
        return offers if offers else _mock_flights(origin, destination, departure_date, return_date, direct_only)
    except Exception:
        return _mock_flights(origin, destination, departure_date, return_date, direct_only)


def _mock_flights(
    origin: str,
    destination: str,
    departure_date: date,
    return_date: Optional[date],
    direct_only: bool,
) -> list[FlightOffer]:
    import random
    rng = random.Random(str(departure_date) + origin + destination)

    offers = []
    flight_options = [
        {"airline": "AA", "base": 220, "stops": 0, "duration_h": 3.5},
        {"airline": "DL", "base": 195, "stops": 0, "duration_h": 3.0},
        {"airline": "UA", "base": 175, "stops": 1, "duration_h": 5.5},
        {"airline": "B6", "base": 160, "stops": 0, "duration_h": 3.2},
        {"airline": "WN", "base": 140, "stops": 1, "duration_h": 6.0},
    ]

    for opt in flight_options:
        if direct_only and opt["stops"] > 0:
            continue
        jitter = rng.uniform(0.85, 1.15)
        price = round(opt["base"] * jitter * 2, 2)  # round trip pricing
        dep_hour = rng.choice([6, 9, 12, 15, 18])
        dep_time = datetime(departure_date.year, departure_date.month, departure_date.day, dep_hour, 0)
        arr_time = dep_time + timedelta(hours=opt["duration_h"])

        ret_dep = ret_arr = None
        if return_date:
            ret_hour = rng.choice([8, 11, 14, 17, 20])
            ret_dep = datetime(return_date.year, return_date.month, return_date.day, ret_hour, 0)
            ret_arr = ret_dep + timedelta(hours=opt["duration_h"])

        offers.append(
            FlightOffer(
                provider="mock",
                offer_id=str(uuid.uuid4()),
                origin=origin,
                destination=destination,
                departure_time=dep_time,
                arrival_time=arr_time,
                return_departure_time=ret_dep,
                return_arrival_time=ret_arr,
                total_price=price,
                stops=opt["stops"],
                airline=opt["airline"],
                is_round_trip=return_date is not None,
            )
        )
    return offers


async def fetch_hotels(
    destination: str,
    check_in: date,
    check_out: date,
    adults: int = 1,
    min_star: Optional[float] = None,
    preferred_neighborhoods: Optional[list[str]] = None,
) -> list[HotelOffer]:
    async with httpx.AsyncClient() as client:
        token = await _get_token(client)
        if token:
            result = await _fetch_amadeus_hotels(
                client, token, destination, check_in, check_out, adults, min_star
            )
            if result:
                return result
    return _mock_hotels(destination, check_in, check_out, min_star, preferred_neighborhoods)


async def _fetch_amadeus_hotels(
    client: httpx.AsyncClient,
    token: str,
    destination: str,
    check_in: date,
    check_out: date,
    adults: int,
    min_star: Optional[float],
) -> list[HotelOffer]:
    try:
        search_resp = await client.get(
            AMADEUS_HOTEL_SEARCH_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={"cityCode": destination, "radius": 50, "radiusUnit": "KM", "hotelSource": "ALL"},
            timeout=15,
        )
        if search_resp.status_code != 200:
            return []

        hotel_ids = [h["hotelId"] for h in search_resp.json().get("data", [])[:20]]
        if not hotel_ids:
            return []

        offers_resp = await client.get(
            AMADEUS_HOTEL_OFFERS_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={
                "hotelIds": ",".join(hotel_ids),
                "checkInDate": check_in.isoformat(),
                "checkOutDate": check_out.isoformat(),
                "adults": adults,
                "currency": "USD",
            },
            timeout=15,
        )
        if offers_resp.status_code != 200:
            return []

        nights = (check_out - check_in).days
        offers = []
        for item in offers_resp.json().get("data", []):
            hotel = item.get("hotel", {})
            for offer in item.get("offers", [])[:1]:
                price = float(offer["price"]["total"])
                nightly = round(price / max(nights, 1), 2)
                rating = hotel.get("rating")
                if min_star and rating and float(rating) < min_star:
                    continue
                offers.append(
                    HotelOffer(
                        provider="amadeus",
                        offer_id=offer["id"],
                        name=hotel.get("name", "Hotel"),
                        check_in=check_in,
                        check_out=check_out,
                        nightly_price=nightly,
                        total_price=price,
                        star_rating=float(rating) if rating else None,
                        address=hotel.get("address", {}).get("lines", [""])[0],
                    )
                )
        return offers
    except Exception:
        return []


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

    hotel_templates = {
        "MIA": [
            {"name": "The Setai Miami Beach", "nightly": 420, "stars": 5.0, "neighborhood": "South Beach"},
            {"name": "1 Hotel South Beach", "nightly": 380, "stars": 4.5, "neighborhood": "South Beach"},
            {"name": "Loews Miami Beach Hotel", "nightly": 280, "stars": 4.0, "neighborhood": "South Beach"},
            {"name": "Marriott Biscayne Bay", "nightly": 220, "stars": 4.0, "neighborhood": "Downtown"},
            {"name": "citizenM Miami Worldcenter", "nightly": 160, "stars": 3.5, "neighborhood": "Downtown"},
            {"name": "Hampton Inn Miami Airport", "nightly": 120, "stars": 3.0, "neighborhood": "Airport"},
            {"name": "Fontainebleau Miami Beach", "nightly": 340, "stars": 4.5, "neighborhood": "Mid-Beach"},
            {"name": "The Betsy Hotel", "nightly": 260, "stars": 4.0, "neighborhood": "South Beach"},
        ],
        "NYC": [
            {"name": "The Plaza Hotel", "nightly": 700, "stars": 5.0, "neighborhood": "Midtown"},
            {"name": "Ace Hotel New York", "nightly": 280, "stars": 4.0, "neighborhood": "Midtown"},
            {"name": "Pod 51 Hotel", "nightly": 150, "stars": 3.0, "neighborhood": "Midtown East"},
            {"name": "The Standard High Line", "nightly": 350, "stars": 4.5, "neighborhood": "Meatpacking"},
            {"name": "Arlo Hudson Square", "nightly": 200, "stars": 3.5, "neighborhood": "Hudson Square"},
        ],
    }

    templates = hotel_templates.get(destination, [
        {"name": f"{destination} Grand Hotel", "nightly": 200, "stars": 4.0, "neighborhood": "City Center"},
        {"name": f"{destination} Budget Inn", "nightly": 90, "stars": 2.5, "neighborhood": "Suburbs"},
        {"name": f"Park Hotel {destination}", "nightly": 140, "stars": 3.5, "neighborhood": "City Center"},
        {"name": f"Luxury Suites {destination}", "nightly": 320, "stars": 5.0, "neighborhood": "City Center"},
        {"name": f"Boutique {destination}", "nightly": 170, "stars": 3.5, "neighborhood": "Old Town"},
    ])

    offers = []
    for t in templates:
        if min_star and t["stars"] < min_star:
            continue
        jitter = rng.uniform(0.9, 1.1)
        nightly = round(t["nightly"] * jitter, 2)
        total = round(nightly * nights, 2)
        offers.append(
            HotelOffer(
                provider="mock",
                offer_id=str(uuid.uuid4()),
                name=t["name"],
                check_in=check_in,
                check_out=check_out,
                nightly_price=nightly,
                total_price=total,
                star_rating=t["stars"],
                neighborhood=t.get("neighborhood"),
            )
        )
    return offers
