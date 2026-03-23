"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useSlidingSession } from "../lib/session";

const API_BASE = "/api/proxy";

type UserProfile = {
  id: number;
  email: string;
  display_name: string;
  timezone: string;
};

const FALLBACK_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Phoenix",
  "Pacific/Honolulu",
  "Europe/London",
  "Europe/Paris",
  "Asia/Tokyo",
  "Asia/Ho_Chi_Minh",
  "Australia/Sydney",
];

function getSupportedTimezones(): string[] {
  const supportedValuesOf = (
    globalThis.Intl as unknown as { supportedValuesOf?: (key: "timeZone") => string[] }
  ).supportedValuesOf;
  if (supportedValuesOf) {
    return supportedValuesOf("timeZone");
  }
  return FALLBACK_TIMEZONES;
}

async function parseError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail || body.message || "Request failed";
  } catch {
    return `Request failed (${res.status})`;
  }
}

export default function AccountPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [timezoneOptions, setTimezoneOptions] = useState<string[]>([]);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const handleSessionExpired = useCallback(() => {
    setProfile(null);
    setError("Session expired due to inactivity. Please log in again.");
    setLoading(false);
  }, []);
  const { token, ready: sessionReady, clearSessionToken } = useSlidingSession({
    apiBase: API_BASE,
    onExpired: handleSessionExpired,
  });

  useEffect(() => {
    setTimezoneOptions(getSupportedTimezones());
  }, []);

  useEffect(() => {
    if (!sessionReady) return;
    if (!token) {
      setError("Log in first to view account details.");
      setLoading(false);
    }
  }, [sessionReady, token]);

  useEffect(() => {
    if (!token) return;

    async function loadProfile() {
      setLoading(true);
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        clearSessionToken();
        handleSessionExpired();
        setLoading(false);
        return;
      }
      const data = (await res.json()) as UserProfile;
      setProfile(data);
      setDisplayName(data.display_name);
      setEmail(data.email);
      setTimezone(data.timezone);
      setLoading(false);
    }

    void loadProfile();
  }, [clearSessionToken, handleSessionExpired, token]);

  useEffect(() => {
    if (!message) return;
    const timeoutId = window.setTimeout(() => setMessage(null), 4200);
    return () => window.clearTimeout(timeoutId);
  }, [message]);

  async function saveProfile() {
    if (!token) return;
    setMessage(null);
    setError(null);

    const res = await fetch(`${API_BASE}/auth/me`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        display_name: displayName.trim(),
        email: email.trim(),
        timezone,
      }),
    });

    if (!res.ok) {
      setError(await parseError(res));
      return;
    }

    const updated = (await res.json()) as UserProfile;
    setProfile(updated);
    setDisplayName(updated.display_name);
    setEmail(updated.email);
    setTimezone(updated.timezone);
    setMessage("Account details updated.");
  }

  async function savePassword() {
    if (!token) return;
    setMessage(null);
    setError(null);

    const res = await fetch(`${API_BASE}/auth/me/password`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });

    if (!res.ok) {
      setError(await parseError(res));
      return;
    }

    setCurrentPassword("");
    setNewPassword("");
    setMessage("Password updated.");
  }

  function logout() {
    clearSessionToken();
    window.location.href = "/";
  }

  return (
    <main className="app-wrap">
      <section className="shell">
        <div className="card detail-shell">
          <div className="row-gap">
            <Link href="/">Back to Dashboard</Link>
            <Link href="/recipes/book">Favorite Recipes</Link>
          </div>

          <div>
            <p className="eyebrow">Account Center</p>
            <h1 className="title">Your account</h1>
            <p className="subtitle">
              Update the way SmartPantry greets you, keep your email current, and manage your password in one place.
            </p>
          </div>

          {loading && <p className="muted-text">Loading your account...</p>}
          {error && (
            <div className="app-alert app-alert-error">
              <p>{error}</p>
            </div>
          )}
          {message && (
            <div className="app-alert app-alert-success">
              <p>{message}</p>
            </div>
          )}

          {profile && (
            <div className="detail-grid">
              <div className="card">
                <h2>Profile details</h2>
                <div className="list-col">
                  <label className="tiny-text" htmlFor="account-display-name">
                    Display name
                  </label>
                  <input
                    id="account-display-name"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="How should I call you?"
                  />

                  <label className="tiny-text" htmlFor="account-email">
                    Email
                  </label>
                  <input
                    id="account-email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    type="email"
                    placeholder="Email"
                  />

                  <label className="tiny-text" htmlFor="account-timezone">
                    Timezone
                  </label>
                  <select
                    id="account-timezone"
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                  >
                    {timezoneOptions.map((tz) => (
                      <option key={tz} value={tz}>
                        {tz}
                      </option>
                    ))}
                  </select>

                  <div className="row-gap">
                    <button onClick={() => void saveProfile()}>Save details</button>
                  </div>
                </div>
              </div>

              <div className="card">
                <h2>Security</h2>
                <div className="list-col">
                  <label className="tiny-text" htmlFor="account-current-password">
                    Current password
                  </label>
                  <input
                    id="account-current-password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    type="password"
                    placeholder="Current password"
                  />

                  <label className="tiny-text" htmlFor="account-new-password">
                    New password
                  </label>
                  <input
                    id="account-new-password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    type="password"
                    placeholder="New password"
                  />

                  <div className="row-gap">
                    <button onClick={() => void savePassword()}>Update password</button>
                    <button onClick={logout}>Log out</button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
