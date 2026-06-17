import time
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from models import TripRequest, ParsedTrip, PlanTripResponse
from llm_parser import parse_trip
from planning_engine import generate_itineraries


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Travel Planning AI Agent",
    description="Natural language travel planning with flight + hotel optimization",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/parse_trip", response_model=ParsedTrip)
async def api_parse_trip(req: TripRequest):
    try:
        return parse_trip(req.raw_query)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse trip: {e}")


@app.post("/plan_trip", response_model=PlanTripResponse)
async def api_plan_trip(req: TripRequest):
    start = time.time()

    try:
        parsed = parse_trip(req.raw_query)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse trip request: {e}")

    try:
        itineraries, evaluated = await generate_itineraries(parsed, top_k=10)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planning engine error: {e}")

    elapsed_ms = round((time.time() - start) * 1000, 1)

    return PlanTripResponse(
        parsed_trip=parsed,
        itineraries=itineraries,
        combinations_evaluated=evaluated,
        search_time_ms=elapsed_ms,
    )
