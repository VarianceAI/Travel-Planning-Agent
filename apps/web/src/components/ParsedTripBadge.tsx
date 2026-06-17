"use client";
import type { ParsedTrip } from "@/types/api";

export default function ParsedTripBadge({ parsed }: { parsed: ParsedTrip }) {
  return (
    <div style={{
      background: "var(--surface2)",
      border: "1px solid var(--border)",
      borderRadius: 12,
      padding: "14px 20px",
      marginBottom: 24,
      fontSize: 13,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 8, color: "var(--text-muted)", letterSpacing: "0.08em", fontSize: 11 }}>
        PARSED TRIP CONSTRAINTS
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 24px" }}>
        <Chip label="Route" value={`${parsed.origin} → ${parsed.destination}`} />
        <Chip label="Dates" value={`${parsed.date_range_start} – ${parsed.date_range_end}`} />
        <Chip label="Stay" value={
          parsed.trip_length_min === parsed.trip_length_max
            ? `${parsed.trip_length_min} days`
            : `${parsed.trip_length_min}–${parsed.trip_length_max} days`
        } />
        {parsed.budget && <Chip label="Budget" value={`$${parsed.budget}`} />}
        {parsed.flight_constraints.direct_only && <Chip label="Flights" value="Nonstop only" accent />}
        {parsed.hotel_constraints.min_star && <Chip label="Hotel" value={`${parsed.hotel_constraints.min_star}+ stars`} />}
        {parsed.hotel_constraints.preferred_neighborhoods.length > 0 && (
          <Chip label="Area" value={parsed.hotel_constraints.preferred_neighborhoods.join(", ")} />
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
