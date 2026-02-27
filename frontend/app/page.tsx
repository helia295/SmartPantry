"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE =
  typeof window !== "undefined"
    ? "/api/proxy"
    : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Health = { status: string; service: string } | null;
type UserProfile = { id: number; email: string; timezone: string } | null;
type InventoryItem = {
  id: number;
  name: string;
  normalized_name: string;
  quantity: number;
  unit: string;
  category: string | null;
  is_perishable: boolean;
  user_id: number;
  created_at?: string | null;
  last_updated: string;
};

type Option = { value: string; label: string };

const UNIT_OPTIONS: Option[] = [
  { value: "count", label: "Count" },
  { value: "piece", label: "Piece" },
  { value: "g", label: "Gram (g)" },
  { value: "kg", label: "Kilogram (kg)" },
  { value: "oz", label: "Ounce (oz)" },
  { value: "lb", label: "Pound (lb)" },
  { value: "ml", label: "Milliliter (ml)" },
  { value: "l", label: "Liter (l)" },
  { value: "tsp", label: "Teaspoon (tsp)" },
  { value: "tbsp", label: "Tablespoon (tbsp)" },
  { value: "cup", label: "Cup" },
  { value: "pint", label: "Pint" },
  { value: "quart", label: "Quart" },
  { value: "gallon", label: "Gallon" },
  { value: "can", label: "Can" },
  { value: "jar", label: "Jar" },
  { value: "bottle", label: "Bottle" },
  { value: "box", label: "Box" },
  { value: "bag", label: "Bag" },
  { value: "carton", label: "Carton" },
  { value: "pack", label: "Pack" },
  { value: "slice", label: "Slice" },
  { value: "other", label: "Other" },
];

const CATEGORY_OPTIONS: Option[] = [
  { value: "Produce", label: "Produce" },
  { value: "Dairy & Eggs", label: "Dairy & Eggs" },
  { value: "Meat & Seafood", label: "Meat & Seafood" },
  { value: "Bakery", label: "Bakery" },
  { value: "Pantry", label: "Pantry" },
  { value: "Canned Goods", label: "Canned Goods" },
  { value: "Condiments & Sauces", label: "Condiments & Sauces" },
  { value: "Spices & Seasonings", label: "Spices & Seasonings" },
  { value: "Frozen Foods", label: "Frozen Foods" },
  { value: "Breakfast & Cereal", label: "Breakfast & Cereal" },
  { value: "Snacks", label: "Snacks" },
  { value: "Beverages", label: "Beverages" },
  { value: "Deli & Prepared Foods", label: "Deli & Prepared Foods" },
  { value: "International Foods", label: "International Foods" },
  { value: "Other", label: "Other" },
];

const FALLBACK_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Phoenix",
  "America/Anchorage",
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

function formatDate(isoValue?: string | null, timezone?: string): string {
  if (!isoValue) return "N/A";
  const hasTimezoneOffset = /[zZ]|[+\-]\d{2}:\d{2}$/.test(isoValue);
  const normalizedIso = hasTimezoneOffset ? isoValue : `${isoValue}Z`;
  const date = new Date(normalizedIso);
  if (Number.isNaN(date.getTime())) return "N/A";

  try {
    return date.toLocaleString([], timezone ? { timeZone: timezone } : undefined);
  } catch {
    return date.toLocaleString();
  }
}

