"use client";

import { useEffect, useState } from "react";

const API_BASE =
  typeof window !== "undefined"
    ? "/api/proxy"
    : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Health = { status: string; service: string } | null;
type InventoryItem = {
  id: number;
  name: string;
  normalized_name: string;
  quantity: number;
  unit: string;
  category: string | null;
  is_perishable: boolean;
  user_id: number;
};

export default function Home() {
  const [health, setHealth] = useState<Health>(null);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string>("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [itemName, setItemName] = useState("");
  const [itemQty, setItemQty] = useState("1");
  const [itemUnit, setItemUnit] = useState("count");
  const [itemCategory, setItemCategory] = useState("");
  const [itemPerishable, setItemPerishable] = useState(false);
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(e.message));

    const savedToken = localStorage.getItem("smartpantry_token");
    if (savedToken) {
      setToken(savedToken);
    }
  }, []);

  async function register() {
    setMessage("");
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const body = await res.json();
      setMessage(body.detail || "Registration failed");
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
      const err = await res.json();
      setMessage(err.detail || "Login failed");
      return;
    }
    const data = await res.json();
    localStorage.setItem("smartpantry_token", data.access_token);
    setToken(data.access_token);
    setMessage("Logged in.");
  }

  async function loadInventory() {
    if (!token) {
      setMessage("Login first.");
      return;
    }
    const res = await fetch(`${API_BASE}/inventory`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      setMessage("Could not load inventory.");
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
      setMessage("Failed to add item.");
      return;
    }
    setItemName("");
    setItemQty("1");
    setItemUnit("count");
    setItemCategory("");
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
      setMessage("Failed to update item.");
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
      setMessage("Failed to delete item.");
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
          maxWidth: 900,
          display: "grid",
          gap: "1rem",
          padding: "1.25rem",
          background: "var(--surface)",
          borderRadius: "10px",
        }}
      >
        <h1 style={{ fontSize: "1.8rem", fontWeight: 700 }}>SmartPantry MVP - Milestone 2</h1>
        <p style={{ color: "var(--muted)" }}>
          Minimal auth + inventory CRUD (no ML yet).
        </p>

        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
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
          <button onClick={loadInventory} style={{ padding: "0.5rem 0.75rem" }}>
            Load Inventory
          </button>
        </div>

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
          <input
            value={itemUnit}
            onChange={(e) => setItemUnit(e.target.value)}
            placeholder="Unit"
            style={{ padding: "0.5rem", width: 120 }}
          />
          <input
            value={itemCategory}
            onChange={(e) => setItemCategory(e.target.value)}
            placeholder="Category"
            style={{ padding: "0.5rem", width: 150 }}
          />
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
              </span>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button onClick={() => updateItem(item)} style={{ padding: "0.4rem 0.6rem" }}>
                  Edit
                </button>
                <button onClick={() => deleteItem(item.id)} style={{ padding: "0.4rem 0.6rem" }}>
                  Delete
                </button>
              </div>
            </div>
          ))}
          {inventory.length === 0 && <p style={{ color: "var(--muted)" }}>No items yet.</p>}
        </div>

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
