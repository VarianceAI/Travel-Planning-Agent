"use client";
import { useState } from "react";
import type { PlanTripResponse } from "@/types/api";
import ItineraryCard from "@/components/ItineraryCard";
import ParsedTripBadge from "@/components/ParsedTripBadge";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const EXAMPLES = [
  "Help me find the best price for staying in Miami for 5 days, prefer South Beach, from New York City, during May 2026",
  "Flight from NYC to LA, 7 days in late June 2026, budget $2000, direct flights only",
  "Tokyo trip from San Francisco, early July 2026, 5-7 days, 4-star hotel or better",
];

export default function Home() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PlanTripResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(q?: string) {
    const finalQuery = q ?? query;
    if (!finalQuery.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    if (q) setQuery(q);

    try {
      const resp = await fetch(`${API_URL}/plan_trip`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_query: finalQuery }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail ?? "Request failed");
      }
      const data: PlanTripResponse = await resp.json();
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ minHeight: "100vh", padding: "40px 20px", maxWidth: 860, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 40 }}>
        <h1 style={{ fontSize: 36, fontWeight: 800, marginBottom: 8, letterSpacing: "-0.02em" }}>
          <span style={{ color: "var(--accent-light)" }}>Travel Planning</span> AI
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: 16 }}>
          Describe your trip in plain English — we find the best flight + hotel combinations
        </p>
      </div>

      {/* Search box */}
      <div style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 16,
        padding: 20,
        marginBottom: 24,
      }}>
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="e.g. Help me find the best price for staying in Miami for 5 days, prefer South Beach, from New York City, during May 2026"
          rows={3}
          style={{
            width: "100%",
            background: "var(--surface2)",
            border: "1px solid var(--border)",
            borderRadius: 10,
            padding: "12px 16px",
            color: "var(--text)",
            fontSize: 15,
            resize: "vertical",
            outline: "none",
            marginBottom: 12,
            fontFamily: "inherit",
          }}
          onKeyDown={e => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSubmit();
          }}
        />
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Cmd+Enter to search</span>
          <button
            onClick={() => handleSubmit()}
            disabled={loading || !query.trim()}
            style={{
              background: loading ? "var(--border)" : "var(--accent)",
              color: "#fff",
              border: "none",
              borderRadius: 10,
              padding: "10px 24px",
              fontSize: 15,
              fontWeight: 600,
              transition: "background 0.2s",
            }}
          >
            {loading ? "Searching..." : "Find Itineraries"}
          </button>
        </div>
      </div>

      {/* Example queries */}
      {!result && !loading && (
        <div style={{ marginBottom: 32 }}>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 10, letterSpacing: "0.06em" }}>
            TRY AN EXAMPLE
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {EXAMPLES.map((ex, i) => (
              <button
                key={i}
                onClick={() => handleSubmit(ex)}
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 10,
                  padding: "10px 16px",
                  color: "var(--text-muted)",
                  fontSize: 13,
                  textAlign: "left",
                  transition: "border-color 0.15s, color 0.15s",
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--accent)";
                  (e.currentTarget as HTMLButtonElement).style.color = "var(--text)";
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border)";
                  (e.currentTarget as HTMLButtonElement).style.color = "var(--text-muted)";
                }}
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-muted)" }}>
          <div style={{
            width: 40, height: 40, border: "3px solid var(--border)",
            borderTopColor: "var(--accent)", borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
            margin: "0 auto 16px",
          }} />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          <div>Parsing your trip and searching offers...</div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          background: "#2a1a1a", border: "1px solid var(--red)",
          borderRadius: 12, padding: 16, color: "var(--red)", marginBottom: 24,
        }}>
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          <ParsedTripBadge parsed={result.parsed_trip} />

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700 }}>
              {result.itineraries.length} itineraries found
            </h2>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
              {result.combinations_evaluated} combinations · {result.search_time_ms.toFixed(0)}ms
            </span>
          </div>

          {result.itineraries.length === 0 ? (
            <div style={{ color: "var(--text-muted)", textAlign: "center", padding: 40 }}>
              No itineraries found. Try relaxing your budget or date range.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {result.itineraries.map((itin, i) => (
                <ItineraryCard key={itin.outbound_flight.offer_id + itin.hotel.offer_id} itin={itin} best={i === 0} />
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}