export default function Home() {
  const [health, setHealth] = useState<Health>(null);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string>("");
  const [user, setUser] = useState<UserProfile>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [itemName, setItemName] = useState("");
  const [itemQty, setItemQty] = useState("1");
  const [itemUnit, setItemUnit] = useState(UNIT_OPTIONS[0].value);
  const [itemCategory, setItemCategory] = useState(CATEGORY_OPTIONS[0].value);
  const [itemPerishable, setItemPerishable] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [timezoneOptions, setTimezoneOptions] = useState<string[]>([]);
  const [selectedTimezone, setSelectedTimezone] = useState("UTC");

  const displayTimezone = user?.timezone || selectedTimezone;

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(e.message));

    const savedToken = localStorage.getItem("smartpantry_token");
    if (savedToken) {
      setToken(savedToken);
    }

    const supported = getSupportedTimezones();
    setTimezoneOptions(supported);

    const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    setSelectedTimezone(browserTimezone);
  }, []);

  useEffect(() => {
    if (!token) return;
    void loadCurrentUser();
    void loadInventory();
  }, [token]);

  const timezoneSelectOptions = useMemo(() => {
    const set = new Set<string>(timezoneOptions);
    set.add("UTC");
    if (selectedTimezone) set.add(selectedTimezone);
    if (user?.timezone) set.add(user.timezone);
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [timezoneOptions, selectedTimezone, user?.timezone]);

  async function parseError(res: Response): Promise<string> {
    try {
      const body = await res.json();
      return body.detail || body.message || "Request failed";
    } catch {
      return `Request failed (${res.status})`;
    }
  }

  async function register() {
    setMessage("");
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      setMessage(await parseError(res));
      return;
    }
    setMessage("Registered successfully. Log in next.");
  }

  async function login() {
    setMessage("");
    const body = new URLSearchParams();
    body.set("username", email);
    body.set("password", password);

    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) {
      setMessage(await parseError(res));
      return;
    }
    const data = await res.json();
    localStorage.setItem("smartpantry_token", data.access_token);
    setToken(data.access_token);
    setMessage("Logged in.");
  }

  async function loadCurrentUser() {
    if (!token) return;
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      setMessage("Session expired. Please log in again.");
      logout();
      return;
    }
    const data = await res.json();
    const userData = { id: data.id, email: data.email, timezone: data.timezone || "UTC" };
    setUser(userData);
    setSelectedTimezone(userData.timezone);
  }

  async function updateTimezone(timezone: string) {
    setSelectedTimezone(timezone);
    if (!token) return;

    const res = await fetch(`${API_BASE}/auth/me/timezone`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ timezone }),
    });
    if (!res.ok) {
      setMessage(await parseError(res));
      return;
    }

    const data = await res.json();
    setUser({ id: data.id, email: data.email, timezone: data.timezone || "UTC" });
    setMessage(`Timezone set to ${data.timezone}`);
  }

  function logout() {
    localStorage.removeItem("smartpantry_token");
    setToken("");
    setUser(null);
    setInventory([]);
    setEmail("");
    setPassword("");
    setMessage("Logged out.");
  }

  async function loadInventory() {
    if (!token) return;

    const res = await fetch(`${API_BASE}/inventory`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      setMessage(await parseError(res));
      return;
    }
    const data = await res.json();
    setInventory(data);
  }

  async function addItem() {
    if (!token) {
      setMessage("Login first.");
      return;
    }
    const res = await fetch(`${API_BASE}/inventory`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: itemName,
        quantity: Number(itemQty),
        unit: itemUnit,
        category: itemCategory || null,
        is_perishable: itemPerishable,
      }),
    });
    if (!res.ok) {
      setMessage(await parseError(res));
      return;
    }
    setItemName("");
    setItemQty("1");
    setItemUnit(UNIT_OPTIONS[0].value);
    setItemCategory(CATEGORY_OPTIONS[0].value);
    setItemPerishable(false);
    await loadInventory();
  }

  async function updateItem(item: InventoryItem) {
    if (!token) {
      setMessage("Login first.");
      return;
    }
    const name = window.prompt("New name:", item.name);
    if (!name) return;
    const qtyText = window.prompt("New quantity:", String(item.quantity));
    if (!qtyText) return;
    const qty = Number(qtyText);

    const res = await fetch(`${API_BASE}/inventory/${item.id}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name, quantity: qty }),
    });
    if (!res.ok) {
      setMessage(await parseError(res));
      return;
    }
    await loadInventory();
  }

  async function deleteItem(itemId: number) {
    if (!token) {
      setMessage("Login first.");
      return;
    }
    const res = await fetch(`${API_BASE}/inventory/${itemId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      setMessage(await parseError(res));
      return;
    }
    await loadInventory();
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: "2rem",
      }}
    >
      <section
        style={{
          width: "100%",
          maxWidth: 980,
          display: "grid",
          gap: "1rem",
          padding: "1.25rem",
          background: "var(--surface)",
          borderRadius: "10px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
          <div>
            <h1 style={{ fontSize: "1.8rem", fontWeight: 700 }}>SmartPantry MVP - Milestone 2</h1>
            <p style={{ color: "var(--muted)" }}>
              Minimal auth + inventory CRUD (no ML yet).
            </p>
          </div>

          {token && (
            <div style={{ display: "grid", gap: "0.35rem", alignContent: "start", minWidth: 240 }}>
              <label style={{ fontSize: "0.85rem", color: "var(--muted)" }}>Timezone</label>
              <select
                value={displayTimezone}
                onChange={(e) => void updateTimezone(e.target.value)}
                style={{ padding: "0.5rem" }}
              >
                {timezoneSelectOptions.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            style={{ padding: "0.5rem", minWidth: 220 }}
          />
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            type="password"
            style={{ padding: "0.5rem", minWidth: 220 }}
          />
          <button onClick={register} style={{ padding: "0.5rem 0.75rem" }}>
            Register
          </button>
          <button onClick={login} style={{ padding: "0.5rem 0.75rem" }}>
            Login
          </button>
          {token && (
            <button onClick={logout} style={{ padding: "0.5rem 0.75rem" }}>
              Logout
            </button>
          )}
        </div>

        {user && (
          <p style={{ color: "var(--muted)" }}>
            Logged in as: <strong>{user.email}</strong> ({user.timezone})
          </p>
        )}

        {token && (
          <details open>
            <summary style={{ cursor: "pointer", fontWeight: 600, marginBottom: "0.75rem" }}>
              Inventory
            </summary>
            <div style={{ display: "grid", gap: "0.75rem" }}>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                <input
                  value={itemName}
                  onChange={(e) => setItemName(e.target.value)}
                  placeholder="Item name"
                  style={{ padding: "0.5rem", minWidth: 180 }}
                />
                <input
                  value={itemQty}
                  onChange={(e) => setItemQty(e.target.value)}
                  placeholder="Qty"
                  type="number"
                  step="0.1"
                  style={{ padding: "0.5rem", width: 90 }}
                />
                <select
                  value={itemUnit}
                  onChange={(e) => setItemUnit(e.target.value)}
                  style={{ padding: "0.5rem", minWidth: 160 }}
                >
                  {UNIT_OPTIONS.map((unit) => (
                    <option key={unit.value} value={unit.value}>
                      {unit.label}
                    </option>
                  ))}
                </select>
                <select
                  value={itemCategory}
                  onChange={(e) => setItemCategory(e.target.value)}
                  style={{ padding: "0.5rem", minWidth: 210 }}
                >
                  {CATEGORY_OPTIONS.map((category) => (
                    <option key={category.value} value={category.value}>
                      {category.label}
                    </option>
                  ))}
                </select>
                <label style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                  <input
                    type="checkbox"
                    checked={itemPerishable}
                    onChange={(e) => setItemPerishable(e.target.checked)}
                  />
                  Perishable
                </label>
                <button onClick={addItem} style={{ padding: "0.5rem 0.75rem" }}>
                  Add Item
                </button>
                <button onClick={loadInventory} style={{ padding: "0.5rem 0.75rem" }}>
                  Refresh
                </button>
              </div>

              <div style={{ display: "grid", gap: "0.5rem" }}>
                {inventory.map((item) => (
                  <div
                    key={item.id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: "1rem",
                      padding: "0.75rem",
                      border: "1px solid #2f3b4d",
                      borderRadius: "8px",
                    }}
                  >
                    <span>
                      {item.name} - {item.quantity} {item.unit}
                      {item.category ? ` (${item.category})` : ""}
                      {item.is_perishable ? " [perishable]" : ""}
                      {` | Date Added: ${formatDate(item.created_at, displayTimezone)}`}
                    </span>
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      <button onClick={() => void updateItem(item)} style={{ padding: "0.4rem 0.6rem" }}>
                        Edit
                      </button>
                      <button onClick={() => void deleteItem(item.id)} style={{ padding: "0.4rem 0.6rem" }}>
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
                {inventory.length === 0 && <p style={{ color: "var(--muted)" }}>No items yet.</p>}
              </div>
            </div>
          </details>
        )}

        <div>
          <h2 style={{ fontSize: "0.95rem", marginBottom: "0.25rem" }}>API status</h2>
          {error && <p style={{ color: "var(--error)" }}>Backend unreachable: {error}</p>}
          {health && (
            <p style={{ color: "var(--success)" }}>
              {health.service} - {health.status}
            </p>
          )}
          {!health && !error && <p style={{ color: "var(--muted)" }}>Checking...</p>}
        </div>

        {message && <p style={{ color: "var(--accent)" }}>{message}</p>}
      </section>
    </main>
  );
}
