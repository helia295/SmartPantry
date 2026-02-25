"use client";

import { useEffect, useState } from "react";

const API_BASE =
  typeof window !== "undefined"
    ? "/api/proxy"
    : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Health = { status: string; service: string } | null;

export default function Home() {
  const [health, setHealth] = useState<Health>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
        gap: "1.5rem",
      }}
    >
      <h1 style={{ fontSize: "2rem", fontWeight: 700 }}>SmartPantry</h1>
      <p style={{ color: "var(--muted)", maxWidth: "32ch", textAlign: "center" }}>
        AI-powered kitchen inventory. Upload pantry photos, get proposals, and
        recipe ideas—all with you in the loop.
      </p>

      <section
        style={{
          padding: "1rem 1.5rem",
          background: "var(--surface)",
          borderRadius: "8px",
          minWidth: "280px",
        }}
      >
        <h2 style={{ fontSize: "0.875rem", color: "var(--muted)", marginBottom: "0.5rem" }}>
          API status
        </h2>
        {error && (
          <p style={{ color: "var(--error)" }}>Backend unreachable: {error}</p>
        )}
        {health && (
          <p style={{ color: "var(--success)" }}>
            {health.service} — {health.status}
          </p>
        )}
        {!health && !error && (
          <p style={{ color: "var(--muted)" }}>Checking…</p>
        )}
      </section>

      <p style={{ fontSize: "0.875rem", color: "var(--muted)" }}>
        Next: auth, inventory, and photo upload.
      </p>
    </main>
  );
}
