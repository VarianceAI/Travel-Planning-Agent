"""Constraint-based trip planning and ranking engine."""
from datetime import date, timedelta
from typing import Optional
import asyncio

from models import ParsedTrip, FlightOffer, HotelOffer, Itinerary
from adapters.amadeus_adapter import fetch_flights, fetch_hotels


async def generate_itineraries(parsed: ParsedTrip, top_k: int = 10) -> tuple[list[Itinerary], int]:
    """
    Enumerate valid departure dates × trip lengths, fetch offers in parallel,
    and rank combinations by total cost.
    Returns (ranked itineraries, combinations_evaluated).
    """
    # Build all (departure_date, trip_length) pairs
    date_trip_pairs: list[tuple[date, int]] = []
    current = parsed.date_range_start
    while current <= parsed.date_range_end:
        for length in range(parsed.trip_length_min, parsed.trip_length_max + 1):
            return_date = current + timedelta(days=length)
            if return_date <= parsed.date_range_end:
                date_trip_pairs.append((current, length))
        current += timedelta(days=1)

    if not date_trip_pairs:
        return [], 0

    # Fetch all flights and hotels concurrently per date window
    # Group by unique departure/return pairs to avoid redundant API calls
    unique_departures: set[tuple[date, date]] = {
        (dep, dep + timedelta(days=length)) for dep, length in date_trip_pairs
    }

    flight_tasks = [
        fetch_flights(
            origin=parsed.origin,
            destination=parsed.destination,
            departure_date=dep,
            return_date=ret,
            direct_only=parsed.flight_constraints.direct_only,
        )
        for dep, ret in unique_departures
    ]

    # Unique check-in/check-out combos
    unique_hotel_windows: set[tuple[date, date]] = {
        (dep, dep + timedelta(days=length)) for dep, length in date_trip_pairs
    }

    hotel_tasks = [
        fetch_hotels(
            destination=parsed.destination,
            check_in=ci,
            check_out=co,
            min_star=parsed.hotel_constraints.min_star,
            preferred_neighborhoods=parsed.hotel_constraints.preferred_neighborhoods or None,
        )
        for ci, co in unique_hotel_windows
    ]

    all_results = await asyncio.gather(*flight_tasks, *hotel_tasks)
    n_flight_tasks = len(flight_tasks)
    flight_results = all_results[:n_flight_tasks]
    hotel_results = all_results[n_flight_tasks:]

    # Index results by window
    dep_ret_list = list(unique_departures)
    hotel_window_list = list(unique_hotel_windows)

    flight_index: dict[tuple[date, date], list[FlightOffer]] = {
        dep_ret_list[i]: flight_results[i] for i in range(len(dep_ret_list))
    }
    hotel_index: dict[tuple[date, date], list[HotelOffer]] = {
        hotel_window_list[i]: hotel_results[i] for i in range(len(hotel_window_list))
    }

    # Evaluate combinations
    candidates: list[Itinerary] = []
    evaluated = 0

    for dep_date, length in date_trip_pairs:
        ret_date = dep_date + timedelta(days=length)
        flights = flight_index.get((dep_date, ret_date), [])
        hotels = hotel_index.get((dep_date, ret_date), [])

        for flight in flights:
            for hotel in hotels:
                evaluated += 1
                total = round(flight.total_price + hotel.total_price, 2)

                # Apply budget constraint
                if parsed.budget and total > parsed.budget:
                    continue

                # Apply stop constraint
                if parsed.flight_constraints.max_stops is not None:
                    if flight.stops > parsed.flight_constraints.max_stops:
                        continue

                score = _score(flight, hotel, total, length)
                candidates.append(
                    Itinerary(
                        rank=0,
                        outbound_flight=flight,
                        return_flight=None,  # round-trip embedded in flight offer
                        hotel=hotel,
                        total_cost=total,
                        trip_days=length,
                        score=score,
                    )
                )

        # Early termination: once we have plenty of candidates stop searching
        if len(candidates) >= top_k * 20:
            break

    # Sort by score descending (lower cost + fewer stops = higher score)
    candidates.sort(key=lambda x: x.score, reverse=True)

    # Assign ranks and return top K
    result = []
    for rank, itin in enumerate(candidates[:top_k], start=1):
        result.append(itin.model_copy(update={"rank": rank}))

    return result, evaluated


def _score(flight: FlightOffer, hotel: HotelOffer, total_cost: float, trip_days: int) -> float:
    """
    Higher score = better itinerary.
    Primary: lower total cost (80%). Secondary: fewer stops (15%). Tertiary: higher stars (5%).
    All components normalized to [0, 1] range before weighting.
    """
    # Cost component: invert so cheaper = higher score; normalize assuming $200–$10000 range
    cost_norm = 1.0 - min(total_cost / 10_000.0, 1.0)

    # Stop component: 0 stops → 1.0, 1 stop → 0.5, 2+ stops → 0.0
    stop_norm = max(0.0, 1.0 - flight.stops * 0.5)

    # Star component: 1–5 stars mapped to 0–1
    star_norm = ((hotel.star_rating or 3.0) - 1.0) / 4.0

    return 0.80 * cost_norm + 0.15 * stop_norm + 0.05 * star_norm
