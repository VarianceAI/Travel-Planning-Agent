# Travel Planning AI Agent

An AI-powered travel planner that takes a free-form natural language query and returns ranked, optimized flight + hotel itineraries by evaluating thousands of date/price combinations. Help travelers save money and gain greater flexibility by eliminating unnecessary expenses associated with traditional trip planning

---

## Architecture

```
User (natural language)
        │
        ▼
┌─────────────────────┐
│  Next.js Frontend   │  natural language input · parsed-trip badge · ranked itinerary cards
└────────┬────────────┘
         │ POST /plan_trip
         ▼
┌─────────────────────┐
│  FastAPI Backend    │
│   (Cloud Run)       │
└────────┬────────────┘
         │
   ┌─────┴──────────────────────┐
   ▼                            ▼
┌──────────────┐     ┌──────────────────────┐
│  LLM Parser  │     │  Planning Engine     │
│  (Claude /   │     │  asyncio.gather()    │
│   rule-based)│     │  date × length grid  │
└──────────────┘     └──────────┬───────────┘
                                │
                   ┌────────────┴────────────┐
                   ▼                         ▼
          ┌──────────────┐         ┌──────────────────┐
          │ Google       │         │ Google Hotels     │
          │ Flights      │         │ (via SerpAPI)     │
          │ (via SerpAPI)│         └──────────────────┘
          └──────────────┘
```

---

## How It Works

### 1. LLM Parsing
Converts free-form user input into a typed constraint schema:

```
Input:  "Miami for 5 days from NYC, prefer South Beach, direct flights, July 2026"

Output: {
  origin: "NYC", destination: "MIA",
  date_range: ["2026-07-01", "2026-07-31"],
  trip_length: [5, 5],
  flight_constraints: { direct_only: true },
  hotel_constraints: { preferred_neighborhoods: ["South Beach"] }
}
```

Uses **Claude** (`claude-sonnet-4-6`) when `ANTHROPIC_API_KEY` is set, falls back to a regex/rule-based parser.

### 2. Parallel Search
The planning engine enumerates all valid `(departure_date, trip_length)` pairs within the date window, then fires all flight and hotel fetches concurrently:

```python
asyncio.gather(*flight_tasks, *hotel_tasks)
# latency = max(T_flights, T_hotels), not their sum
```

Real data comes from **SerpAPI** (Google Flights + Google Hotels). Mock data is used as fallback when no API key is set.

### 3. Constraint-Based Ranking
Joins all flight × hotel combinations, applies hard filters (budget, stops, star rating), and scores each itinerary:

```
score = 0.80 × (1 - cost/10000)   # primary: lower cost
      + 0.15 × (1 - stops × 0.5)  # secondary: fewer stops
      + 0.05 × (stars / 5)        # tertiary: higher hotel rating
```

Returns top-K ranked itineraries.

---

## Project Structure

```
.
├── apps/
│   ├── api/                        # FastAPI backend
│   │   ├── main.py                 # endpoints: /health, /parse_trip, /plan_trip
│   │   ├── models.py               # Pydantic schemas (ParsedTrip, FlightOffer, HotelOffer, Itinerary)
│   │   ├── llm_parser.py           # Claude LLM parser + rule-based fallback
│   │   ├── planning_engine.py      # date enumeration, parallel fetch, ranking
│   │   ├── adapters/
│   │   │   └── serpapi_adapter.py  # Google Flights + Hotels via SerpAPI (mock fallback)
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── web/                        # Next.js 15 frontend
│       └── src/
│           ├── app/                # page, layout, global CSS
│           ├── components/
│           │   ├── ItineraryCard.tsx     # per-itinerary card with flight + hotel breakdown
│           │   └── ParsedTripBadge.tsx   # shows extracted constraints
│           └── types/api.ts        # TypeScript types matching backend schemas
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## API

### `POST /plan_trip`
Full pipeline: parse → search → rank.

**Request**
```json
{ "raw_query": "Miami for 5 days from NYC in July 2026" }
```

**Response**
```json
{
  "parsed_trip": { "origin": "NYC", "destination": "MIA", ... },
  "itineraries": [
    {
      "rank": 1,
      "outbound_flight": { "airline": "Delta", "total_price": 341, "stops": 0, ... },
      "hotel": { "name": "1 Hotel South Beach", "nightly_price": 420, ... },
      "total_cost": 2441,
      "trip_days": 5
    }
  ],
  "combinations_evaluated": 240,
  "search_time_ms": 2850
}
```

### `POST /parse_trip`
Only runs the LLM/rule-based parser. Useful for debugging.

---

## Local Setup

### Prerequisites
- Python 3.12+
- Node.js 18+

### 1. Clone and configure

```bash
git clone https://github.com/VarianceAI/Travel-Planning-Agent.git
cd Travel-Planning-Agent
cp .env.example .env
```

Edit `.env`:

```env
# Required for real flight + hotel data
SERPAPI_KEY=your_serpapi_key

# Optional — enables Claude LLM parsing (falls back to rule-based if unset)
ANTHROPIC_API_KEY=sk-ant-...
```

Get a free SerpAPI key at `serpapi.com` (100 searches/month free).

### 2. Run the backend

```bash
cd apps/api
pip install -r requirements.txt
uvicorn main:app --port 8000 --reload
```

API available at `http://localhost:8000` · Docs at `http://localhost:8000/docs`

### 3. Run the frontend

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Frontend at `http://localhost:3000`

### 4. Or run with Docker

```bash
docker-compose up --build
```

---

## Design Decisions

| Decision | Rationale |
|---|---|
| LLM as planner, not executor | LLM produces a typed constraint object; deterministic engine handles all API calls. Predictable latency, easy to test. |
| Rule-based fallback parser | System works end-to-end without an LLM API key. Forced clear thinking about what the agent actually needs from the LLM. |
| `asyncio.gather` for search | Parallel provider calls reduce latency from `T_flights + T_hotels` to `max(T_flights, T_hotels)`. |
| Pydantic at every boundary | Strong typing between every layer makes debugging fast — data shape errors surface immediately. |
| SerpAPI for data | Single key covers both Google Flights and Google Hotels. No enterprise partnership required. |

---

## Performance

| Stage | Target |
|---|---|
| LLM parsing | < 1s |
| Flight + hotel fetch (parallel) | 1–2s |
| Planning engine (ranking) | < 500ms |
| **End-to-end** | **~3s** |

---

## What's Not Yet Implemented

- GCP Cloud Run deployment (Docker config ready, not deployed)
- Redis caching for repeated route queries
- Real hotel booking links
- Multi-city routing
- User accounts / search history
- Streaming response (frontend shows results progressively)
