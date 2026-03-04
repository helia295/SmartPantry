"use client";

import { ChangeEvent, MouseEvent, useEffect, useMemo, useRef, useState } from "react";

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

type ImageRecord = {
  id: number;
  user_id: number;
  storage_key: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
  expires_at: string;
  deleted_at?: string | null;
};

type DetectionProposal = {
  id: number;
  session_id: number;
  label_raw: string;
  label_normalized: string;
  confidence?: number | null;
  quantity_suggested?: number | null;
  quantity_unit?: string | null;
  category_suggested?: string | null;
  is_perishable_suggested?: boolean | null;
  bbox_x?: number | null;
  bbox_y?: number | null;
  bbox_w?: number | null;
  bbox_h?: number | null;
  source?: string | null;
  state: string;
};

type UploadResult = {
  image: ImageRecord;
  detection_session: {
    id: number;
    image_id: number;
    user_id: number;
    status: string;
    model_version?: string | null;
  };
};

type FilePick = {
  key: string;
  file: File;
  previewUrl: string;
};

type ReviewFrame = {
  image: ImageRecord;
  sessionId: number;
  imageUrl: string;
  proposals: DetectionProposal[];
};

const UNIT_OPTIONS: Option[] = [
  { value: "count", label: "Count" },
  { value: "piece", label: "Piece" },
  { value: "g", label: "Gram (g)" },
  { value: "kg", label: "Kilogram (kg)" },
  { value: "oz", label: "Ounce (oz)" },
  { value: "lb", label: "Pound (lb)" },
  { value: "ml", label: "Milliliter (ml)" },
  { value: "l", label: "Liter (l)" },
  { value: "cup", label: "Cup" },
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

function normalizeLabel(label: string): string {
  return label.trim().toLowerCase().replace(/\s+/g, " ");
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

  const [pickedFiles, setPickedFiles] = useState<FilePick[]>([]);
  const [uploading, setUploading] = useState(false);
  const [reviewFrames, setReviewFrames] = useState<ReviewFrame[]>([]);
  const [activeImageIndex, setActiveImageIndex] = useState(0);
  const [activeProposalIndex, setActiveProposalIndex] = useState(0);
  const [manualPointMode, setManualPointMode] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);

  const cameraInputRef = useRef<HTMLInputElement | null>(null);
  const libraryInputRef = useRef<HTMLInputElement | null>(null);
  const cameraVideoRef = useRef<HTMLVideoElement | null>(null);
  const cameraCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);

  const displayTimezone = user?.timezone || selectedTimezone;

  const activeFrame = reviewFrames[activeImageIndex] || null;
  const activeProposal = activeFrame?.proposals[activeProposalIndex] || null;

  const activeInventoryMatch = useMemo(() => {
    if (!activeProposal) return null;
    const normalized = normalizeLabel(activeProposal.label_raw || activeProposal.label_normalized);
    return inventory.find((item) => item.normalized_name === normalized) || null;
  }, [activeProposal, inventory]);

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(e.message));

    const savedToken = localStorage.getItem("smartpantry_token");
    if (savedToken) setToken(savedToken);

    const supported = getSupportedTimezones();
    setTimezoneOptions(supported);
    setSelectedTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  }, []);

  useEffect(() => {
    return () => {
      stopCameraStream();
    };
  }, []);

  useEffect(() => {
    if (!token) return;
    void loadCurrentUser();
    void loadInventory();
  }, [token]);

  useEffect(() => {
    return () => {
      pickedFiles.forEach((f) => URL.revokeObjectURL(f.previewUrl));
      reviewFrames.forEach((f) => {
        if (f.imageUrl.startsWith("blob:")) URL.revokeObjectURL(f.imageUrl);
      });
    };
  }, []);

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

  function authHeaders(contentType?: string): HeadersInit {
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
    if (contentType) headers["Content-Type"] = contentType;
    return headers;
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
    const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
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
      headers: authHeaders("application/json"),
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

  function clearReviewState() {
    setReviewFrames((prev) => {
      prev.forEach((f) => {
        if (f.imageUrl.startsWith("blob:")) URL.revokeObjectURL(f.imageUrl);
      });
      return [];
    });
    setActiveImageIndex(0);
    setActiveProposalIndex(0);
    setManualPointMode(false);
  }

  function stopCameraStream() {
    const stream = cameraStreamRef.current;
    if (!stream) return;
    stream.getTracks().forEach((track) => track.stop());
    cameraStreamRef.current = null;
  }

  function logout() {
    localStorage.removeItem("smartpantry_token");
    setToken("");
    setUser(null);
    setInventory([]);
    setEmail("");
    setPassword("");
    setMessage("Logged out.");
    clearReviewState();
  }

  async function loadInventory() {
    const res = await fetch(`${API_BASE}/inventory`, { headers: authHeaders() });
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
      headers: authHeaders("application/json"),
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
    const name = window.prompt("New name:", item.name);
    if (!name) return;
    const qtyText = window.prompt("New quantity:", String(item.quantity));
    if (!qtyText) return;
    const qty = Number(qtyText);

    const res = await fetch(`${API_BASE}/inventory/${item.id}`, {
      method: "PATCH",
      headers: authHeaders("application/json"),
      body: JSON.stringify({ name, quantity: qty }),
    });
    if (!res.ok) {
      setMessage(await parseError(res));
      return;
    }
    await loadInventory();
  }

  async function deleteItem(itemId: number) {
    const res = await fetch(`${API_BASE}/inventory/${itemId}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (!res.ok) {
      setMessage(await parseError(res));
      return;
    }
    await loadInventory();
  }

  function appendEntryFiles(files: File[]) {
    const entries: FilePick[] = files.map((file) => ({
      key: `${file.name}-${file.size}-${crypto.randomUUID()}`,
      file,
      previewUrl: URL.createObjectURL(file),
    }));

    setPickedFiles((prev) => {
      const max = 3;
      const combined = [...prev, ...entries].slice(0, max);
      const dropped = [...prev, ...entries].slice(max);
      dropped.forEach((f) => URL.revokeObjectURL(f.previewUrl));
      return combined;
    });
  }

  function appendFiles(fileList: FileList | null) {
    if (!fileList) return;
    appendEntryFiles(Array.from(fileList));
  }

  function onCameraPick(event: ChangeEvent<HTMLInputElement>) {
    appendFiles(event.target.files);
    if (cameraInputRef.current) cameraInputRef.current.value = "";
  }

  function onLibraryPick(event: ChangeEvent<HTMLInputElement>) {
    appendFiles(event.target.files);
    if (libraryInputRef.current) libraryInputRef.current.value = "";
  }

  function removePickedFile(key: string) {
    setPickedFiles((prev) => {
      const target = prev.find((f) => f.key === key);
      if (target) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((f) => f.key !== key);
    });
  }

  function clearPickedFiles() {
    setPickedFiles((prev) => {
      prev.forEach((f) => URL.revokeObjectURL(f.previewUrl));
      return [];
    });
    setMessage("Selected uploads cleared.");
  }

  async function openCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      cameraInputRef.current?.click();
      return;
    }

    try {
      setCameraError(null);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      cameraStreamRef.current = stream;
      setCameraOpen(true);

      requestAnimationFrame(() => {
        if (cameraVideoRef.current) {
          cameraVideoRef.current.srcObject = stream;
        }
      });
    } catch {
      setCameraError("Camera not available or permission denied. Falling back to file upload.");
      cameraInputRef.current?.click();
    }
  }

  function closeCamera() {
    stopCameraStream();
    setCameraOpen(false);
  }

  function captureCameraImage() {
    const video = cameraVideoRef.current;
    const canvas = cameraCanvasRef.current;
    if (!video || !canvas) return;

    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, width, height);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const file = new File([blob], `camera-${Date.now()}.jpg`, { type: "image/jpeg" });
        appendEntryFiles([file]);
        closeCamera();
      },
      "image/jpeg",
      0.92
    );
  }

  async function fetchImageObjectUrl(imageId: number): Promise<string> {
    const contentRes = await fetch(`${API_BASE}/images/${imageId}/content`, {
      headers: authHeaders(),
    });
    if (!contentRes.ok) {
      throw new Error(`Image content for ${imageId} could not be loaded`);
    }
    const blob = await contentRes.blob();
    return URL.createObjectURL(blob);
  }

  async function uploadAndAnalyze() {
    if (!token) {
      setMessage("Log in first.");
      return;
    }
    if (pickedFiles.length === 0) {
      setMessage("Pick at least one image first.");
      return;
    }

    const form = new FormData();
    pickedFiles.forEach((entry) => form.append("files", entry.file));

    setUploading(true);
    setMessage("Uploading and running detection...");

    const res = await fetch(`${API_BASE}/images`, {
      method: "POST",
      headers: authHeaders(),
      body: form,
    });

    if (!res.ok) {
      setUploading(false);
      setMessage(await parseError(res));
      return;
    }

    const payload: { results: UploadResult[] } = await res.json();

    const framePromises = payload.results.map(async (row) => {
      const detectionRes = await fetch(`${API_BASE}/detections/${row.detection_session.id}`, {
        headers: authHeaders(),
      });
      if (!detectionRes.ok) {
        throw new Error(`Detection session ${row.detection_session.id} could not be loaded`);
      }
      const detail = (await detectionRes.json()) as {
        proposals: DetectionProposal[];
      };
      const imageUrl = await fetchImageObjectUrl(row.image.id);

      return {
        image: row.image,
        sessionId: row.detection_session.id,
        imageUrl,
        proposals: detail.proposals,
      } as ReviewFrame;
    });

    try {
      const frames = await Promise.all(framePromises);
      clearReviewState();
      setReviewFrames(frames);
      setActiveImageIndex(0);
      setActiveProposalIndex(0);
      clearPickedFiles();
      setMessage("Detection ready. Review each proposal.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Failed to load detection proposals");
    } finally {
      setUploading(false);
    }
  }

  function updateActiveProposal(patch: Partial<DetectionProposal>) {
    if (!activeFrame || !activeProposal) return;

    setReviewFrames((prev) =>
      prev.map((frame, frameIndex) => {
        if (frameIndex !== activeImageIndex) return frame;
        const proposals = frame.proposals.map((proposal, proposalIndex) =>
          proposalIndex === activeProposalIndex ? { ...proposal, ...patch } : proposal
        );
        return { ...frame, proposals };
      })
    );
  }

  function moveToNextProposal() {
    if (!activeFrame) return;
    if (activeProposalIndex + 1 < activeFrame.proposals.length) {
      setActiveProposalIndex((idx) => idx + 1);
      return;
    }

    if (activeImageIndex + 1 < reviewFrames.length) {
      setActiveImageIndex((idx) => idx + 1);
      setActiveProposalIndex(0);
      return;
    }

    setMessage("Review complete for all uploaded images.");
  }

  async function persistActiveProposal(stateOverride?: string): Promise<boolean> {
    if (!activeFrame || !activeProposal) return false;
    const res = await fetch(
      `${API_BASE}/detections/${activeFrame.sessionId}/proposals/${activeProposal.id}`,
      {
        method: "PATCH",
        headers: authHeaders("application/json"),
        body: JSON.stringify({
          label_raw: activeProposal.label_raw,
          quantity_suggested: activeProposal.quantity_suggested ?? 1,
          quantity_unit: activeProposal.quantity_unit || "count",
          category_suggested: activeProposal.category_suggested || "Other",
          is_perishable_suggested: Boolean(activeProposal.is_perishable_suggested),
          state: stateOverride || activeProposal.state || "pending",
        }),
      }
    );
    if (!res.ok) {
      setMessage(await parseError(res));
      return false;
    }

    const saved = (await res.json()) as DetectionProposal;
    updateActiveProposal(saved);
    return true;
  }

  async function addProposalToInventory() {
    if (!activeProposal) return;
    const name = activeProposal.label_raw;
    const quantity = activeProposal.quantity_suggested || 1;
    const unit = activeProposal.quantity_unit || "count";
    const category = activeProposal.category_suggested || "Other";
    const isPerishable = Boolean(activeProposal.is_perishable_suggested);

    const persisted = await persistActiveProposal("accepted");
    if (!persisted) return;

    const res = await fetch(`${API_BASE}/inventory`, {
      method: "POST",
      headers: authHeaders("application/json"),
      body: JSON.stringify({
        name,
        quantity,
        unit,
        category,
        is_perishable: isPerishable,
      }),
    });
    if (!res.ok) {
      setMessage(await parseError(res));
      return;
    }

    await loadInventory();
    moveToNextProposal();
  }

  async function updateMatchingInventory() {
    if (!activeProposal || !activeInventoryMatch) {
      setMessage("No matching inventory item found for update.");
      return;
    }
    const persisted = await persistActiveProposal("accepted");
    if (!persisted) return;

    const mergedQuantity = activeInventoryMatch.quantity + (activeProposal.quantity_suggested || 1);
    const res = await fetch(`${API_BASE}/inventory/${activeInventoryMatch.id}`, {
      method: "PATCH",
      headers: authHeaders("application/json"),
      body: JSON.stringify({
        quantity: mergedQuantity,
        category: activeInventoryMatch.category || activeProposal.category_suggested || "Other",
      }),
    });
    if (!res.ok) {
      setMessage(await parseError(res));
      return;
    }

    await loadInventory();
    moveToNextProposal();
  }

  async function manualAddFromCurrentImage() {
    if (!activeFrame) return;
    setManualPointMode(true);
    setMessage("Manual mode on. Click the image where the missed item is.");
  }

  async function handleImageClick(event: MouseEvent<HTMLImageElement>) {
    if (!manualPointMode || !activeFrame) return;

    const rect = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    const labelHint = window.prompt("Optional hint for item label:", "") || undefined;

    const res = await fetch(`${API_BASE}/detections/${activeFrame.sessionId}/manual-proposals`, {
      method: "POST",
      headers: authHeaders("application/json"),
      body: JSON.stringify({ x, y, w: 0.22, h: 0.22, label_hint: labelHint }),
    });
    if (!res.ok) {
      setMessage(await parseError(res));
      return;
    }
    const proposal = (await res.json()) as DetectionProposal;

    setReviewFrames((prev) =>
      prev.map((frame, idx) =>
        idx === activeImageIndex ? { ...frame, proposals: [...frame.proposals, proposal] } : frame
      )
    );
    setActiveProposalIndex(activeFrame.proposals.length);
    setManualPointMode(false);
    setMessage("Manual proposal added. Review and confirm it.");
  }

  const activeBox =
    activeProposal &&
    activeProposal.bbox_x !== null &&
    activeProposal.bbox_y !== null &&
    activeProposal.bbox_w !== null &&
    activeProposal.bbox_h !== null
      ? {
          left: `${Math.max(0, activeProposal.bbox_x || 0) * 100}%`,
          top: `${Math.max(0, activeProposal.bbox_y || 0) * 100}%`,
          width: `${Math.min(1, activeProposal.bbox_w || 0) * 100}%`,
          height: `${Math.min(1, activeProposal.bbox_h || 0) * 100}%`,
        }
      : null;

  return (
    <main className="app-wrap">
      <section className="shell">
        <div className="hero-row">
          <div>
            <h1 className="title">SmartPantry - Milestone 3/4</h1>
            <p className="subtitle">Private image upload, proposal review, and human-in-loop inventory updates.</p>
          </div>

          {token && (
            <div className="timezone-panel">
              <label>Timezone</label>
              <select value={displayTimezone} onChange={(e) => void updateTimezone(e.target.value)}>
                {timezoneSelectOptions.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="card">
          <div className="auth-row">
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              type="password"
            />
            <button onClick={() => void register()}>Register</button>
            <button onClick={() => void login()}>Login</button>
            {token && <button onClick={logout}>Logout</button>}
          </div>

          {user && (
            <p className="muted-text">
              Logged in as <strong>{user.email}</strong> ({user.timezone})
            </p>
          )}
        </div>

        <div className="two-col">
          <section className="card">
            <h2>Inventory</h2>
            <div className="toolbar-wrap">
              <input value={itemName} onChange={(e) => setItemName(e.target.value)} placeholder="Item name" />
              <input
                value={itemQty}
                onChange={(e) => setItemQty(e.target.value)}
                type="number"
                step="0.1"
                placeholder="Qty"
              />
              <select value={itemUnit} onChange={(e) => setItemUnit(e.target.value)}>
                {UNIT_OPTIONS.map((u) => (
                  <option key={u.value} value={u.value}>
                    {u.label}
                  </option>
                ))}
              </select>
              <select value={itemCategory} onChange={(e) => setItemCategory(e.target.value)}>
                {CATEGORY_OPTIONS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={itemPerishable}
                  onChange={(e) => setItemPerishable(e.target.checked)}
                />
                Perishable
              </label>
              <button onClick={() => void addItem()}>Add Item</button>
            </div>

            <div className="list-col">
              {inventory.map((item) => (
                <article key={item.id} className="list-item">
                  <div>
                    <strong>{item.name}</strong>
                    <p className="muted-text">
                      {item.quantity} {item.unit} {item.category ? `- ${item.category}` : ""}
                    </p>
                    <p className="tiny-text">Date Added: {formatDate(item.created_at, displayTimezone)}</p>
                  </div>
                  <div className="row-gap">
                    <button onClick={() => void updateItem(item)}>Edit</button>
                    <button onClick={() => void deleteItem(item.id)}>Delete</button>
                  </div>
                </article>
              ))}
              {inventory.length === 0 && <p className="muted-text">No items yet.</p>}
            </div>
          </section>

          <section className="card">
            <h2>Upload & Review</h2>
            <p className="muted-text">Take photos from camera or select from library (max 3).</p>

            <div className="toolbar-wrap">
              <button onClick={() => void openCamera()}>Take Photo</button>
              <button onClick={() => libraryInputRef.current?.click()}>Upload From Device</button>
              <input
                ref={cameraInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={onCameraPick}
                hidden
              />
              <input
                ref={libraryInputRef}
                type="file"
                accept="image/*"
                multiple
                onChange={onLibraryPick}
                hidden
              />
              <button onClick={clearPickedFiles}>Clear Picks</button>
              <button onClick={() => void uploadAndAnalyze()} disabled={uploading || pickedFiles.length === 0}>
                {uploading ? "Uploading..." : "Upload & Detect"}
              </button>
            </div>

            {pickedFiles.length > 0 && (
              <div className="preview-grid">
                {pickedFiles.map((entry) => (
                  <figure key={entry.key} className="preview-card">
                    <img src={entry.previewUrl} alt={entry.file.name} />
                    <figcaption>{entry.file.name}</figcaption>
                    <button onClick={() => removePickedFile(entry.key)}>Remove</button>
                  </figure>
                ))}
              </div>
            )}

            {cameraError && <p className="tiny-text">{cameraError}</p>}

            {activeFrame && (
              <div className="review-grid">
                <div>
                  <div className="image-stage">
                    <img
                      src={activeFrame.imageUrl}
                      alt={activeFrame.image.original_filename}
                      onClick={(e) => void handleImageClick(e)}
                    />
                    {activeBox && <div className="bbox" style={activeBox} />}
                  </div>
                  <p className="tiny-text">
                    Image {activeImageIndex + 1}/{reviewFrames.length} - {activeFrame.image.original_filename}
                  </p>
                  {manualPointMode && (
                    <p className="tiny-text">Manual mode enabled: click image to add missed item proposal.</p>
                  )}
                </div>

                <div className="proposal-panel">
                  {activeProposal ? (
                    <>
                      <h3>
                        Proposal {activeProposalIndex + 1}/{activeFrame.proposals.length}
                      </h3>
                      <label>Detected label</label>
                      <input
                        value={activeProposal.label_raw}
                        onChange={(e) => updateActiveProposal({ label_raw: e.target.value })}
                      />

                      <label>Suggested quantity</label>
                      <input
                        type="number"
                        step="0.1"
                        value={activeProposal.quantity_suggested || 1}
                        onChange={(e) =>
                          updateActiveProposal({ quantity_suggested: Number(e.target.value || "1") })
                        }
                      />

                      <label>Unit</label>
                      <select
                        value={activeProposal.quantity_unit || "count"}
                        onChange={(e) => updateActiveProposal({ quantity_unit: e.target.value })}
                      >
                        {UNIT_OPTIONS.map((u) => (
                          <option key={u.value} value={u.value}>
                            {u.label}
                          </option>
                        ))}
                      </select>

                      <label>Category</label>
                      <select
                        value={activeProposal.category_suggested || "Other"}
                        onChange={(e) => updateActiveProposal({ category_suggested: e.target.value })}
                      >
                        {CATEGORY_OPTIONS.map((c) => (
                          <option key={c.value} value={c.value}>
                            {c.label}
                          </option>
                        ))}
                      </select>

                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={Boolean(activeProposal.is_perishable_suggested)}
                          onChange={(e) =>
                            updateActiveProposal({ is_perishable_suggested: e.target.checked })
                          }
                        />
                        Perishable
                      </label>

                      <p className="tiny-text">
                        Confidence: {activeProposal.confidence?.toFixed(2) || "N/A"} | Source: {activeProposal.source || "auto"} | Current state: {activeProposal.state}
                      </p>

                      {activeInventoryMatch ? (
                        <p className="tiny-text">
                          Potential duplicate in inventory: <strong>{activeInventoryMatch.name}</strong>
                        </p>
                      ) : (
                        <p className="tiny-text">No duplicate match in current inventory.</p>
                      )}

                      <div className="row-gap">
                        <button onClick={() => void addProposalToInventory()}>Add As New</button>
                        <button onClick={() => void updateMatchingInventory()} disabled={!activeInventoryMatch}>
                          Update Existing
                        </button>
                        <button
                          onClick={() => void (async () => {
                            const persisted = await persistActiveProposal("rejected");
                            if (!persisted) return;
                            updateActiveProposal({ state: "rejected" });
                            moveToNextProposal();
                          })()}
                        >
                          Skip
                        </button>
                        <button onClick={() => void manualAddFromCurrentImage()}>Manual Point Add</button>
                      </div>
                    </>
                  ) : (
                    <p className="muted-text">No proposal to review on this image.</p>
                  )}
                </div>
              </div>
            )}
          </section>
        </div>

        <div className="card">
          <h3>System</h3>
          {error && <p className="error">Backend unreachable: {error}</p>}
          {health && (
            <p className="ok">
              {health.service} - {health.status}
            </p>
          )}
          {!health && !error && <p className="muted-text">Checking...</p>}
          {message && <p className="note">{message}</p>}
        </div>

        {cameraOpen && (
          <div className="camera-modal-backdrop">
            <div className="camera-modal">
              <h3>Take Photo</h3>
              <video ref={cameraVideoRef} autoPlay playsInline muted className="camera-video" />
              <canvas ref={cameraCanvasRef} hidden />
              <div className="row-gap">
                <button onClick={captureCameraImage}>Capture</button>
                <button onClick={closeCamera}>Cancel</button>
              </div>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
