from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class FlightConstraints(BaseModel):
    direct_only: bool = False
    max_stops: Optional[int] = None
    preferred_airlines: list[str] = []


class HotelConstraints(BaseModel):
    min_star: Optional[float] = None
    max_star: Optional[float] = None
    preferred_neighborhoods: list[str] = []


class TripRequest(BaseModel):
    raw_query: str


class ParsedTrip(BaseModel):
    origin: str
    destination: str
    date_range_start: date
    date_range_end: date
    trip_length_min: int
    trip_length_max: int
    budget: Optional[float] = None
    flight_constraints: FlightConstraints = Field(default_factory=FlightConstraints)
    hotel_constraints: HotelConstraints = Field(default_factory=HotelConstraints)


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
