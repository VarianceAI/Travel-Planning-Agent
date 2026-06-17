"use client";
import type { Itinerary } from "@/types/api";

function fmt(dt: string) {
  return new Date(dt).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function fmtDate(d: string) {
  return new Date(d + "T00:00:00").toLocaleDateString("en-US", {
    month: "short", day: "numeric",
  });
}

function Stars({ rating }: { rating: number | null }) {
  if (!rating) return null;
  return (
    <span style={{ color: "var(--amber)", fontSize: 13 }}>
      {"★".repeat(Math.floor(rating))}{"☆".repeat(5 - Math.floor(rating))}
      <span style={{ color: "var(--text-muted)", marginLeft: 4 }}>{rating}</span>
    </span>
  );
}

export default function ItineraryCard({ itin, best }: { itin: Itinerary; best: boolean }) {
  const f = itin.outbound_flight;
  const h = itin.hotel;

  return (
    <div style={{
      background: "var(--surface)",
      border: `1px solid ${best ? "var(--accent)" : "var(--border)"}`,
      borderRadius: 16,
      padding: "20px 24px",
      position: "relative",
      boxShadow: best ? "0 0 0 2px var(--accent)22" : undefined,
    }}>
      {best && (
        <div style={{
          position: "absolute", top: -12, left: 20,
          background: "var(--accent)", color: "#fff",
          fontSize: 11, fontWeight: 700, padding: "2px 10px",
          borderRadius: 99, letterSpacing: "0.05em",
        }}>
          BEST VALUE
        </div>
      )}

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 2 }}>Rank #{itin.rank}</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: "var(--accent-light)" }}>
            ${itin.total_cost.toFixed(0)}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{itin.trip_days}-day trip · total</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Flight ${f.total_price.toFixed(0)}</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Hotel ${h.total_price.toFixed(0)}</div>
        </div>
      </div>

      <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "12px 0" }} />

      {/* Flight */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.08em", marginBottom: 6 }}>
          FLIGHT ({f.is_round_trip ? "round-trip" : "one-way"})
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontWeight: 600, fontSize: 15 }}>
            {f.origin} → {f.destination}
          </span>
          {f.airline && (
            <span style={{
              background: "var(--surface2)", borderRadius: 6,
              padding: "2px 8px", fontSize: 12,
            }}>{f.airline}</span>
          )}
          <span style={{
            background: f.stops === 0 ? "#1a3a2a" : "var(--surface2)",
            color: f.stops === 0 ? "var(--green)" : "var(--text-muted)",
            borderRadius: 6, padding: "2px 8px", fontSize: 12,
          }}>
            {f.stops === 0 ? "Nonstop" : `${f.stops} stop${f.stops > 1 ? "s" : ""}`}
          </span>
        </div>
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
          Out: {fmt(f.departure_time)} → {fmt(f.arrival_time)}
          {f.return_departure_time && (
            <> &nbsp;|&nbsp; Ret: {fmt(f.return_departure_time)} → {fmt(f.return_arrival_time!)}</>
          )}
        </div>
      </div>

      {/* Hotel */}
      <div>
        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.08em", marginBottom: 6 }}>
          HOTEL
        </div>
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 2 }}>{h.name}</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <Stars rating={h.star_rating} />
          {h.neighborhood && (
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{h.neighborhood}</span>
          )}
        </div>
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
          {fmtDate(h.check_in)} – {fmtDate(h.check_out)} · ${h.nightly_price.toFixed(0)}/night
        </div>
      </div>

      {/* Provider badge */}
      <div style={{ marginTop: 12, fontSize: 11, color: "var(--border)" }}>
        via {f.provider} / {h.provider}
      </div>
    </div>
  );
}
