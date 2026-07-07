"use client";
import type { ParsedTrip } from "@/types/api";

const CABIN_LABELS: Record<string, string> = {
  economy: "Economy",
  premium_economy: "Premium Economy",
  business: "Business",
  first: "First Class",
};

const LEVEL_LABELS: Record<string, string> = {
  budget: "Budget",
  mid: "Mid-range",
  upscale: "Upscale",
  luxury: "Luxury",
};

export default function ParsedTripBadge({ parsed }: { parsed: ParsedTrip }) {
  const fc = parsed.flight_constraints;
  const hc = parsed.hotel_constraints;

  return (
    <div style={{
      background: "var(--surface2)",
      border: "1px solid var(--border)",
      borderRadius: 12,
      padding: "14px 20px",
      marginBottom: 24,
      fontSize: 13,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 10, color: "var(--text-muted)", letterSpacing: "0.08em", fontSize: 11 }}>
        PARSED TRIP CONSTRAINTS
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 28px" }}>

        {/* Core */}
        <Chip label="Route" value={`${parsed.origin} → ${parsed.destination}`} />
        <Chip label="Type" value={parsed.is_round_trip ? "Round trip" : "One way"} />
        <Chip label="Dates" value={`${parsed.date_range_start} – ${parsed.date_range_end}`} />
        <Chip label="Stay" value={
          parsed.trip_length_min === parsed.trip_length_max
            ? `${parsed.trip_length_min} days`
            : `${parsed.trip_length_min}–${parsed.trip_length_max} days`
        } />
        {parsed.travelers > 1 && <Chip label="Travelers" value={`${parsed.travelers} people`} />}

        {/* Budget */}
        {parsed.budget && <Chip label="Total budget" value={`$${parsed.budget.toLocaleString()}`} />}
        {parsed.budget_per_person && <Chip label="Per person" value={`$${parsed.budget_per_person.toLocaleString()}`} />}

        {/* Flight */}
        {fc.direct_only && <Chip label="Flights" value="Nonstop only" accent />}
        {fc.cabin_class !== "economy" && <Chip label="Cabin" value={CABIN_LABELS[fc.cabin_class]} accent />}
        {fc.max_stops != null && !fc.direct_only && <Chip label="Max stops" value={String(fc.max_stops)} />}
        {fc.max_duration_hours && <Chip label="Max flight time" value={`${fc.max_duration_hours}h`} />}
        {fc.preferred_airlines.length > 0 && <Chip label="Airlines" value={fc.preferred_airlines.join(", ")} />}
        {fc.excluded_airlines.length > 0 && <Chip label="Avoid" value={fc.excluded_airlines.join(", ")} />}

        {/* Hotel */}
        {hc.level && <Chip label="Hotel level" value={LEVEL_LABELS[hc.level]} />}
        {hc.min_star && <Chip label="Min stars" value={`${hc.min_star}★`} />}
        {hc.max_nightly_rate && <Chip label="Max/night" value={`$${hc.max_nightly_rate}`} />}
        {hc.preferred_neighborhoods.length > 0 && <Chip label="Area" value={hc.preferred_neighborhoods.join(", ")} />}
        {hc.preferred_brands.length > 0 && <Chip label="Brands" value={hc.preferred_brands.join(", ")} />}
        {hc.required_amenities.length > 0 && <Chip label="Amenities" value={hc.required_amenities.join(", ")} />}

        {/* Special */}
        {parsed.special_requirements.length > 0 && (
          <Chip label="Special" value={parsed.special_requirements.join(", ")} />
        )}
      </div>
    </div>
  );
}

function Chip({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <span style={{ color: "var(--text-muted)", marginRight: 4 }}>{label}:</span>
      <span style={{ color: accent ? "var(--accent-light)" : "var(--text)", fontWeight: 500 }}>{value}</span>
    </div>
  );
}
