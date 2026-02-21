🧠 Travel Planning AI Agent
System Design (MVP)
1. Problem Statement

Design an AI-powered travel planning system that:

Accepts free-form natural language trip requests

Extracts structured constraints using LLMs

Aggregates real-time flight and hotel offers from multiple providers

Generates and ranks optimal itineraries

Returns results within ~3 seconds

The system must:

Handle ambiguous language

Support flexible date ranges

Evaluate thousands of flight + hotel combinations

Remain provider-agnostic

Be cloud-deployable and horizontally scalable

2. High-Level Architecture
                    ┌──────────────────────┐
                    │  Next.js Web Client  │
                    └───────────┬──────────┘
                                │ HTTPS
                                ▼
                    ┌──────────────────────┐
                    │  FastAPI Backend     │
                    │  (Cloud Run)         │
                    └───────────┬──────────┘
                                │
      ┌─────────────────────────┼─────────────────────────┐
      ▼                         ▼                         ▼
┌──────────────┐        ┌────────────────┐        ┌────────────────┐
│ LLM Parsing  │        │ Meta-Search     │        │ Planning Engine│
│ (GPT-4)      │        │ Aggregator      │        │ & Ranking      │
└──────────────┘        └────────────────┘        └────────────────┘
                                │
                                ▼
                    ┌──────────────────────┐
                    │ Unified Offer Schema │
                    └──────────────────────┘

3. Component-Level Design
3.1 LLM Parsing Layer
Purpose

Convert natural language into structured constraints.

Example Input
"Go to Tokyo in late May for 5–7 days, under $2000, direct flights only, 4-star hotel."

Structured Output
{
  "origin": "NYC",
  "destination": "TYO",
  "date_range": ["2026-05-20", "2026-05-31"],
  "trip_length_range": [5, 7],
  "budget": 2000,
  "flight_constraints": {
    "direct_only": true
  },
  "hotel_constraints": {
    "min_star": 4
  }
}

Implementation

GPT-4

LangChain structured output parser

JSON schema validation via Pydantic

Design Decisions

Why LLM?

Eliminates rigid form-based UI

Handles ambiguous phrasing

Extensible constraint parsing

Natural UX for users

3.2 Meta-Search Aggregator
Responsibilities

Call multiple provider APIs in parallel

Normalize heterogeneous JSON responses

Convert into unified internal schema

Providers (MVP)

Amadeus (Flights)

Skyscanner-style APIs

Booking-style Hotel APIs

Unified Internal Schema
class FlightOffer:
    provider: str
    departure_time: datetime
    arrival_time: datetime
    total_price: float
    stops: int

class HotelOffer:
    provider: str
    check_in: date
    check_out: date
    nightly_price: float
    star_rating: float
    total_price: float

Key Design Pattern

Adapter Pattern

Each provider gets its own adapter:

AmadeusAdapter → FlightOffer
SkyscannerAdapter → FlightOffer
BookingAdapter → HotelOffer


This keeps the planning engine provider-agnostic.

3.3 Planning & Optimization Engine

This is the core algorithmic component.

Inputs

Date range window

Trip length range

All candidate flight offers

All candidate hotel offers

Budget constraints

Algorithm Strategy

Instead of searching one fixed departure date:

Enumerate all valid departure dates within range

For each departure date:

For each valid trip length:

Compute return date

Match:

Outbound flights

Return flights

Hotels covering exact stay window

Compute total trip cost

TotalCost = outbound + return + hotel_total


Apply constraints:

budget

direct_only

minimum star rating

Rank candidates by:

total cost (primary)

total travel time (secondary)

Complexity

Let:

F = number of flight offers

H = number of hotel offers

D = number of date windows

Worst-case naive:

O(D × F × H)


MVP optimization techniques:

Pre-filter flights by date before join

Pre-group hotels by check-in date

Early pruning by budget

Stop evaluation once top-K stable

Effective runtime: ~1000–5000 combinations per query

3.4 Backend Design (FastAPI)
Why FastAPI?

Async support

High performance

Auto OpenAPI docs

Clean schema enforcement

Core Endpoints
POST /parse_trip
POST /search_offers
POST /generate_itinerary
POST /plan_trip (combined pipeline)

Concurrency Model

Parallel external calls:

asyncio.gather(
    fetch_flights(),
    fetch_hotels()
)


This reduces total latency from:

T_flights + T_hotels


to:

max(T_flights, T_hotels)

3.5 Frontend (Next.js + TypeScript)
MVP Features

Single natural-language input box

Loading state

Ranked itinerary cards

Cost breakdown

Error handling

Architecture
User Input
   ↓
POST /plan_trip
   ↓
Render itinerary cards

4. Deployment Architecture
4.1 Containerization

Multi-stage Docker build

Slim production image

Environment-based config

4.2 GCP Cloud Run

Advantages:

Auto-scaling

Scale-to-zero

Fully managed HTTPS

No server management

Scaling Model

Stateless backend

Horizontal scaling via container replication

Each request isolated

5. Performance Design
Stage	Target Latency
LLM parsing	< 1s
Flight API calls	1–2s
Hotel API calls	1–2s
Planning engine	< 500ms
End-to-end	~3s
6. Fault Tolerance Strategy

Provider timeout fallback

Partial result tolerance

Graceful degradation if one provider fails

Input schema validation

7. Security Considerations

API key isolation via environment variables

No provider keys exposed to frontend

Input sanitization before LLM call

Rate limiting (future)

8. Scalability Roadmap

Future improvements:

Redis caching for common routes

Precomputed cheapest-date indexing

Vector memory for user preference modeling

Multi-city routing

Reinforcement learning ranking layer

Distributed planning computation (if search space expands)

9. Design Trade-offs
Decision	Trade-off
LLM parsing	Cost vs flexibility
Real-time aggregation	Freshness vs latency
Constraint brute-force search	Accuracy vs computational cost
Cloud Run	Simplicity vs deep infra control
10. Why This Design Is Interesting

This system combines:

LLM semantic parsing

Cross-provider meta-search

Constraint-satisfaction search

Optimization-based ranking

Cloud-native deployment

It sits at the intersection of:

AI agents

Travel meta-search

Operations research

Distributed backend systems
