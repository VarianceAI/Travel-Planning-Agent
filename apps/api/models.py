from __future__ import annotations
from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class FlightConstraints(BaseModel):
    direct_only: bool = False
    max_stops: Optional[int] = None
    cabin_class: Literal["economy", "premium_economy", "business", "first"] = "economy"
    preferred_airlines: list[str] = []
    excluded_airlines: list[str] = []
    max_duration_hours: Optional[float] = None   # max total flight time


class HotelConstraints(BaseModel):
    min_star: Optional[float] = None
    max_star: Optional[float] = None
    level: Optional[Literal["budget", "mid", "upscale", "luxury"]] = None
    preferred_neighborhoods: list[str] = []
    required_amenities: list[str] = []          # e.g. ["pool", "gym", "breakfast", "parking"]
    preferred_brands: list[str] = []            # e.g. ["Marriott", "Hilton"]
    max_nightly_rate: Optional[float] = None


class TripRequest(BaseModel):
    raw_query: str


class ParsedTrip(BaseModel):
    # Route
    origin: str
    destination: str

    # Dates
    date_range_start: date
    date_range_end: date
    trip_length_min: int
    trip_length_max: int

    # Trip type
    is_round_trip: bool = True
    travelers: int = 1                          # number of adult travelers

    # Budget
    budget: Optional[float] = None             # total trip budget (USD)
    budget_per_person: Optional[float] = None  # per-person budget if specified

    # Constraints
    flight_constraints: FlightConstraints = Field(default_factory=FlightConstraints)
    hotel_constraints: HotelConstraints = Field(default_factory=HotelConstraints)

    # Freeform catch-all for anything else
    special_requirements: list[str] = []       # e.g. ["wheelchair accessible", "pet friendly"]


class FlightOffer(BaseModel):
    provider: str
    offer_id: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    return_departure_time: Optional[datetime] = None
    return_arrival_time: Optional[datetime] = None
    total_price: float
    currency: str = "USD"
    stops: int = 0
    airline: Optional[str] = None
    cabin_class: str = "economy"
    is_round_trip: bool = False


class HotelOffer(BaseModel):
    provider: str
    offer_id: str
    name: str
    check_in: date
    check_out: date
    nightly_price: float
    total_price: float
    currency: str = "USD"
    star_rating: Optional[float] = None
    neighborhood: Optional[str] = None
    address: Optional[str] = None


class Itinerary(BaseModel):
    rank: int
    outbound_flight: FlightOffer
    return_flight: Optional[FlightOffer] = None
    hotel: HotelOffer
    total_cost: float
    currency: str = "USD"
    trip_days: int
    score: float


class PlanTripResponse(BaseModel):
    parsed_trip: ParsedTrip
    itineraries: list[Itinerary]
    combinations_evaluated: int
    search_time_ms: float
