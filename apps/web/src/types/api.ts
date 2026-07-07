export interface FlightConstraints {
  direct_only: boolean;
  max_stops: number | null;
  cabin_class: "economy" | "premium_economy" | "business" | "first";
  preferred_airlines: string[];
  excluded_airlines: string[];
  max_duration_hours: number | null;
}

export interface HotelConstraints {
  min_star: number | null;
  max_star: number | null;
  level: "budget" | "mid" | "upscale" | "luxury" | null;
  preferred_neighborhoods: string[];
  required_amenities: string[];
  preferred_brands: string[];
  max_nightly_rate: number | null;
}

export interface ParsedTrip {
  origin: string;
  destination: string;
  date_range_start: string;
  date_range_end: string;
  trip_length_min: number;
  trip_length_max: number;
  is_round_trip: boolean;
  travelers: number;
  budget: number | null;
  budget_per_person: number | null;
  flight_constraints: FlightConstraints;
  hotel_constraints: HotelConstraints;
  special_requirements: string[];
}

export interface FlightOffer {
  provider: string;
  offer_id: string;
  origin: string;
  destination: string;
  departure_time: string;
  arrival_time: string;
  return_departure_time: string | null;
  return_arrival_time: string | null;
  total_price: number;
  currency: string;
  stops: number;
  airline: string | null;
  cabin_class: string;
  is_round_trip: boolean;
}

export interface HotelOffer {
  provider: string;
  offer_id: string;
  name: string;
  check_in: string;
  check_out: string;
  nightly_price: number;
  total_price: number;
  currency: string;
  star_rating: number | null;
  neighborhood: string | null;
  address: string | null;
}

export interface Itinerary {
  rank: number;
  outbound_flight: FlightOffer;
  return_flight: FlightOffer | null;
  hotel: HotelOffer;
  total_cost: number;
  currency: string;
  trip_days: number;
  score: number;
}

export interface PlanTripResponse {
  parsed_trip: ParsedTrip;
  itineraries: Itinerary[];
  combinations_evaluated: number;
  search_time_ms: number;
}
