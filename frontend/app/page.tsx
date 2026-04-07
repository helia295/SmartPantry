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

type RecipeAssistantSuggestion = {
  recipe_id: number;
  title: string;
  reason: string;
  uses_up: string[];
  missing_ingredients: string[];
  substitution_ideas: string[];
  time_note?: string | null;
};

type RecipeAssistantResponse = {
  mode?: string;
  summary: string;
  strategy_note?: string | null;
  availability_note?: string | null;
  cta_label?: string | null;
  cta_url?: string | null;
  pantry_items_to_use_first: string[];
  recipes: RecipeAssistantSuggestion[];
};

type RecipeQuestionReference = {
  recipe_id: number;
  title: string;
  reason: string;
  pantry_fit?: string | null;
  missing_ingredients: string[];
  time_note?: string | null;
};

type RecipeQuestionAnswerResponse = {
  mode?: string;
  answer: string;
  strategy_note?: string | null;
  availability_note?: string | null;
  cta_label?: string | null;
  cta_url?: string | null;
  pantry_items_considered: string[];
  recipes: RecipeQuestionReference[];
};

type AssistantIngredientOption = {
  value: string;
  label: string;
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
  imageUrl: string | null;
  proposals: DetectionProposal[] | null;
  loading: boolean;
  error: string | null;
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
  const [assistantGoal, setAssistantGoal] = useState("");
  const [assistantMaxTotalMinutes, setAssistantMaxTotalMinutes] = useState("");
  const [assistantPrioritizeOldest, setAssistantPrioritizeOldest] = useState(true);
  const [assistantPrioritizedIngredients, setAssistantPrioritizedIngredients] = useState<string[]>([]);
  const [assistantIngredientPickerOpen, setAssistantIngredientPickerOpen] = useState(false);
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantResult, setAssistantResult] = useState<RecipeAssistantResponse | null>(null);
  const [assistantError, setAssistantError] = useState<string | null>(null);
  const [recipeQuestion, setRecipeQuestion] = useState("");
  const [recipeQuestionMaxMinutes, setRecipeQuestionMaxMinutes] = useState("");
  const [recipeQuestionLoading, setRecipeQuestionLoading] = useState(false);
  const [recipeQuestionResult, setRecipeQuestionResult] = useState<RecipeQuestionAnswerResponse | null>(null);
  const [recipeQuestionError, setRecipeQuestionError] = useState<string | null>(null);
  const [activeRecipeIntelligencePanel, setActiveRecipeIntelligencePanel] = useState<
    "assistant" | "question" | null
  >(null);

  const cameraInputRef = useRef<HTMLInputElement | null>(null);
  const libraryInputRef = useRef<HTMLInputElement | null>(null);
  const cameraVideoRef = useRef<HTMLVideoElement | null>(null);
  const cameraCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const activeImageRef = useRef<HTMLImageElement | null>(null);
  const cameraSectionRef = useRef<HTMLElement | null>(null);
  const assistantIngredientPickerRef = useRef<HTMLDivElement | null>(null);

  const [activeImageBounds, setActiveImageBounds] = useState<{
    left: number;
    top: number;
    width: number;
    height: number;
  } | null>(null);

  const displayTimezone = user?.timezone || selectedTimezone;

  const activeFrame = reviewFrames[activeImageIndex] || null;
  const activeProposal = activeFrame?.proposals?.[activeProposalIndex] || null;

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
    if (!notice || notice.tone === "error") return;
    const timeoutId = window.setTimeout(() => {
      setNotice((current) =>
        current &&
        current.section === notice.section &&
        current.tone === notice.tone &&
        current.text === notice.text
          ? null
          : current
      );
    }, 4200);

    return () => window.clearTimeout(timeoutId);
  }, [notice]);

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
    function handleOutsideClick(event: MouseEvent | globalThis.MouseEvent) {
      if (!assistantIngredientPickerRef.current) return;
      if (assistantIngredientPickerRef.current.contains(event.target as Node)) return;
      setAssistantIngredientPickerOpen(false);
    }

    if (assistantIngredientPickerOpen) {
      window.addEventListener("mousedown", handleOutsideClick);
    }
    return () => window.removeEventListener("mousedown", handleOutsideClick);
  }, [assistantIngredientPickerOpen]);

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
        if (f.imageUrl?.startsWith("blob:")) URL.revokeObjectURL(f.imageUrl);
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
    (count, frame) => count + (frame.image.pending_proposal_count ?? frame.proposals?.filter((proposal) => proposal.state === "pending").length ?? 0),
    0
  );
  const assistantIngredientOptions = useMemo<AssistantIngredientOption[]>(() => {
    const seen = new Set<string>();
    return inventory
      .map((item) => ({ value: item.normalized_name || normalizeLabel(item.name), label: item.name }))
      .filter((item) => {
        if (!item.value || seen.has(item.value)) return false;
        seen.add(item.value);
        return true;
      })
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [inventory]);

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

  async function hydrateReviewThumbnail(frameIndex: number, framesOverride?: ReviewFrame[]) {
    const sourceFrames = framesOverride ?? reviewFrames;
    const frame = sourceFrames[frameIndex];
    if (!frame || frame.imageUrl) return;

    try {
      const imageUrl = await fetchImageObjectUrl(frame.image.id);
      setReviewFrames((prev) =>
        prev.map((candidate, index) => {
          if (index !== frameIndex || candidate.imageUrl) return candidate;
          return { ...candidate, imageUrl };
        })
      );
    } catch {
      // Keep the lightweight placeholder if the thumbnail cannot be loaded.
    }
  }

  function revokeFrameImage(frame: ReviewFrame) {
    if (frame.imageUrl?.startsWith("blob:")) {
      URL.revokeObjectURL(frame.imageUrl);
    }
  }

  function mergeReviewFrames(rows: ImageRecord[], previousFrames: ReviewFrame[]): ReviewFrame[] {
    const previousById = new Map(previousFrames.map((frame) => [frame.image.id, frame]));
    return rows.map((row) => {
      const existing = previousById.get(row.id);
      if (!existing) {
        return {
          image: row,
          sessionId: row.detection_session_id as number,
          imageUrl: null,
          proposals: null,
          loading: false,
          error: null,
        };
      }

      return {
        ...existing,
        image: row,
        sessionId: row.detection_session_id as number,
      };
    });
  }

  function replaceReviewFrames(nextFrames: ReviewFrame[]) {
    setReviewFrames((prev) => {
      const nextIds = new Set(nextFrames.map((frame) => frame.image.id));
      prev.forEach((frame) => {
        if (!nextIds.has(frame.image.id)) {
          revokeFrameImage(frame);
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

  async function hydrateReviewFrame(
    frameIndex: number,
    framesOverride?: ReviewFrame[]
  ): Promise<ReviewFrame | null> {
    const sourceFrames = framesOverride ?? reviewFrames;
    const frame = sourceFrames[frameIndex];
    if (!frame) return null;
    if (frame.imageUrl && frame.proposals) return frame;

    setReviewFrames((prev) =>
      prev.map((candidate, index) =>
        index === frameIndex ? { ...candidate, loading: true, error: null } : candidate
      )
    );

    try {
      const [imageUrl, proposals] = await Promise.all([
        fetchImageObjectUrl(frame.image.id),
        fetchDetectionProposals(frame.sessionId, reviewMode),
      ]);
      const hydrated: ReviewFrame = {
        ...frame,
        imageUrl,
        proposals,
        loading: false,
        error: null,
        image: {
          ...frame.image,
          pending_proposal_count: proposals.filter((proposal) => proposal.state === "pending").length,
        },
      };

      setReviewFrames((prev) =>
        prev.map((candidate, index) => {
          if (index !== frameIndex) return candidate;
          if (candidate.imageUrl && candidate.imageUrl !== imageUrl) {
            revokeFrameImage(candidate);
          }
          return hydrated;
        })
      );
      return hydrated;
    } catch (e) {
      const errorMessage =
        e instanceof Error ? e.message : `Recent upload ${frame.image.original_filename} could not be loaded`;
      setReviewFrames((prev) =>
        prev.map((candidate, index) =>
          index === frameIndex ? { ...candidate, loading: false, error: errorMessage } : candidate
        )
      );
      showNotice("camera", "error", errorMessage);
      return null;
    }
  }

  async function openReviewFrame(frameIndex: number, framesOverride?: ReviewFrame[]) {
    const hydrated = await hydrateReviewFrame(frameIndex, framesOverride);
    if (!hydrated) return;
    setActiveImageIndex(frameIndex);
    const nextPendingIndex = hydrated.proposals?.findIndex((proposal) => proposal.state === "pending") ?? -1;
    setActiveProposalIndex(nextPendingIndex >= 0 ? nextPendingIndex : 0);
    setCameraWorkspaceOpen(true);
  }

  async function loadRecentUploads(
    openWorkspace = false,
    preferredImageIds: number[] = [],
    existingFramesOverride?: ReviewFrame[]
  ) {
    if (!token) return;

    const res = await fetch(`${API_BASE}/images`, { headers: authHeaders() });
    if (!res.ok) {
      showNotice("camera", "error", await parseError(res));
      return;
    }

    const payload = (await res.json()) as { results: ImageRecord[] };
    const rows = payload.results.filter((row) => row.detection_session_id).slice(0, 10);
    const sourceFrames = existingFramesOverride ?? reviewFrames;
    const currentImageId = sourceFrames[activeImageIndex]?.image.id;
    const frames = mergeReviewFrames(rows, sourceFrames);
    replaceReviewFrames(frames);
    frames.forEach((_, index) => {
      void hydrateReviewThumbnail(index, frames);
    });

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
              (frame.proposals?.some((proposal) => proposal.state === "pending") ??
                (frame.image.pending_proposal_count ?? 0) > 0)
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
    const loadedProposals = frames[nextIndex].proposals;
    const nextPendingIndex = loadedProposals?.findIndex((proposal) => proposal.state === "pending") ?? -1;
    setActiveProposalIndex(nextPendingIndex >= 0 ? nextPendingIndex : 0);
    if (openWorkspace) {
      await openReviewFrame(nextIndex, frames);
    } else {
      setCameraWorkspaceOpen(false);
    }
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
        uploadPayload.results.map((row) => row.image.id),
        []
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
        const proposals = (frame.proposals ?? []).map((proposal, proposalIndex) =>
          proposalIndex === activeProposalIndex ? { ...proposal, ...patch } : proposal
        );
        return {
          ...frame,
          proposals,
          image: {
            ...frame.image,
            pending_proposal_count: proposals.filter((proposal) => proposal.state === "pending").length,
          },
        };
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
        const proposals = (frame.proposals ?? []).map((proposal, proposalIndex) =>
          proposalIndex === activeProposalIndex ? { ...proposal, state: nextState } : proposal
        );
        return {
          ...frame,
          proposals,
          image: {
            ...frame.image,
            pending_proposal_count: proposals.filter((proposal) => proposal.state === "pending").length,
          },
        };
      });
      return nextFrames;
    });
    return nextFrames;
  }

  async function moveToNextProposal(framesOverride: ReviewFrame[] = reviewFrames) {
    const currentFrame = framesOverride[activeImageIndex];
    const currentProposals = currentFrame?.proposals ?? [];
    const nextInCurrentIndex = currentProposals.findIndex(
      (proposal, index) => index > activeProposalIndex && proposal.state === "pending"
    );
    if (nextInCurrentIndex >= 0) {
      setActiveProposalIndex(nextInCurrentIndex);
      return;
    }

    for (let offset = 1; offset <= framesOverride.length; offset += 1) {
      const frameIndex = (activeImageIndex + offset) % framesOverride.length;
      const frame = framesOverride[frameIndex];
      if ((frame.image.pending_proposal_count ?? 0) > 0) {
        await openReviewFrame(frameIndex, framesOverride);
        return;
      }
    }

    if (framesOverride.every((frame) => (frame.image.pending_proposal_count ?? 0) <= 0)) {
      setCameraWorkspaceOpen(false);
      showNotice("camera", "success", "Review complete for the current uploads.");
    }
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
    await moveToNextProposal(nextFrames);
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
      prev.map((frame, idx) => {
        if (idx !== activeImageIndex) return frame;
        const proposals = [...(frame.proposals ?? []), proposal];
        return {
          ...frame,
          proposals,
          image: {
            ...frame.image,
            pending_proposal_count: proposals.filter((candidate) => candidate.state === "pending").length,
          },
        };
      })
    );
    setActiveProposalIndex(activeFrame.proposals?.length ?? 0);
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
        reviewFrames.map(async (frame) => {
          if (!frame.proposals) {
            return frame;
          }
          const proposals = await fetchDetectionProposals(frame.sessionId, mode);
          return {
            ...frame,
            proposals,
            image: {
              ...frame.image,
              pending_proposal_count: proposals.filter((proposal) => proposal.state === "pending").length,
            },
          };
        })
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

  async function runRecipeAssistant() {
    if (!token) {
      showNotice("recipes", "error", "Log in first.");
      return;
    }

    setAssistantLoading(true);
    setAssistantError(null);

    const payload = {
      user_goal: assistantGoal.trim() || null,
      max_total_minutes: assistantMaxTotalMinutes.trim()
        ? Number(assistantMaxTotalMinutes.trim())
        : null,
      main_ingredients: recipeMainIngredients.trim() || null,
      prioritize_oldest_items: assistantPrioritizeOldest,
      prioritized_ingredients: assistantPrioritizedIngredients,
    };

    const res = await fetch(`${API_BASE}/recipes/assistant/use-up`, {
      method: "POST",
      headers: authHeaders("application/json"),
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const message = await parseError(res);
      setAssistantLoading(false);
      setAssistantError(message);
      showNotice("recipes", "error", message);
      return;
    }

    const response = (await res.json()) as RecipeAssistantResponse;
    setAssistantResult(response);
    setAssistantLoading(false);
    showNotice(
      "recipes",
      response.recipes.length > 0 ? "success" : "info",
      response.recipes.length > 0
        ? "Sous chef suggestions are ready."
        : "The assistant needs a little more pantry context before it can narrow things down."
    );
  }

  function toggleAssistantIngredientSelection(nextValue: string) {
    setAssistantPrioritizedIngredients((prev) =>
      prev.includes(nextValue) ? prev.filter((value) => value !== nextValue) : [...prev, nextValue]
    );
  }

  function removeAssistantIngredientSelection(valueToRemove: string) {
    setAssistantPrioritizedIngredients((prev) => prev.filter((value) => value !== valueToRemove));
  }

  function clearRecipeIntelligencePanels() {
    setAssistantResult(null);
    setAssistantError(null);
    setRecipeQuestionResult(null);
    setRecipeQuestionError(null);
    setAssistantIngredientPickerOpen(false);
    setActiveRecipeIntelligencePanel(null);
  }

  function toggleRecipeFinder() {
    clearRecipeIntelligencePanels();
    setShowRecipeFinder((prev) => !prev);
  }

  async function askSmartPantry() {
    if (!token) {
      showNotice("recipes", "error", "Log in first.");
      return;
    }

    const question = recipeQuestion.trim();
    if (!question) {
      setRecipeQuestionError("Enter a question first so SmartPantry knows what to look for.");
      showNotice("recipes", "error", "Enter a recipe question first.");
      return;
    }

    setRecipeQuestionLoading(true);
    setRecipeQuestionError(null);

    const payload = {
      question,
      max_total_minutes: recipeQuestionMaxMinutes.trim()
        ? Number(recipeQuestionMaxMinutes.trim())
        : null,
    };

    const res = await fetch(`${API_BASE}/recipes/assistant/ask`, {
      method: "POST",
      headers: authHeaders("application/json"),
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const message = await parseError(res);
      setRecipeQuestionLoading(false);
      setRecipeQuestionError(message);
      showNotice("recipes", "error", message);
      return;
    }

    const response = (await res.json()) as RecipeQuestionAnswerResponse;
    setRecipeQuestionResult(response);
    setRecipeQuestionLoading(false);
    showNotice(
      "recipes",
      response.recipes.length > 0 ? "success" : "info",
      response.recipes.length > 0
        ? "Ask SmartPantry is ready with recipe ideas."
        : "SmartPantry needs a broader question or more pantry context to answer that well."
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
    !manualPointMode &&
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

  const manualPointMarker =
    manualPointMode &&
    pendingManualPoint &&
    activeImageBounds
      ? {
          left: `${(activeImageBounds.left || 0) + pendingManualPoint.x * (activeImageBounds.width || 0)}px`,
          top: `${(activeImageBounds.top || 0) + pendingManualPoint.y * (activeImageBounds.height || 0)}px`,
        }
      : null;

  return (
    <main className="app-wrap">
      <section className="shell">
        <div className="hero-row">
            <div className="hero-copy">
              <div className="brand-lockup">
                <div>
                  <p className="eyebrow">AI-assisted pantry helper</p>
                  <img
                    src="/smartpantry-wordmark.png"
                    alt="SmartPantry"
                    className="brand-wordmark"
                  />
                </div>
              </div>
            <div className="subtitle hero-message">
              <p>Keep your kitchen organized with faster inventory updates and AI-assisted photo review.</p>
              <p>
                Then get pantry-aware recipe suggestions, with a smarter ask-anything recipe AI guide.
              </p>
            </div>
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
                    const pendingCount = frame.image.pending_proposal_count ?? 0;
                    return (
                      <button
                        key={frame.image.id}
                        className={`review-thumb ${frameIndex === activeImageIndex && cameraWorkspaceOpen ? "review-thumb-active" : ""}`}
                        onClick={() => void openReviewFrame(frameIndex)}
                      >
                        {frame.imageUrl ? (
                          <img src={frame.imageUrl} alt={frame.image.original_filename} />
                        ) : (
                          <div className="review-thumb-placeholder">
                            <span aria-hidden="true">🖼️</span>
                          </div>
                        )}
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

            {cameraWorkspaceOpen && activeFrame?.loading ? (
              <div className="review-collapsed-note">
                <p className="muted-text">Opening that upload and loading its review details…</p>
              </div>
            ) : cameraWorkspaceOpen && activeFrame?.error ? (
              <div className="review-collapsed-note">
                <p className="error">{activeFrame.error}</p>
              </div>
            ) : cameraWorkspaceOpen && activeFrame && activeFrame.imageUrl && activeFrame.proposals ? (
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
                  <div className="review-sidebar-card review-complete-card">
                    <p className="tiny-text">
                      Finished reviewing this upload set? Collapse the workspace and keep Recent Uploads only.
                    </p>
                    <button
                      className="secondary-button"
                      onClick={() => {
                        clearNotice("camera");
                        setCameraWorkspaceOpen(false);
                        setManualPointMode(false);
                        setPendingManualPoint(null);
                        setManualLabelHint("");
                      }}
                    >
                      Done reviewing
                    </button>
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
                    {manualPointMarker && <div className="manual-point-marker" style={manualPointMarker} />}
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
                    {!manualPointMode && activeFrame.image.pending_proposal_count === 0 && (
                      <p className="tiny-text">
                        Finished with this upload? Use <strong>Done reviewing</strong> to collapse the workspace.
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
              <button onClick={toggleRecipeFinder}>
                {showRecipeFinder ? "Hide Filters" : "Find Recipe"}
              </button>
            </div>
          </div>

            <div className="recipe-assistant-shell">
            <div className="recipe-intelligence-head">
              <div>
                <p className="eyebrow">Recipe intelligence</p>
                <h3>Choose between guided planning and grounded recipe Q&amp;A.</h3>
                <p className="muted-text">
                  Use the planner when you want a short pantry-aware shortlist. Use Ask SmartPantry when you want to ask about any recipe or ingredient in plain language.
                </p>
              </div>
              <button
                type="button"
                className="recipe-intelligence-reset"
                onClick={clearRecipeIntelligencePanels}
              >
                Clear AI panels
              </button>
            </div>

            <div className="recipe-intelligence-grid">
            <div
              className={`recipe-assistant-panel${
                activeRecipeIntelligencePanel === "assistant" ? " recipe-assistant-panel-active" : ""
              }`}
            >
              <div className="recipe-assistant-copy">
                <p className="eyebrow">SmartPantry assistant</p>
                <div className="recipe-assistant-heading-row">
                  <h3>Build me a shortlist</h3>
                  <span className="section-chip">Planner</span>
                </div>
                <p className="muted-text">
                  Best when you want a few pantry-aware recipe options without writing a long question.
                </p>
                <button
                  type="button"
                  className="recipe-assistant-inline-toggle"
                  onClick={() =>
                    setActiveRecipeIntelligencePanel((prev) => (prev === "assistant" ? null : "assistant"))
                  }
                >
                  {activeRecipeIntelligencePanel === "assistant" ? "Hide planner" : "Open planner"}
                </button>
              </div>

              {activeRecipeIntelligencePanel === "assistant" && (
              <>
              <div className="recipe-assistant-controls">
                <div className="recipe-assistant-primary-row">
                  <input
                    value={assistantGoal}
                    onChange={(e) => setAssistantGoal(e.target.value)}
                    placeholder="What sounds good? e.g. quick dinner"
                  />
                </div>
                <div className="recipe-assistant-secondary-row">
                  <input
                    value={assistantMaxTotalMinutes}
                    onChange={(e) => setAssistantMaxTotalMinutes(e.target.value)}
                    type="number"
                    min="1"
                    step="1"
                    placeholder="Max minutes (optional)"
                  />
                  <button onClick={() => void runRecipeAssistant()} disabled={assistantLoading}>
                    {assistantLoading ? "Thinking..." : "Get suggestions"}
                  </button>
                </div>
              </div>

              <div className="recipe-assistant-options">
                <label className="checkbox-label recipe-assistant-toggle">
                  <input
                    type="checkbox"
                    checked={assistantPrioritizeOldest}
                    onChange={(e) => setAssistantPrioritizeOldest(e.target.checked)}
                  />
                  Prioritize older perishables
                </label>

                <div className="recipe-assistant-ingredient-picker" ref={assistantIngredientPickerRef}>
                  <label className="tiny-text" htmlFor="assistant-prioritized-ingredients-button">
                    Priority ingredients
                  </label>
                  <button
                    id="assistant-prioritized-ingredients-button"
                    type="button"
                    className="recipe-assistant-picker-button"
                    onClick={() => setAssistantIngredientPickerOpen((prev) => !prev)}
                  >
                    <span>
                      {assistantPrioritizedIngredients.length > 0
                        ? `${assistantPrioritizedIngredients.length} ingredient${assistantPrioritizedIngredients.length === 1 ? "" : "s"} selected`
                        : "Select pantry items"}
                    </span>
                    <span aria-hidden="true">{assistantIngredientPickerOpen ? "▲" : "▼"}</span>
                  </button>
                  {assistantIngredientPickerOpen && (
                    <div className="recipe-assistant-picker-menu">
                      {assistantIngredientOptions.length > 0 ? (
                        assistantIngredientOptions.map((option) => (
                          <label key={option.value} className="recipe-assistant-picker-option">
                            <input
                              type="checkbox"
                              checked={assistantPrioritizedIngredients.includes(option.value)}
                              onChange={() => toggleAssistantIngredientSelection(option.value)}
                            />
                            <span>{option.label}</span>
                          </label>
                        ))
                      ) : (
                        <p className="tiny-text">Add pantry items first to choose them here.</p>
                      )}
                    </div>
                  )}
                  {assistantPrioritizedIngredients.length > 0 && (
                    <div className="recipe-assistant-selected-row">
                      {assistantPrioritizedIngredients.map((value) => {
                        const label =
                          assistantIngredientOptions.find((option) => option.value === value)?.label || value;
                        return (
                          <button
                            key={value}
                            type="button"
                            className="recipe-assistant-selected-pill"
                            onClick={() => removeAssistantIngredientSelection(value)}
                          >
                            <span>{label}</span>
                            <span aria-hidden="true">×</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                  <p className="tiny-text">
                    Optional. Pick specific pantry items when you want the shortlist to center around them.
                  </p>
                </div>
              </div>

              {assistantError && (
                <div className="app-alert app-alert-error">
                  <p>{assistantError}</p>
                </div>
              )}

              {assistantResult && (
                <div className="recipe-assistant-results">
                  <div className={`recipe-assistant-summary${assistantResult.mode === "preview" ? " recipe-assistant-summary-preview" : ""}`}>
                    <div>
                      <span className="section-chip">
                        {assistantResult.mode === "preview" ? "Preview mode" : "AI recommendation"}
                      </span>
                    </div>
                    <p>{assistantResult.summary}</p>
                    {assistantResult.strategy_note && (
                      <p className="tiny-text">{assistantResult.strategy_note}</p>
                    )}
                    {assistantResult.availability_note && (
                      <p className="tiny-text recipe-assistant-preview-note">{assistantResult.availability_note}</p>
                    )}
                    {assistantResult.cta_url && assistantResult.cta_label && (
                      <div className="recipe-assistant-preview-actions">
                        <a
                          href={assistantResult.cta_url}
                          target="_blank"
                          rel="noreferrer"
                          className="header-link-chip"
                        >
                          {assistantResult.cta_label}
                        </a>
                      </div>
                    )}
                    {assistantResult.pantry_items_to_use_first.length > 0 && (
                      <div className="recipe-assistant-pantry-priority">
                        <span className="tiny-text">Use soon:</span>
                        {assistantResult.pantry_items_to_use_first.map((item) => (
                          <span key={item} className="recipe-assistant-pill">
                            {item}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {assistantResult.recipes.length > 0 && (
                    <div className="recipe-assistant-card-grid">
                      {assistantResult.recipes.map((suggestion) => (
                        <article key={suggestion.recipe_id} className="recipe-assistant-card">
                          <div className="recipe-assistant-card-head">
                            <div>
                              <h4>{suggestion.title}</h4>
                              {suggestion.time_note && (
                                <p className="tiny-text">{suggestion.time_note}</p>
                              )}
                            </div>
                            <Link href={`/recipes/${suggestion.recipe_id}`} className="header-link-chip">
                              View recipe
                            </Link>
                          </div>

                          <p>{suggestion.reason}</p>

                          {suggestion.uses_up.length > 0 && (
                            <div className="recipe-assistant-meta-block">
                              <span className="tiny-text">Helps use up</span>
                              <div className="recipe-assistant-pill-row">
                                {suggestion.uses_up.map((item) => (
                                  <span key={`${suggestion.recipe_id}-use-${item}`} className="recipe-assistant-pill">
                                    {item}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {suggestion.missing_ingredients.length > 0 && (
                            <div className="recipe-assistant-meta-block">
                              <span className="tiny-text">Missing</span>
                              <p className="tiny-text">
                                {suggestion.missing_ingredients.join(", ")}
                              </p>
                            </div>
                          )}

                          {suggestion.substitution_ideas.length > 0 && (
                            <div className="recipe-assistant-meta-block">
                              <span className="tiny-text">Substitution ideas</span>
                              <ul className="recipe-assistant-list">
                                {suggestion.substitution_ideas.map((idea) => (
                                  <li key={`${suggestion.recipe_id}-idea-${idea}`}>{idea}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              )}
              </>
              )}
            </div>

            <div
              className={`recipe-assistant-panel recipe-assistant-panel-secondary${
                activeRecipeIntelligencePanel === "question" ? " recipe-assistant-panel-active" : ""
              }`}
            >
              <div className="recipe-assistant-copy">
                <p className="eyebrow">Ask SmartPantry</p>
                <div className="recipe-assistant-heading-row">
                  <h3>Ask a recipe question</h3>
                  <span className="section-chip">Grounded Q&amp;A</span>
                </div>
                <p className="muted-text">
                  Best when you want to ask something specific, like an ingredient combination, time limit, or meal idea.
                </p>
                <button
                  type="button"
                  className="recipe-assistant-inline-toggle"
                  onClick={() =>
                    setActiveRecipeIntelligencePanel((prev) => (prev === "question" ? null : "question"))
                  }
                >
                  {activeRecipeIntelligencePanel === "question" ? "Hide Q&A" : "Open Q&A"}
                </button>
              </div>

              {activeRecipeIntelligencePanel === "question" && (
              <>
              <div className="recipe-assistant-controls recipe-assistant-controls-secondary">
                <div className="recipe-assistant-primary-row">
                  <input
                    value={recipeQuestion}
                    onChange={(e) => setRecipeQuestion(e.target.value)}
                    placeholder="Ask about any ingredients, timing, or meal ideas"
                  />
                </div>
                <div className="recipe-assistant-secondary-row">
                  <input
                    value={recipeQuestionMaxMinutes}
                    onChange={(e) => setRecipeQuestionMaxMinutes(e.target.value)}
                    type="number"
                    min="1"
                    step="1"
                    placeholder="Max minutes (optional)"
                  />
                  <button onClick={() => void askSmartPantry()} disabled={recipeQuestionLoading}>
                    {recipeQuestionLoading ? "Searching..." : "Ask SmartPantry"}
                  </button>
                </div>
              </div>

              {recipeQuestionError && (
                <div className="app-alert app-alert-error">
                  <p>{recipeQuestionError}</p>
                </div>
              )}

              {recipeQuestionResult && (
                <div className="recipe-assistant-results">
                  <div className={`recipe-assistant-summary${recipeQuestionResult.mode === "preview" ? " recipe-assistant-summary-preview" : ""}`}>
                    <div>
                      <span className="section-chip">
                        {recipeQuestionResult.mode === "preview" ? "Preview mode" : "Grounded answer"}
                      </span>
                    </div>
                    <p>{recipeQuestionResult.answer}</p>
                    {recipeQuestionResult.strategy_note && (
                      <p className="tiny-text">{recipeQuestionResult.strategy_note}</p>
                    )}
                    {recipeQuestionResult.availability_note && (
                      <p className="tiny-text recipe-assistant-preview-note">{recipeQuestionResult.availability_note}</p>
                    )}
                    {recipeQuestionResult.cta_url && recipeQuestionResult.cta_label && (
                      <div className="recipe-assistant-preview-actions">
                        <a
                          href={recipeQuestionResult.cta_url}
                          target="_blank"
                          rel="noreferrer"
                          className="header-link-chip"
                        >
                          {recipeQuestionResult.cta_label}
                        </a>
                      </div>
                    )}
                    {recipeQuestionResult.pantry_items_considered.length > 0 && (
                      <div className="recipe-assistant-pantry-priority">
                        <span className="tiny-text">Pantry context:</span>
                        {recipeQuestionResult.pantry_items_considered.map((item) => (
                          <span key={item} className="recipe-assistant-pill">
                            {item}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {recipeQuestionResult.recipes.length > 0 && (
                    <div className="recipe-assistant-card-grid">
                      {recipeQuestionResult.recipes.map((recipe) => (
                        <article key={recipe.recipe_id} className="recipe-assistant-card">
                          <div className="recipe-assistant-card-head">
                            <div>
                              <h4>{recipe.title}</h4>
                              {recipe.time_note && <p className="tiny-text">{recipe.time_note}</p>}
                            </div>
                            <Link href={`/recipes/${recipe.recipe_id}`} className="header-link-chip">
                              View recipe
                            </Link>
                          </div>

                          <p>{recipe.reason}</p>

                          {recipe.pantry_fit && (
                            <div className="recipe-assistant-meta-block">
                              <span className="tiny-text">Why it fits</span>
                              <p className="tiny-text">{recipe.pantry_fit}</p>
                            </div>
                          )}

                          {recipe.missing_ingredients.length > 0 && (
                            <div className="recipe-assistant-meta-block">
                              <span className="tiny-text">Missing</span>
                              <p className="tiny-text">{recipe.missing_ingredients.join(", ")}</p>
                            </div>
                          )}
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              )}
              </>
              )}
            </div>
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
            Recipe discovery data courtesy of the MIT-licensed Kaggle's AllRecipe Dataset, derived from AllRecipes.com content.
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
