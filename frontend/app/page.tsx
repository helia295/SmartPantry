"use client";

import Link from "next/link";
import { ChangeEvent, MouseEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useSlidingSession } from "./lib/session";

const API_BASE =
  typeof window !== "undefined"
    ? "/api/proxy"
    : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Health = { status: string; service: string } | null;
type UserProfile = { id: number; email: string; display_name: string; timezone: string } | null;

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
type RecipeSummary = {
  id: number;
  title: string;
  slug: string;
  source_name?: string | null;
  source_url?: string | null;
  image_url?: string | null;
  rating?: number | null;
  current_feedback?: "like" | "dislike" | null;
  prep_minutes?: number | null;
  cook_minutes?: number | null;
  total_minutes?: number | null;
  servings?: number | null;
  cuisine?: string | null;
  dietary_tags: string[];
  nutrition: Record<string, string | number | boolean | null>;
};

type RecipeRecommendation = {
  recipe: RecipeSummary;
  score: number;
  inventory_match_count: number;
  required_ingredient_count: number;
  matched_ingredients: string[];
  missing_ingredients: string[];
};

type RecipeRecommendationResponse = {
  page: number;
  page_size: number;
  total_results: number;
  total_pages: number;
  results: RecipeRecommendation[];
};

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
  detection_session_id?: number | null;
  detection_session_status?: string | null;
  pending_proposal_count?: number | null;
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
type ReviewMode = "grouped" | "boxes";
type NoticeSection = "auth" | "inventory" | "camera" | "recipes";
type NoticeTone = "success" | "error" | "info";
type DashboardNotice = {
  section: NoticeSection;
  tone: NoticeTone;
  text: string;
};
type InventoryEditDraft = {
  name: string;
  quantity: string;
  unit: string;
  category: string;
  is_perishable: boolean;
  refreshCreatedAt: boolean;
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

const CATEGORY_META: Record<string, { icon: string; label: string; accent: string }> = {
  Produce: { icon: "🥕", label: "Produce", accent: "produce" },
  "Dairy & Eggs": { icon: "🥛", label: "Dairy & Eggs", accent: "dairy" },
  "Meat & Seafood": { icon: "🥩", label: "Meat & Seafood", accent: "meat" },
  Bakery: { icon: "🥖", label: "Bakery", accent: "bakery" },
  Pantry: { icon: "🥫", label: "Pantry", accent: "pantry" },
  "Canned Goods": { icon: "🥫", label: "Canned Goods", accent: "pantry" },
  "Condiments & Sauces": { icon: "🫙", label: "Condiments & Sauces", accent: "sauces" },
  "Spices & Seasonings": { icon: "🧂", label: "Spices & Seasonings", accent: "spices" },
  "Frozen Foods": { icon: "🧊", label: "Frozen Foods", accent: "frozen" },
  "Breakfast & Cereal": { icon: "🥣", label: "Breakfast & Cereal", accent: "breakfast" },
  Snacks: { icon: "🍿", label: "Snacks", accent: "snacks" },
  Beverages: { icon: "🧃", label: "Beverages", accent: "drinks" },
  "Deli & Prepared Foods": { icon: "🥪", label: "Deli & Prepared Foods", accent: "deli" },
  "International Foods": { icon: "🍜", label: "International Foods", accent: "international" },
  Other: { icon: "🧺", label: "Other", accent: "other" },
};

const MANUAL_HINT_SUGGESTIONS = [
  "milk",
  "eggs",
  "bread",
  "rice",
  "cheese",
  "tomatoes",
  "onion",
  "chicken",
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

function formatInventoryDate(isoValue?: string | null, timezone?: string): string {
  if (!isoValue) return "N/A";
  const hasTimezoneOffset = /[zZ]|[+\-]\d{2}:\d{2}$/.test(isoValue);
  const normalizedIso = hasTimezoneOffset ? isoValue : `${isoValue}Z`;
  const date = new Date(normalizedIso);
  if (Number.isNaN(date.getTime())) return "N/A";

  try {
    return date.toLocaleString([], {
      timeZone: timezone,
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return date.toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }
}

function buildAllrecipesSearchUrl(title: string): string {
  return `https://www.allrecipes.com/search?q=${encodeURIComponent(title)}`;
}

function displayRecipeSourceName(sourceName?: string | null): string {
  if (!sourceName || sourceName === "allrecipes-search") return "Allrecipes.com";
  return sourceName;
}

function RecipeCardImage({ src, alt }: { src?: string | null; alt: string }) {
  const [broken, setBroken] = useState(false);

  if (!src || broken) {
    return <div className="recipe-image recipe-image-fallback">Recipe image unavailable</div>;
  }

  return (
    <img
      src={src}
      alt={alt}
      className="recipe-image"
      onError={() => setBroken(true)}
    />
  );
}

function getVisiblePageNumbers(currentPage: number, totalPages: number): number[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages = new Set<number>([1, totalPages, currentPage]);
  for (let page = currentPage - 1; page <= currentPage + 1; page += 1) {
    if (page > 1 && page < totalPages) pages.add(page);
  }

  if (currentPage <= 3) {
    pages.add(2);
    pages.add(3);
    pages.add(4);
  }

  if (currentPage >= totalPages - 2) {
    pages.add(totalPages - 1);
    pages.add(totalPages - 2);
    pages.add(totalPages - 3);
  }

  return Array.from(pages)
    .filter((page) => page >= 1 && page <= totalPages)
    .sort((a, b) => a - b);
}

function getCategoryMeta(category?: string | null) {
  return CATEGORY_META[category || "Other"] || CATEGORY_META.Other;
}

function getProposalStateLabel(state: string): string {
  switch (state) {
    case "added":
      return "Added";
    case "updated":
      return "Updated";
    case "accepted":
      return "Accepted";
    case "rejected":
    case "skipped":
      return "Skipped";
    default:
      return "Pending";
  }
}

function findNextPendingPosition(
  frames: ReviewFrame[],
  startImageIndex: number,
  startProposalIndex: number
): { imageIndex: number; proposalIndex: number } | null {
  if (frames.length === 0) return null;

  for (let imageIndex = startImageIndex; imageIndex < frames.length; imageIndex += 1) {
    const frame = frames[imageIndex];
    const proposalStart = imageIndex === startImageIndex ? startProposalIndex + 1 : 0;
    const proposalIndex = frame.proposals.findIndex(
      (proposal, index) => index >= proposalStart && proposal.state === "pending"
    );
    if (proposalIndex >= 0) {
      return { imageIndex, proposalIndex };
    }
  }

  for (let imageIndex = 0; imageIndex <= startImageIndex; imageIndex += 1) {
    const frame = frames[imageIndex];
    const proposalLimit = imageIndex === startImageIndex ? startProposalIndex : frame.proposals.length;
    const proposalIndex = frame.proposals.findIndex(
      (proposal, index) => index < proposalLimit && proposal.state === "pending"
    );
    if (proposalIndex >= 0) {
      return { imageIndex, proposalIndex };
    }
  }

  return null;
}

export default function Home() {
  const [health, setHealth] = useState<Health>(null);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [itemName, setItemName] = useState("");
  const [itemQty, setItemQty] = useState("1");
  const [itemUnit, setItemUnit] = useState(UNIT_OPTIONS[0].value);
  const [itemCategory, setItemCategory] = useState(CATEGORY_OPTIONS[0].value);
  const [itemPerishable, setItemPerishable] = useState(false);
  const [showQuickAdd, setShowQuickAdd] = useState(false);
  const [inventoryFilter, setInventoryFilter] = useState("All");
  const [showInventoryCategories, setShowInventoryCategories] = useState(true);
  const [editingItemId, setEditingItemId] = useState<number | null>(null);
  const [inventoryDraft, setInventoryDraft] = useState<InventoryEditDraft | null>(null);
  const [notice, setNotice] = useState<DashboardNotice | null>(null);

  const [timezoneOptions, setTimezoneOptions] = useState<string[]>([]);
  const [selectedTimezone, setSelectedTimezone] = useState("UTC");

  const [pickedFiles, setPickedFiles] = useState<FilePick[]>([]);
  const [uploading, setUploading] = useState(false);
  const [reviewFrames, setReviewFrames] = useState<ReviewFrame[]>([]);
  const [activeImageIndex, setActiveImageIndex] = useState(0);
  const [activeProposalIndex, setActiveProposalIndex] = useState(0);
  const [activeProposalQuantityInput, setActiveProposalQuantityInput] = useState("1");
  const [reviewMode, setReviewMode] = useState<ReviewMode>("grouped");
  const [manualPointMode, setManualPointMode] = useState(false);
  const [manualLabelHint, setManualLabelHint] = useState("");
  const [pendingManualPoint, setPendingManualPoint] = useState<{ x: number; y: number } | null>(null);
  const [cameraWorkspaceOpen, setCameraWorkspaceOpen] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [showRecipeFinder, setShowRecipeFinder] = useState(false);
  const [recipeMainIngredients, setRecipeMainIngredients] = useState("");
  const [recipeMaxTotalMinutes, setRecipeMaxTotalMinutes] = useState("");
  const [recipeResults, setRecipeResults] = useState<RecipeRecommendation[]>([]);
  const [recipesLoading, setRecipesLoading] = useState(false);
  const [recipePage, setRecipePage] = useState(1);
  const [recipePageSize] = useState(10);
  const [recipeTotalPages, setRecipeTotalPages] = useState(0);
  const [recipeTotalResults, setRecipeTotalResults] = useState(0);

  const cameraInputRef = useRef<HTMLInputElement | null>(null);
  const libraryInputRef = useRef<HTMLInputElement | null>(null);
  const cameraVideoRef = useRef<HTMLVideoElement | null>(null);
  const cameraCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const activeImageRef = useRef<HTMLImageElement | null>(null);
  const cameraSectionRef = useRef<HTMLElement | null>(null);

  const [activeImageBounds, setActiveImageBounds] = useState<{
    left: number;
    top: number;
    width: number;
    height: number;
  } | null>(null);

  const displayTimezone = user?.timezone || selectedTimezone;

  const activeFrame = reviewFrames[activeImageIndex] || null;
  const activeProposal = activeFrame?.proposals[activeProposalIndex] || null;

  const activeInventoryMatch = useMemo(() => {
    if (!activeProposal) return null;
    const normalized = normalizeLabel(activeProposal.label_raw || activeProposal.label_normalized);
    return inventory.find((item) => item.normalized_name === normalized) || null;
  }, [activeProposal, inventory]);

  function recalculateActiveImageBounds() {
    const img = activeImageRef.current;
    if (!img) return;

    const frameWidth = img.clientWidth;
    const frameHeight = img.clientHeight;
    const naturalWidth = img.naturalWidth;
    const naturalHeight = img.naturalHeight;

    if (!frameWidth || !frameHeight || !naturalWidth || !naturalHeight) {
      setActiveImageBounds(null);
      return;
    }

    const scale = Math.min(frameWidth / naturalWidth, frameHeight / naturalHeight);
    const width = naturalWidth * scale;
    const height = naturalHeight * scale;
    const left = (frameWidth - width) / 2;
    const top = (frameHeight - height) / 2;
    setActiveImageBounds({ left, top, width, height });
  }

  const handleSessionExpired = useCallback(() => {
    setUser(null);
    setDisplayName("");
    setInventory([]);
    setEmail("");
    setPassword("");
    setAuthMode("login");
    showNotice("auth", "error", "Session expired due to inactivity. Please log in again.");
    clearReviewState();
  }, []);

  const { token, setSessionToken, clearSessionToken } = useSlidingSession({
    apiBase: API_BASE,
    onExpired: handleSessionExpired,
  });

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(e.message));

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
    void loadRecentUploads();
  }, [token]);

  useEffect(() => {
    return () => {
      pickedFiles.forEach((f) => URL.revokeObjectURL(f.previewUrl));
      reviewFrames.forEach((f) => {
        if (f.imageUrl.startsWith("blob:")) URL.revokeObjectURL(f.imageUrl);
      });
    };
  }, []);

  useEffect(() => {
    setActiveProposalQuantityInput(String(activeProposal?.quantity_suggested ?? 1));
  }, [activeProposal?.id, activeProposal?.quantity_suggested]);

  useEffect(() => {
    if (!activeFrame) {
      setActiveImageBounds(null);
      return;
    }

    const onResize = () => recalculateActiveImageBounds();
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [activeFrame?.image.id]);

  const timezoneSelectOptions = useMemo(() => {
    const set = new Set<string>(timezoneOptions);
    set.add("UTC");
    if (selectedTimezone) set.add(selectedTimezone);
    if (user?.timezone) set.add(user.timezone);
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [timezoneOptions, selectedTimezone, user?.timezone]);

  const inventoryGroups = useMemo(() => {
    const grouped = new Map<string, InventoryItem[]>();
    inventory.forEach((item) => {
      const key = item.category || "Other";
      const current = grouped.get(key) || [];
      current.push(item);
      grouped.set(key, current);
    });

    return Array.from(grouped.entries())
      .sort((a, b) => {
        const aIndex = CATEGORY_OPTIONS.findIndex((option) => option.value === a[0]);
        const bIndex = CATEGORY_OPTIONS.findIndex((option) => option.value === b[0]);
        return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
      })
      .map(([category, items]) => ({
        category,
        items: items.sort((a, b) => a.name.localeCompare(b.name)),
      }));
  }, [inventory]);

  const visibleInventoryGroups = useMemo(() => {
    if (inventoryFilter === "All") return inventoryGroups;
    return inventoryGroups.filter((group) => group.category === inventoryFilter);
  }, [inventoryFilter, inventoryGroups]);

  const perishableCount = inventory.filter((item) => item.is_perishable).length;
  const pendingProposalCount = reviewFrames.reduce(
    (count, frame) => count + frame.proposals.filter((proposal) => proposal.state === "pending").length,
    0
  );

  function showNotice(section: NoticeSection, tone: NoticeTone, text: string) {
    setNotice({ section, tone, text });
  }

  function clearNotice(section?: NoticeSection) {
    setNotice((prev) => {
      if (!prev) return prev;
      if (!section || prev.section === section) return null;
      return prev;
    });
  }

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

  async function loginWithCredentials(
    emailValue: string,
    passwordValue: string,
    successMessage = "Logged in."
  ): Promise<boolean> {
    const body = new URLSearchParams();
    body.set("username", emailValue);
    body.set("password", passwordValue);

    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) {
      showNotice("auth", "error", await parseError(res));
      return false;
    }
    const data = await res.json();
    setSessionToken(data.access_token);
    setAuthMode("login");
    showNotice("auth", "success", successMessage);
    return true;
  }

  async function register() {
    clearNotice("auth");
    const emailValue = email.trim();
    const displayNameValue = displayName.trim();
    const passwordValue = password;
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: emailValue,
        display_name: displayNameValue,
        password: passwordValue,
      }),
    });
    if (!res.ok) {
      showNotice("auth", "error", await parseError(res));
      return;
    }

    const loggedIn = await loginWithCredentials(
      emailValue,
      passwordValue,
      "Registered successfully and logged in."
    );
    if (!loggedIn) {
      showNotice("auth", "info", "Registered successfully, but automatic login failed. Please log in manually.");
    }
  }

  async function login() {
    clearNotice("auth");
    await loginWithCredentials(email.trim(), password);
  }

  async function loadCurrentUser() {
    const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
    if (!res.ok) {
      clearSessionToken();
      handleSessionExpired();
      return;
    }
    const data = await res.json();
    const userData = {
      id: data.id,
      email: data.email,
      display_name: data.display_name,
      timezone: data.timezone || "UTC",
    };
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
      showNotice("auth", "error", await parseError(res));
      return;
    }

    const data = await res.json();
    setUser({
      id: data.id,
      email: data.email,
      display_name: data.display_name,
      timezone: data.timezone || "UTC",
    });
    showNotice("auth", "success", `Timezone set to ${data.timezone}`);
  }

  function clearReviewState() {
    replaceReviewFrames([]);
    setActiveImageIndex(0);
    setActiveProposalIndex(0);
    setManualPointMode(false);
    setManualLabelHint("");
    setPendingManualPoint(null);
    setCameraWorkspaceOpen(false);
  }

  function stopCameraStream() {
    const stream = cameraStreamRef.current;
    if (!stream) return;
    stream.getTracks().forEach((track) => track.stop());
    cameraStreamRef.current = null;
  }

  function logout() {
    clearSessionToken();
    setUser(null);
    setDisplayName("");
    setInventory([]);
    setEmail("");
    setPassword("");
    setAuthMode("login");
    showNotice("auth", "info", "Logged out.");
    clearReviewState();
  }

  async function loadInventory() {
    const res = await fetch(`${API_BASE}/inventory`, { headers: authHeaders() });
    if (!res.ok) {
      showNotice("inventory", "error", await parseError(res));
      return;
    }
    const data = await res.json();
    setInventory(data);
  }

  async function addItem() {
    if (!token) {
      showNotice("inventory", "error", "Log in first.");
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
      showNotice("inventory", "error", await parseError(res));
      return;
    }
    setItemName("");
    setItemQty("1");
    setItemUnit(UNIT_OPTIONS[0].value);
    setItemCategory(CATEGORY_OPTIONS[0].value);
    setItemPerishable(false);
    setShowQuickAdd(false);
    await loadInventory();
    showNotice("inventory", "success", "Item added to pantry.");
  }

  function beginEditItem(item: InventoryItem) {
    setEditingItemId(item.id);
    setInventoryDraft({
      name: item.name,
      quantity: String(item.quantity),
      unit: item.unit,
      category: item.category || "Other",
      is_perishable: item.is_perishable,
      refreshCreatedAt: false,
    });
  }

  function cancelEditItem() {
    setEditingItemId(null);
    setInventoryDraft(null);
  }

  async function saveItemEdits(item: InventoryItem) {
    if (!inventoryDraft) return;
    const parsedQuantity = Number(inventoryDraft.quantity);
    const quantity = Number.isFinite(parsedQuantity) && parsedQuantity > 0 ? parsedQuantity : item.quantity;

    const res = await fetch(`${API_BASE}/inventory/${item.id}`, {
      method: "PATCH",
      headers: authHeaders("application/json"),
      body: JSON.stringify({
        name: inventoryDraft.name.trim() || item.name,
        quantity,
        unit: inventoryDraft.unit,
        category: inventoryDraft.category || null,
        is_perishable: inventoryDraft.is_perishable,
        refresh_created_at: inventoryDraft.refreshCreatedAt,
      }),
    });
    if (!res.ok) {
      showNotice("inventory", "error", await parseError(res));
      return;
    }
    cancelEditItem();
    await loadInventory();
    showNotice("inventory", "success", "Inventory item updated.");
  }

  async function deleteItem(itemId: number) {
    const res = await fetch(`${API_BASE}/inventory/${itemId}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (!res.ok) {
      showNotice("inventory", "error", await parseError(res));
      return;
    }
    await loadInventory();
    showNotice("inventory", "success", "Inventory item removed.");
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

  function replaceReviewFrames(nextFrames: ReviewFrame[]) {
    setReviewFrames((prev) => {
      prev.forEach((frame) => {
        if (frame.imageUrl.startsWith("blob:")) {
          URL.revokeObjectURL(frame.imageUrl);
        }
      });
      return nextFrames;
    });
  }

  async function fetchDetectionProposals(
    sessionId: number,
    mode: ReviewMode = reviewMode
  ): Promise<DetectionProposal[]> {
    const detectionRes = await fetch(`${API_BASE}/detections/${sessionId}?view=${mode}`, {
      headers: authHeaders(),
    });
    if (!detectionRes.ok) {
      throw new Error(`Detection session ${sessionId} could not be loaded`);
    }
    const detail = (await detectionRes.json()) as {
      proposals: DetectionProposal[];
    };
    return detail.proposals;
  }

  function openReviewFrame(frameIndex: number) {
    const frame = reviewFrames[frameIndex];
    if (!frame) return;
    setActiveImageIndex(frameIndex);
    const nextPendingIndex = frame.proposals.findIndex((proposal) => proposal.state === "pending");
    setActiveProposalIndex(nextPendingIndex >= 0 ? nextPendingIndex : 0);
    setCameraWorkspaceOpen(true);
  }

  async function loadRecentUploads(openWorkspace = false, preferredImageIds: number[] = []) {
    if (!token) return;

    const res = await fetch(`${API_BASE}/images`, { headers: authHeaders() });
    if (!res.ok) {
      showNotice("camera", "error", await parseError(res));
      return;
    }

    const payload = (await res.json()) as { results: ImageRecord[] };
    const rows = payload.results.filter((row) => row.detection_session_id).slice(0, 8);
    const frames = await Promise.all(
      rows.map(async (row) => ({
        image: row,
        sessionId: row.detection_session_id as number,
        imageUrl: await fetchImageObjectUrl(row.id),
        proposals: await fetchDetectionProposals(row.detection_session_id as number, reviewMode),
      }))
    );

    const currentImageId = reviewFrames[activeImageIndex]?.image.id;
    replaceReviewFrames(frames);

    if (frames.length === 0) {
      setCameraWorkspaceOpen(false);
      setActiveImageIndex(0);
      setActiveProposalIndex(0);
      return;
    }

    const preferredIndex =
      preferredImageIds.length > 0
        ? frames.findIndex(
            (frame) =>
              preferredImageIds.includes(frame.image.id) &&
              frame.proposals.some((proposal) => proposal.state === "pending")
          )
        : -1;
    const preferredFallbackIndex =
      preferredIndex >= 0 || preferredImageIds.length === 0
        ? -1
        : frames.findIndex((frame) => preferredImageIds.includes(frame.image.id));
    const preservedIndex =
      preferredImageIds.length === 0 && currentImageId
        ? frames.findIndex((frame) => frame.image.id === currentImageId)
        : -1;
    const nextIndex =
      preferredIndex >= 0
        ? preferredIndex
        : preferredFallbackIndex >= 0
          ? preferredFallbackIndex
          : preservedIndex >= 0
            ? preservedIndex
            : 0;
    setActiveImageIndex(nextIndex);
    const nextPendingIndex = frames[nextIndex].proposals.findIndex((proposal) => proposal.state === "pending");
    setActiveProposalIndex(nextPendingIndex >= 0 ? nextPendingIndex : 0);
    setCameraWorkspaceOpen(openWorkspace);
  }

  async function uploadAndAnalyze() {
    if (!token) {
      showNotice("camera", "error", "Log in first.");
      return;
    }
    if (pickedFiles.length === 0) {
      showNotice("camera", "error", "Pick at least one image first.");
      return;
    }

    const form = new FormData();
    pickedFiles.forEach((entry) => form.append("files", entry.file));

    setUploading(true);
    showNotice("camera", "info", "Uploading photos and running detection...");

    const res = await fetch(`${API_BASE}/images`, {
      method: "POST",
      headers: authHeaders(),
      body: form,
    });

    if (!res.ok) {
      setUploading(false);
      showNotice("camera", "error", await parseError(res));
      return;
    }

    const uploadPayload = (await res.json()) as {
      results: Array<{
        image: { id: number };
      }>;
    };

    try {
      clearReviewState();
      setPickedFiles((prev) => {
        prev.forEach((f) => URL.revokeObjectURL(f.previewUrl));
        return [];
      });
      await loadRecentUploads(
        true,
        uploadPayload.results.map((row) => row.image.id)
      );
      showNotice("camera", "success", "Detection ready. Review each proposal before saving anything.");
      cameraSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      showNotice("camera", "error", e instanceof Error ? e.message : "Failed to load detection proposals");
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

  function handleActiveProposalQuantityChange(rawValue: string) {
    setActiveProposalQuantityInput(rawValue);
    if (rawValue.trim() === "") return;

    const parsedValue = Number(rawValue);
    if (Number.isNaN(parsedValue)) return;

    updateActiveProposal({ quantity_suggested: parsedValue });
  }

  function commitActiveProposalQuantity() {
    const parsedValue = Number(activeProposalQuantityInput);
    const nextValue =
      activeProposalQuantityInput.trim() === "" || Number.isNaN(parsedValue) ? 1 : parsedValue;

    setActiveProposalQuantityInput(String(nextValue));
    updateActiveProposal({ quantity_suggested: nextValue });
  }

  function markActiveProposalState(nextState: string): ReviewFrame[] {
    let nextFrames: ReviewFrame[] = reviewFrames;
    setReviewFrames((prev) => {
      nextFrames = prev.map((frame, frameIndex) => {
        if (frameIndex !== activeImageIndex) return frame;
        const proposals = frame.proposals.map((proposal, proposalIndex) =>
          proposalIndex === activeProposalIndex ? { ...proposal, state: nextState } : proposal
        );
        return { ...frame, proposals };
      });
      return nextFrames;
    });
    return nextFrames;
  }

  function moveToNextProposal(framesOverride: ReviewFrame[] = reviewFrames) {
    const nextPosition = findNextPendingPosition(framesOverride, activeImageIndex, activeProposalIndex);
    if (!nextPosition) {
      setCameraWorkspaceOpen(false);
      showNotice("camera", "success", "Review complete for the current uploads.");
      return;
    }

    setActiveImageIndex(nextPosition.imageIndex);
    setActiveProposalIndex(nextPosition.proposalIndex);
  }

  async function confirmActiveProposal(
    action: "add_new" | "update_existing" | "reject",
    targetItemId?: number
  ): Promise<boolean> {
    if (!activeFrame || !activeProposal) return false;
    const res = await fetch(`${API_BASE}/detections/${activeFrame.sessionId}/confirm`, {
      method: "POST",
      headers: authHeaders("application/json"),
      body: JSON.stringify({
        actions: [
          {
            proposal_id: activeProposal.id,
            action,
            target_item_id: targetItemId,
            apply_grouped_label: reviewMode === "grouped",
            name: activeProposal.label_raw,
            quantity: activeProposal.quantity_suggested ?? 1,
            unit: activeProposal.quantity_unit || "count",
            category: activeProposal.category_suggested || "Other",
            is_perishable: Boolean(activeProposal.is_perishable_suggested),
          },
        ],
      }),
    });
    if (!res.ok) {
      showNotice("camera", "error", await parseError(res));
      return false;
    }
    const nextState =
      action === "reject" ? "skipped" : action === "update_existing" ? "updated" : "added";
    const nextFrames = markActiveProposalState(nextState);
    moveToNextProposal(nextFrames);
    return true;
  }

  async function addProposalToInventory() {
    if (!activeProposal) return;
    const persisted = await confirmActiveProposal("add_new");
    if (!persisted) return;

    await loadInventory();
  }

  async function updateMatchingInventory() {
    if (!activeProposal || !activeInventoryMatch) {
      showNotice("camera", "error", "No matching inventory item found for update.");
      return;
    }
    const persisted = await confirmActiveProposal("update_existing", activeInventoryMatch.id);
    if (!persisted) return;

    await loadInventory();
  }

  async function manualAddFromCurrentImage() {
    if (!activeFrame) return;
    setManualPointMode(true);
    setPendingManualPoint(null);
    setManualLabelHint("");
    showNotice("camera", "info", "Click the image where the missed item appears, then add a short hint to create a proposal.");
  }

  async function handleImageClick(event: MouseEvent<HTMLImageElement>) {
    if (!manualPointMode || !activeFrame) return;

    const rect = event.currentTarget.getBoundingClientRect();
    const bounds = activeImageBounds || { left: 0, top: 0, width: rect.width, height: rect.height };
    const clickX = event.clientX - rect.left;
    const clickY = event.clientY - rect.top;
    const x = (clickX - bounds.left) / bounds.width;
    const y = (clickY - bounds.top) / bounds.height;
    if (x < 0 || x > 1 || y < 0 || y > 1) {
      showNotice("camera", "error", "Click inside the visible photo area to add a missed item.");
      return;
    }
    setPendingManualPoint({ x, y });
    showNotice("camera", "info", "Point saved. Add a short hint below so SmartPantry knows what to look for.");
  }

  async function submitManualProposal() {
    if (!activeFrame || !pendingManualPoint) return;

    const res = await fetch(`${API_BASE}/detections/${activeFrame.sessionId}/manual-proposals`, {
      method: "POST",
      headers: authHeaders("application/json"),
      body: JSON.stringify({
        x: pendingManualPoint.x,
        y: pendingManualPoint.y,
        w: 0.22,
        h: 0.22,
        label_hint: manualLabelHint.trim() || undefined,
      }),
    });
    if (!res.ok) {
      showNotice("camera", "error", await parseError(res));
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
    setPendingManualPoint(null);
    setManualLabelHint("");
    showNotice("camera", "success", "Manual proposal added. Review it just like any other suggestion.");
  }

  async function changeReviewMode(mode: ReviewMode) {
    setReviewMode(mode);
    if (reviewFrames.length === 0) return;
    try {
      const refreshed = await Promise.all(
        reviewFrames.map(async (frame) => ({
          ...frame,
          proposals: await fetchDetectionProposals(frame.sessionId, mode),
        }))
      );
      setReviewFrames(refreshed);
      setActiveProposalIndex(0);
      showNotice("camera", "info", `Switched review mode to ${mode === "grouped" ? "Grouped" : "Per-box"}.`);
    } catch (e) {
      showNotice("camera", "error", e instanceof Error ? e.message : "Failed to switch review mode");
    }
  }

  async function findRecipes() {
    await findRecipesPage(1);
  }

  async function findRecipesPage(page: number) {
    if (!token) {
      showNotice("recipes", "error", "Log in first.");
      return;
    }

    const params = new URLSearchParams();
    if (recipeMainIngredients.trim()) params.set("main_ingredients", recipeMainIngredients.trim());
    if (recipeMaxTotalMinutes.trim()) params.set("max_total_minutes", recipeMaxTotalMinutes.trim());
    params.set("page", String(page));
    params.set("page_size", String(recipePageSize));

    setRecipesLoading(true);
    const res = await fetch(`${API_BASE}/recipes/recommendations?${params.toString()}`, {
      headers: authHeaders(),
    });
    if (!res.ok) {
      setRecipesLoading(false);
      showNotice("recipes", "error", await parseError(res));
      return;
    }

    const payload = (await res.json()) as RecipeRecommendationResponse;
    setRecipeResults(payload.results);
    setRecipePage(payload.page);
    setRecipeTotalPages(payload.total_pages);
    setRecipeTotalResults(payload.total_results);
    setRecipesLoading(false);
    showNotice(
      "recipes",
      payload.total_results > 0 ? "success" : "info",
      payload.total_results > 0
        ? `Loaded page ${payload.page} of ${Math.max(payload.total_pages, 1)} recipe recommendations.`
        : "No recipe matches found for the current inventory and filters."
    );
  }

  async function submitRecipeFeedback(recipeId: number, feedbackType: "like" | "dislike") {
    if (!token) {
      showNotice("recipes", "error", "Log in first.");
      return;
    }

    const currentFeedback = recipeResults.find((result) => result.recipe.id === recipeId)?.recipe.current_feedback;
    if (feedbackType === "like" && currentFeedback === "like") {
      const deleteRes = await fetch(`${API_BASE}/recipes/${recipeId}/feedback`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!deleteRes.ok) {
        showNotice("recipes", "error", await parseError(deleteRes));
        return;
      }
      setRecipeResults((prev) =>
        prev.map((result) =>
          result.recipe.id === recipeId
            ? { ...result, recipe: { ...result.recipe, current_feedback: null } }
          : result
        )
      );
      showNotice("recipes", "success", "Recipe removed from Favorites.");
      return;
    }

    const res = await fetch(`${API_BASE}/recipes/${recipeId}/feedback`, {
      method: "POST",
      headers: authHeaders("application/json"),
      body: JSON.stringify({ feedback_type: feedbackType }),
    });
    if (!res.ok) {
      showNotice("recipes", "error", await parseError(res));
      return;
    }

    if (feedbackType === "dislike") {
      const nextTotalResults = Math.max(0, recipeTotalResults - 1);
      const nextTotalPages = nextTotalResults > 0 ? Math.ceil(nextTotalResults / recipePageSize) : 0;
      const nextPage = nextTotalPages > 0 ? Math.min(recipePage, nextTotalPages) : 1;
      await findRecipesPage(nextPage);
      showNotice("recipes", "success", "Recipe disliked. It will be excluded from future recommendations.");
      return;
    }

    setRecipeResults((prev) =>
      prev.map((result) =>
        result.recipe.id === recipeId
          ? {
              ...result,
              recipe: { ...result.recipe, current_feedback: feedbackType },
            }
          : result
      )
    );
    showNotice("recipes", "success", "Recipe saved to your Favorites.");
  }

  function renderRecipePagination() {
    if (recipeTotalPages <= 1) return null;

    const pages = getVisiblePageNumbers(recipePage, recipeTotalPages);
    return (
      <div className="recipe-pagination">
        <button onClick={() => void findRecipesPage(recipePage - 1)} disabled={recipePage <= 1 || recipesLoading}>
          &lt;
        </button>
        {pages.map((pageNumber, index) => [
          index > 0 && pageNumber - pages[index - 1] > 1 ? (
            <span key={`gap-${pages[index - 1]}-${pageNumber}`} className="pagination-ellipsis">
              ...
            </span>
          ) : null,
          <button
            key={pageNumber}
            className={pageNumber === recipePage ? "pagination-button-active" : undefined}
            onClick={() => void findRecipesPage(pageNumber)}
            disabled={recipesLoading}
          >
            {pageNumber}
          </button>,
        ])}
        <button
          onClick={() => void findRecipesPage(recipePage + 1)}
          disabled={recipePage >= recipeTotalPages || recipesLoading}
        >
          &gt;
        </button>
      </div>
    );
  }

  function renderSectionNotice(section: NoticeSection) {
    if (!notice || notice.section !== section) return null;

    return (
      <div className={`app-alert app-alert-${notice.tone}`}>
        <p>{notice.text}</p>
      </div>
    );
  }

  const activeBox =
    activeImageBounds &&
    activeProposal &&
    activeProposal.bbox_x !== null &&
    activeProposal.bbox_y !== null &&
    activeProposal.bbox_w !== null &&
    activeProposal.bbox_h !== null
      ? {
          left: `${(activeImageBounds?.left || 0) + Math.max(0, activeProposal.bbox_x || 0) * (activeImageBounds?.width || 0)}px`,
          top: `${(activeImageBounds?.top || 0) + Math.max(0, activeProposal.bbox_y || 0) * (activeImageBounds?.height || 0)}px`,
          width: `${Math.min(1, activeProposal.bbox_w || 0) * (activeImageBounds?.width || 0)}px`,
          height: `${Math.min(1, activeProposal.bbox_h || 0) * (activeImageBounds?.height || 0)}px`,
        }
      : null;

  return (
    <main className="app-wrap">
      <section className="shell">
        <div className="hero-row">
          <div className="hero-copy">
            <div className="brand-lockup">
              <span className="brand-badge" aria-hidden="true" />
              <div>
                <p className="eyebrow">AI-assisted pantry helper</p>
                <h1 className="title">SmartPantry</h1>
              </div>
            </div>
            <p className="subtitle">
              Keep track of your kitchen in one place. Add and update items faster with AI-assisted photo review, then find recipes from what is already in your inventory.
            </p>
          </div>

          <div className="header-actions">
            {user && (
              <div className="welcome-chip">
                <span className="welcome-label">Hi {user.display_name}!</span>
                <Link href="/account" className="header-link-chip">
                  Account
                </Link>
                <Link href="/recipes/book" className="header-link-chip">
                  Favorites
                </Link>
                <button onClick={logout}>Log out</button>
              </div>
            )}

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
        </div>

        {!token && (
          <div className="card card-accent">
            <div className="section-heading">
              <div>
                <p className="eyebrow">{authMode === "login" ? "Welcome back" : "Get started"}</p>
                <h2>{authMode === "login" ? "Sign in" : "Create your account"}</h2>
              </div>
            </div>
            <div className="auth-mode-toggle">
              <button
                className={authMode === "login" ? "auth-mode-active" : undefined}
                onClick={() => setAuthMode("login")}
              >
                Login
              </button>
              <button
                className={authMode === "register" ? "auth-mode-active" : undefined}
                onClick={() => setAuthMode("register")}
              >
                Register
              </button>
            </div>
            <div className="auth-row">
              {authMode === "register" && (
                <input
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="How should I call you?"
                />
              )}
              <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
              <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                type="password"
              />
              {authMode === "register" ? (
                <button onClick={() => void register()}>Register</button>
              ) : (
                <button onClick={() => void login()}>Login</button>
              )}
            </div>
            <p className="muted-text">
              {authMode === "register"
                ? "Create an account to save pantry items, review photo suggestions, and keep your favorite recipes handy."
                : "Sign in to jump back into your pantry, photo review, and favorite recipes."}
            </p>
            {renderSectionNotice("auth")}
          </div>
        )}

        {token && renderSectionNotice("auth")}
        {error && (
          <div className="card card-soft status-banner">
            <div className="app-alert app-alert-error">
              <p>Backend unreachable: {error}</p>
            </div>
          </div>
        )}

        <section className="card inventory-card">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Pantry notebook</p>
                <h2>Inventory</h2>
              </div>
              <span className="section-chip">{inventory.length} item{inventory.length === 1 ? "" : "s"}</span>
            </div>
            <div className="inventory-summary-row">
              <div className="summary-pill">
                <span className="summary-pill-icon">🧺</span>
                <div>
                  <strong>{inventoryGroups.length || 0}</strong>
                  <p>categories stocked</p>
                </div>
              </div>
              <div className="summary-pill">
                <span className="summary-pill-icon">🥬</span>
                <div>
                  <strong>{perishableCount}</strong>
                  <p>perishable items</p>
                </div>
              </div>
              <div className="summary-pill">
                <span className="summary-pill-icon">🕒</span>
                <div>
                  <strong>{inventory.length ? "Freshly updated" : "Ready when you are"}</strong>
                  <p>edit or refill any item inline</p>
                </div>
              </div>
            </div>

            <div className="inventory-add-strip">
              <article className="inventory-action-card">
                <div>
                  <p className="eyebrow">Quick add</p>
                  <h3>Add one item by hand</h3>
                  <p className="muted-text">
                    Best when you already know the item and just want to drop it into your pantry fast.
                  </p>
                </div>
                <button className="secondary-button" onClick={() => setShowQuickAdd((prev) => !prev)}>
                  {showQuickAdd ? "Hide fields" : "Open Quick Add"}
                </button>
              </article>

              <article className="inventory-action-card inventory-action-card-smart">
                <div>
                  <p className="eyebrow">Smart add</p>
                  <h3>Let the camera draft it</h3>
                  <p className="muted-text">
                    Snap or upload a shelf photo and let SmartPantry suggest items before you confirm anything.
                  </p>
                </div>
                <button
                  className="secondary-button"
                  onClick={() => cameraSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
                >
                  Go to Camera Counter
                </button>
              </article>
            </div>

            {renderSectionNotice("inventory")}

            {showQuickAdd && (
              <div className="inventory-add-card">
                <div className="inventory-add-grid">
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
                  <label className="checkbox-label inventory-toggle">
                    <input
                      type="checkbox"
                      checked={itemPerishable}
                      onChange={(e) => setItemPerishable(e.target.checked)}
                    />
                    Mark as perishable
                  </label>
                  <button onClick={() => void addItem()}>Add to Pantry</button>
                </div>
              </div>
            )}

            <div className="inventory-filter-header">
              <h3>Browse by category</h3>
              <button
                className="secondary-button"
                onClick={() => setShowInventoryCategories((prev) => !prev)}
              >
                {showInventoryCategories ? "Hide tabs" : "Show tabs"}
              </button>
            </div>
            {showInventoryCategories && (
              <div className="category-tabs">
                <button
                  className={inventoryFilter === "All" ? "category-tab-active" : undefined}
                  onClick={() => setInventoryFilter("All")}
                >
                  All
                  <span>{inventory.length}</span>
                </button>
                {inventoryGroups.map((group) => {
                  const meta = getCategoryMeta(group.category);
                  return (
                    <button
                      key={group.category}
                      className={inventoryFilter === group.category ? "category-tab-active" : undefined}
                      onClick={() => setInventoryFilter(group.category)}
                    >
                      <span aria-hidden="true">{meta.icon}</span>
                      {meta.label}
                      <span>{group.items.length}</span>
                    </button>
                  );
                })}
              </div>
            )}

            <div className="inventory-groups">
              {visibleInventoryGroups.map((group) => {
                const meta = getCategoryMeta(group.category);
                return (
                  <section key={group.category} className={`inventory-group inventory-group-${meta.accent}`}>
                    <div className="inventory-group-heading">
                      <div className="inventory-group-title">
                        <span className="inventory-group-icon" aria-hidden="true">
                          {meta.icon}
                        </span>
                        <div>
                          <h3>{meta.label}</h3>
                          <p className="tiny-text">{group.items.length} item{group.items.length === 1 ? "" : "s"}</p>
                        </div>
                      </div>
                    </div>

                    <div className="inventory-item-grid">
                      {group.items.map((item) => {
                        const isEditing = editingItemId === item.id && inventoryDraft;
                        return (
                          <article key={item.id} className="inventory-item-card">
                            <div className="inventory-item-topline">
                              <div>
                                <p className="tiny-text inventory-item-category">{meta.label}</p>
                                <h4>{item.name}</h4>
                              </div>
                              {item.is_perishable && <span className="inventory-badge inventory-badge-perishable">Use sooner</span>}
                            </div>

                            {!isEditing ? (
                              <div className="inventory-item-row">
                                <div className="inventory-item-metrics inventory-item-metrics-compact">
                                  <div>
                                    <span className="tiny-text">Amount</span>
                                    <strong>
                                      {item.quantity} {item.unit}
                                    </strong>
                                  </div>
                                  <div>
                                    <span className="tiny-text">Added</span>
                                    <strong>{formatInventoryDate(item.created_at, displayTimezone)}</strong>
                                  </div>
                                  <div>
                                    <span className="tiny-text">Updated</span>
                                    <strong>{formatInventoryDate(item.last_updated, displayTimezone)}</strong>
                                  </div>
                                </div>
                                <div className="inventory-item-actions">
                                  <button onClick={() => beginEditItem(item)}>Edit</button>
                                  <button onClick={() => void deleteItem(item.id)}>Delete</button>
                                </div>
                              </div>
                            ) : (
                              <div className="inventory-edit-panel">
                                <div className="inventory-edit-grid">
                                  <input
                                    value={inventoryDraft.name}
                                    onChange={(e) =>
                                      setInventoryDraft((prev) =>
                                        prev ? { ...prev, name: e.target.value } : prev
                                      )
                                    }
                                    placeholder="Item name"
                                  />
                                  <input
                                    type="number"
                                    step="0.1"
                                    value={inventoryDraft.quantity}
                                    onChange={(e) =>
                                      setInventoryDraft((prev) =>
                                        prev ? { ...prev, quantity: e.target.value } : prev
                                      )
                                    }
                                    placeholder="Qty"
                                  />
                                  <select
                                    value={inventoryDraft.unit}
                                    onChange={(e) =>
                                      setInventoryDraft((prev) =>
                                        prev ? { ...prev, unit: e.target.value } : prev
                                      )
                                    }
                                  >
                                    {UNIT_OPTIONS.map((u) => (
                                      <option key={u.value} value={u.value}>
                                        {u.label}
                                      </option>
                                    ))}
                                  </select>
                                  <select
                                    value={inventoryDraft.category}
                                    onChange={(e) =>
                                      setInventoryDraft((prev) =>
                                        prev ? { ...prev, category: e.target.value } : prev
                                      )
                                    }
                                  >
                                    {CATEGORY_OPTIONS.map((c) => (
                                      <option key={c.value} value={c.value}>
                                        {c.label}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                                <div className="inventory-edit-options">
                                  <label className="checkbox-label">
                                    <input
                                      type="checkbox"
                                      checked={inventoryDraft.is_perishable}
                                      onChange={(e) =>
                                        setInventoryDraft((prev) =>
                                          prev ? { ...prev, is_perishable: e.target.checked } : prev
                                        )
                                      }
                                    />
                                    Perishable
                                  </label>
                                  <label className="checkbox-label">
                                    <input
                                      type="checkbox"
                                      checked={inventoryDraft.refreshCreatedAt}
                                      onChange={(e) =>
                                        setInventoryDraft((prev) =>
                                          prev ? { ...prev, refreshCreatedAt: e.target.checked } : prev
                                        )
                                      }
                                    />
                                    Refresh date added to now
                                  </label>
                                </div>
                                <div className="inventory-item-actions">
                                  <button onClick={() => void saveItemEdits(item)}>Save changes</button>
                                  <button onClick={cancelEditItem}>Cancel</button>
                                </div>
                              </div>
                            )}
                          </article>
                        );
                      })}
                    </div>
                  </section>
                );
              })}

              {inventory.length === 0 && (
                <div className="inventory-empty card-soft">
                  <h3>Your pantry starts here</h3>
                  <p className="muted-text">
                    Add a few staples by hand or let the AI-assisted camera counter do the first pass for you.
                  </p>
                </div>
              )}
            </div>
          </section>

        <section className="card capture-card" ref={cameraSectionRef}>
            <div className="section-heading">
              <div>
                <p className="eyebrow">Camera counter</p>
                <h2>AI-assisted Capture</h2>
              </div>
              <span className="section-chip">{pendingProposalCount} proposal{pendingProposalCount === 1 ? "" : "s"} waiting</span>
            </div>
            <p className="muted-text">
              Too lazy to track your fridge by hand? Share a few photos and let SmartPantry draft the first pass. Nothing gets added until you review it.
            </p>
            <p className="tiny-text">
              Smart Add is the quickest route here: snap or upload a shelf photo, let the AI suggest what it sees, then confirm only the items you want saved.
            </p>

            {renderSectionNotice("camera")}

            <div className="capture-overview capture-overview-compact">
              <div className="capture-mode-card">
                <div>
                  <h3>Review style</h3>
                  <p className="tiny-text">
                    Grouped keeps similar detections together. Per-box lets you inspect every single box one by one.
                  </p>
                </div>
                <div className="auth-mode-toggle review-mode-toggle">
                  <button
                    className={reviewMode === "grouped" ? "auth-mode-active" : undefined}
                    onClick={() => void changeReviewMode("grouped")}
                  >
                    Grouped
                  </button>
                  <button
                    className={reviewMode === "boxes" ? "auth-mode-active" : undefined}
                    onClick={() => void changeReviewMode("boxes")}
                  >
                    Per-box
                  </button>
                </div>
              </div>
              <div className="capture-actions">
                <button onClick={() => void openCamera()}>Take Photo</button>
                <button onClick={() => libraryInputRef.current?.click()}>Upload From Device</button>
                <button onClick={() => void uploadAndAnalyze()} disabled={uploading || pickedFiles.length === 0}>
                  {uploading ? "Uploading..." : "Analyze Photos"}
                </button>
              </div>
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
            </div>

            {pickedFiles.length > 0 && (
              <div className="preview-grid upload-preview-grid">
                {pickedFiles.map((entry) => (
                  <figure key={entry.key} className="preview-card">
                    <img src={entry.previewUrl} alt={entry.file.name} />
                    <figcaption>{entry.file.name}</figcaption>
                    <button onClick={() => removePickedFile(entry.key)}>Remove photo</button>
                  </figure>
                ))}
              </div>
            )}

            {cameraError && <p className="tiny-text">{cameraError}</p>}

            <div className="recent-uploads-card">
              <div className="section-heading">
                <div>
                  <h3>Recent uploads</h3>
                  <p className="tiny-text">
                    Your latest photo history stays here for 7 days. Open any card when you want to review or revisit it.
                  </p>
                </div>
                <span className="section-chip">Showing {reviewFrames.length} photo{reviewFrames.length === 1 ? "" : "s"}</span>
              </div>

              {reviewFrames.length > 0 ? (
                <div className="review-thumb-strip review-thumb-grid">
                  {reviewFrames.map((frame, frameIndex) => {
                    const pendingCount = frame.proposals.filter((proposal) => proposal.state === "pending").length;
                    return (
                      <button
                        key={frame.image.id}
                        className={`review-thumb ${frameIndex === activeImageIndex && cameraWorkspaceOpen ? "review-thumb-active" : ""}`}
                        onClick={() => openReviewFrame(frameIndex)}
                      >
                        <img src={frame.imageUrl} alt={frame.image.original_filename} />
                        <div>
                          <strong>Photo {frameIndex + 1}</strong>
                          <p>{pendingCount} pending</p>
                          <p className="tiny-text">{formatInventoryDate(frame.image.created_at, displayTimezone)}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <p className="muted-text">
                  No recent uploads yet. Use Smart Add, Take Photo, or Upload From Device to let the AI help with your pantry.
                </p>
              )}
            </div>

            {cameraWorkspaceOpen && activeFrame ? (
              <div className="review-workspace">
                <div className="review-sidebar">
                  <div className="review-sidebar-card">
                    <h3>Proposal queue</h3>
                    <div className="proposal-list">
                      {activeFrame.proposals.map((proposal, proposalIndex) => (
                        <button
                          key={proposal.id}
                          className={`proposal-list-item proposal-state-${proposal.state} ${proposalIndex === activeProposalIndex ? "proposal-list-item-active" : ""}`}
                          onClick={() => setActiveProposalIndex(proposalIndex)}
                        >
                          <span>{proposal.label_raw}</span>
                          <strong>{getProposalStateLabel(proposal.state)}</strong>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="review-stage-panel">
                  <div className="image-stage">
                    <img
                      ref={activeImageRef}
                      src={activeFrame.imageUrl}
                      alt={activeFrame.image.original_filename}
                      onLoad={() => recalculateActiveImageBounds()}
                      onClick={(e) => void handleImageClick(e)}
                    />
                    {activeBox && <div className="bbox" style={activeBox} />}
                  </div>
                  <div className="review-stage-caption">
                    <p className="tiny-text">
                      Photo {activeImageIndex + 1}/{reviewFrames.length} · {activeFrame.image.original_filename}
                    </p>
                    {manualPointMode && (
                      <p className="tiny-text">
                        Tap the photo where the missing item appears, then add a quick hint below.
                      </p>
                    )}
                  </div>

                  {manualPointMode && (
                    <div className="manual-hint-card">
                      <div>
                        <h3>Add a missed item</h3>
                        <p className="tiny-text">
                          After you click the image, add a short hint like “milk” or “tomatoes” so we can create a new proposal for review.
                        </p>
                      </div>
                      <input
                        value={manualLabelHint}
                        onChange={(e) => setManualLabelHint(e.target.value)}
                        placeholder="Optional label hint"
                      />
                      <div className="manual-hint-chips">
                        {MANUAL_HINT_SUGGESTIONS.map((hint) => (
                          <button key={hint} onClick={() => setManualLabelHint(hint)}>
                            {hint}
                          </button>
                        ))}
                      </div>
                      <div className="row-gap">
                        <button onClick={() => void submitManualProposal()} disabled={!pendingManualPoint}>
                          Create proposal
                        </button>
                        <button
                          onClick={() => {
                            setManualPointMode(false);
                            setPendingManualPoint(null);
                            setManualLabelHint("");
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                <div className="proposal-panel proposal-panel-rich">
                  {activeProposal ? (
                    <>
                      <div className="proposal-panel-header">
                        <div>
                          <p className="tiny-text">Proposal {activeProposalIndex + 1}/{activeFrame.proposals.length}</p>
                          <h3>{activeProposal.label_raw}</h3>
                        </div>
                        <span className={`inventory-badge proposal-badge proposal-badge-${activeProposal.state}`}>
                          {getProposalStateLabel(activeProposal.state)}
                        </span>
                      </div>
                      <label>Detected label</label>
                      <input
                        value={activeProposal.label_raw}
                        onChange={(e) => updateActiveProposal({ label_raw: e.target.value })}
                      />

                      <label>Suggested quantity</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="1"
                        value={activeProposalQuantityInput}
                        onChange={(e) => handleActiveProposalQuantityChange(e.target.value)}
                        onBlur={commitActiveProposalQuantity}
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
                        <button onClick={() => void addProposalToInventory()}>Add as New</button>
                        <button onClick={() => void updateMatchingInventory()} disabled={!activeInventoryMatch}>
                          Update Existing
                        </button>
                        <button
                          onClick={() => void (async () => {
                            const persisted = await confirmActiveProposal("reject");
                            if (!persisted) return;
                          })()}
                        >
                          Skip
                        </button>
                        <button onClick={() => void manualAddFromCurrentImage()}>Add Missed Item</button>
                      </div>
                    </>
                  ) : (
                    <div className="proposal-empty">
                      <h3>This photo is all set</h3>
                      <p className="muted-text">
                        No pending proposal is selected for this image. You can review another photo or add a missed item manually.
                      </p>
                      <button onClick={() => void manualAddFromCurrentImage()}>Add Missed Item</button>
                    </div>
                  )}
                </div>
              </div>
            ) : reviewFrames.length > 0 ? (
              <div className="review-collapsed-note">
                <p className="muted-text">
                  {pendingProposalCount > 0
                    ? "Open a recent upload whenever you want to continue reviewing pending proposals."
                    : "Everything in the current photo history is reviewed. Open any recent upload if you want to revisit or adjust something."}
                </p>
              </div>
            ) : null}
          </section>

        <section className="card">
          <div className="hero-row">
            <div>
              <p className="eyebrow">Recipe corner</p>
              <h2>Find Recipes</h2>
              <p className="muted-text">
                Match recipes against your confirmed inventory and optional preferences.
              </p>
              <p className="tiny-text">
                After you cook, open any recipe detail page and use <strong>Update pantry</strong> to review ingredient-based inventory changes before applying them.
              </p>
            </div>
            <div className="row-gap">
              <Link href="/recipes/book">Favorite Recipes</Link>
              <button onClick={() => setShowRecipeFinder((prev) => !prev)}>
                {showRecipeFinder ? "Hide Filters" : "Find Recipe"}
              </button>
            </div>
          </div>

          {showRecipeFinder && (
            <div className="recipe-toolbar">
              <input
                value={recipeMainIngredients}
                onChange={(e) => setRecipeMainIngredients(e.target.value)}
                placeholder="Main ingredients (comma-separated)"
              />
              <input
                value={recipeMaxTotalMinutes}
                onChange={(e) => setRecipeMaxTotalMinutes(e.target.value)}
                type="number"
                min="1"
                step="1"
                placeholder="Max total minutes"
              />
              <button onClick={() => void findRecipes()} disabled={recipesLoading}>
                {recipesLoading ? "Loading..." : "Get Recommendations"}
              </button>
            </div>
          )}

          {showRecipeFinder && (
            <p className="tiny-text">
              Main ingredients are prioritized first in ranking, while all inventory-matched recipes stay in the result set.
            </p>
          )}

          <p className="tiny-text">
            Recipe discovery data courtesy of the MIT-licensed Kaggle All Recipe Dataset, derived from Allrecipes.com content.
          </p>

          {renderSectionNotice("recipes")}

          {recipeResults.length > 0 && (
            <>
              <p className="tiny-text">
                Showing page {recipePage} of {Math.max(recipeTotalPages, 1)} ({recipeTotalResults} total matches)
              </p>
              <div className="recipe-grid">
                {recipeResults.map((result) => (
                  <article
                    key={result.recipe.id}
                    className={`recipe-card ${result.recipe.current_feedback ? `recipe-card-${result.recipe.current_feedback}` : ""}`}
                  >
                    <RecipeCardImage src={result.recipe.image_url} alt={result.recipe.title} />

                    <div className="recipe-meta">
                      <div>
                        <h3>{result.recipe.title}</h3>
                        <p className="tiny-text">
                          {displayRecipeSourceName(result.recipe.source_name)}
                          {result.recipe.cuisine ? ` - ${result.recipe.cuisine}` : ""}
                        </p>
                      </div>
                      {typeof result.recipe.rating === "number" && (
                        <p className="tiny-text">Rating: {result.recipe.rating.toFixed(1)} / 5</p>
                      )}
                      {result.recipe.current_feedback && (
                        <p className="tiny-text">
                          Saved state: {result.recipe.current_feedback === "like" ? "Favorite" : "Disliked"}
                        </p>
                      )}
                      <p className="tiny-text">
                        Score {result.score.toFixed(2)} - Matched {result.inventory_match_count}/
                        {result.required_ingredient_count}
                      </p>
                      <p className="tiny-text">
                        Time: {result.recipe.total_minutes ?? "N/A"} min
                        {result.recipe.prep_minutes ? ` | Prep ${result.recipe.prep_minutes}` : ""}
                        {result.recipe.cook_minutes ? ` | Cook ${result.recipe.cook_minutes}` : ""}
                      </p>
                      <p className="tiny-text">
                        Missing:{" "}
                        {result.missing_ingredients.length > 0
                          ? result.missing_ingredients.slice(0, 4).join(", ")
                          : "None"}
                      </p>
                      <div className="row-gap">
                        <Link href={`/recipes/${result.recipe.id}`}>View Details</Link>
                        <a
                          href={buildAllrecipesSearchUrl(result.recipe.title)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Search on Allrecipes
                        </a>
                      </div>
                      <div className="row-gap">
                        <button
                          className={result.recipe.current_feedback === "like" ? "feedback-button-liked" : undefined}
                          onClick={() => void submitRecipeFeedback(result.recipe.id, "like")}
                        >
                          {result.recipe.current_feedback === "like" ? "Favorited" : "Like"}
                        </button>
                        <button
                          className={result.recipe.current_feedback === "dislike" ? "feedback-button-disliked" : undefined}
                          onClick={() => void submitRecipeFeedback(result.recipe.id, "dislike")}
                        >
                          Dislike
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
              {renderRecipePagination()}
            </>
          )}
        </section>

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
