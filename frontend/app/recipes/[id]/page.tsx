"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { useSlidingSession } from "../../lib/session";

const API_BASE = "/api/proxy";

type RecipeIngredient = {
  ingredient_raw: string;
  ingredient_normalized: string;
  quantity_text?: string | null;
  is_optional: boolean;
};

type RecipeDetail = {
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
  favorite_tags: string[];
  nutrition: Record<string, string | number | boolean | null>;
  instructions_text?: string | null;
  ingredients: RecipeIngredient[];
};

type InventoryOption = {
  id: number;
  name: string;
  normalized_name: string;
  quantity: number;
  unit: string;
  category?: string | null;
};

type RecipeCookPreviewItem = {
  ingredient_key: string;
  ingredient_raw: string;
  ingredient_normalized: string;
  quantity_text?: string | null;
  match_status: "matched" | "needs_review" | "unmatched";
  selected_inventory_item_id?: number | null;
  selected_inventory_item_name?: string | null;
  inventory_item_quantity?: number | null;
  inventory_item_unit?: string | null;
  reliable_quantity_match: boolean;
  suggested_used_quantity?: number | null;
  suggested_remaining_quantity?: number | null;
  notes: string[];
};

type RecipeCookPreview = {
  recipe_id: number;
  multiplier: number;
  inventory_options: InventoryOption[];
  items: RecipeCookPreviewItem[];
};

type CookActionDraft = {
  ingredientKey: string;
  ingredientRaw: string;
  ingredientNormalized: string;
  pantryChoice: string;
  newQuantity: string;
  newUnit: string;
};

function buildAllrecipesSearchUrl(title: string): string {
  return `https://www.allrecipes.com/search?q=${encodeURIComponent(title)}`;
}

function displayRecipeSourceName(sourceName?: string | null): string {
  if (!sourceName || sourceName === "allrecipes-search") return "Allrecipes.com";
  return sourceName;
}

function RecipeDetailImage({ src, alt }: { src?: string | null; alt: string }) {
  const [broken, setBroken] = useState(false);

  if (!src || broken) {
    return <div className="detail-image recipe-image-fallback">Recipe image unavailable</div>;
  }

  return (
    <img
      src={src}
      alt={alt}
      className="detail-image"
      onError={() => setBroken(true)}
    />
  );
}

export default function RecipeDetailPage() {
  const params = useParams<{ id: string }>();
  const [recipe, setRecipe] = useState<RecipeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [cookOpen, setCookOpen] = useState(false);
  const [cookLoading, setCookLoading] = useState(false);
  const [cookApplying, setCookApplying] = useState(false);
  const [cookMessage, setCookMessage] = useState<string | null>(null);
  const [cookError, setCookError] = useState<string | null>(null);
  const [cookMultiplier, setCookMultiplier] = useState("1");
  const [cookPreview, setCookPreview] = useState<RecipeCookPreview | null>(null);
  const [cookActions, setCookActions] = useState<Record<string, CookActionDraft>>({});
  const handleSessionExpired = useCallback(() => {
    setRecipe(null);
    setError("Session expired due to inactivity. Please log in again.");
    setLoading(false);
  }, []);
  const { token, ready: sessionReady, clearSessionToken } = useSlidingSession({
    apiBase: API_BASE,
    onExpired: handleSessionExpired,
  });

  useEffect(() => {
    if (!sessionReady) return;
    if (!token) {
      setError("Log in first to view recipe details.");
      setLoading(false);
    }
  }, [sessionReady, token]);

  useEffect(() => {
    if (!token || !params?.id) return;

    async function loadRecipe() {
      setLoading(true);
      const res = await fetch(`${API_BASE}/recipes/${params.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        if (res.status === 401) {
          clearSessionToken();
          handleSessionExpired();
          return;
        }
        setError(`Recipe ${params.id} could not be loaded.`);
        setLoading(false);
        return;
      }
      setRecipe((await res.json()) as RecipeDetail);
      setLoading(false);
    }

    void loadRecipe();
  }, [clearSessionToken, handleSessionExpired, params?.id, token]);

  useEffect(() => {
    if (!cookMessage) return;
    const timeoutId = window.setTimeout(() => setCookMessage(null), 4800);
    return () => window.clearTimeout(timeoutId);
  }, [cookMessage]);

  async function submitFeedback(feedbackType: "like" | "dislike") {
    if (!token || !recipe) return;
    if (feedbackType === "like" && recipe.current_feedback === "like") {
      setFeedbackLoading(true);
      const deleteRes = await fetch(`${API_BASE}/recipes/${recipe.id}/feedback`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!deleteRes.ok) {
        setError(`Could not remove recipe favorite (${deleteRes.status}).`);
        setFeedbackLoading(false);
        return;
      }
      setRecipe((prev) => (prev ? { ...prev, current_feedback: null } : prev));
      setFeedbackLoading(false);
      return;
    }
    setFeedbackLoading(true);
    const res = await fetch(`${API_BASE}/recipes/${recipe.id}/feedback`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ feedback_type: feedbackType }),
    });
    if (!res.ok) {
      setError(`Could not save recipe feedback (${res.status}).`);
      setFeedbackLoading(false);
      return;
    }
    setRecipe((prev) => (prev ? { ...prev, current_feedback: feedbackType } : prev));
    setFeedbackLoading(false);
  }

  const inventoryOptionsById = useMemo(() => {
    const map = new Map<number, InventoryOption>();
    cookPreview?.inventory_options.forEach((option) => map.set(option.id, option));
    return map;
  }, [cookPreview]);

  function buildDefaultCookActions(preview: RecipeCookPreview): Record<string, CookActionDraft> {
    return Object.fromEntries(
      preview.items.map((item) => {
        const defaultPantryChoice = item.selected_inventory_item_id
          ? String(item.selected_inventory_item_id)
          : "ignore";

        return [
          item.ingredient_key,
          {
            ingredientKey: item.ingredient_key,
            ingredientRaw: item.ingredient_raw,
            ingredientNormalized: item.ingredient_normalized,
            pantryChoice: defaultPantryChoice,
            newQuantity:
              typeof item.suggested_remaining_quantity === "number"
                ? String(Math.max(item.suggested_remaining_quantity, 0))
                : "",
            newUnit: item.inventory_item_unit || "count",
          },
        ];
      })
    );
  }

  async function loadCookPreview(multiplierOverride?: string) {
    if (!token || !recipe) return;
    const multiplierValue = Number(multiplierOverride ?? cookMultiplier);
    if (!Number.isFinite(multiplierValue) || multiplierValue <= 0) {
      setCookError("Choose a valid portion multiplier before previewing pantry updates.");
      return;
    }

    setCookLoading(true);
    setCookError(null);
    setCookMessage(null);
    const res = await fetch(`${API_BASE}/recipes/${recipe.id}/cook-preview`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ multiplier: multiplierValue }),
    });
    if (!res.ok) {
      setCookError(`Pantry update preview could not be generated (${res.status}).`);
      setCookLoading(false);
      return;
    }
    const preview = (await res.json()) as RecipeCookPreview;
    setCookPreview(preview);
    setCookActions(buildDefaultCookActions(preview));
    setCookLoading(false);
  }

  async function openCookFlow() {
    const nextOpen = !cookOpen;
    setCookOpen(nextOpen);
    setCookError(null);
    if (nextOpen && !cookPreview) {
      await loadCookPreview();
    }
  }

  function updateCookAction(
    ingredientKey: string,
    updates: Partial<CookActionDraft>
  ) {
    setCookActions((prev) => {
      const current = prev[ingredientKey];
      if (!current) return prev;
      return {
        ...prev,
        [ingredientKey]: {
          ...current,
          ...updates,
        },
      };
    });
  }

  async function applyCookUpdates() {
    if (!token || !recipe || !cookPreview) return;
    setCookApplying(true);
    setCookError(null);
    setCookMessage(null);
    const res = await fetch(`${API_BASE}/recipes/${recipe.id}/cook-apply`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        multiplier: Number(cookMultiplier),
        actions: Object.values(cookActions).map((action) => ({
          ingredient_key: action.ingredientKey,
          ingredient_raw: action.ingredientRaw,
          ingredient_normalized: action.ingredientNormalized,
          inventory_item_id:
            action.pantryChoice !== "ignore" && action.pantryChoice !== "remove"
              ? Number(action.pantryChoice)
              : null,
          decision:
            action.pantryChoice === "ignore"
              ? "ignore"
              : action.pantryChoice === "remove" || Number(action.newQuantity || "0") <= 0
                ? "remove"
                : "update",
          new_quantity:
            action.pantryChoice !== "ignore" && action.newQuantity !== ""
              ? Number(action.newQuantity)
              : null,
          new_unit:
            action.pantryChoice !== "ignore" && action.newUnit !== ""
              ? action.newUnit
              : null,
        })),
      }),
    });
    if (!res.ok) {
      setCookError(`Pantry updates could not be applied (${res.status}).`);
      setCookApplying(false);
      return;
    }
    const payload = (await res.json()) as {
      updated: number;
      removed: number;
      ignored: number;
    };
    setCookMessage(
      `Pantry updated: ${payload.updated} adjusted, ${payload.removed} removed, ${payload.ignored} ignored.`
    );
    setCookOpen(false);
    setCookPreview(null);
    setCookActions({});
    setCookApplying(false);
  }

  return (
    <main className="app-wrap">
      <section className="shell">
        <div className="card detail-shell">
          <div className="detail-nav">
            <Link href="/" className="header-link-chip">Dashboard</Link>
            <Link href="/account" className="header-link-chip">Account</Link>
            <Link href="/recipes/book" className="header-link-chip">Favorite Recipes</Link>
            {recipe && (
              <a
                href={buildAllrecipesSearchUrl(recipe.title)}
                target="_blank"
                rel="noreferrer"
                className="header-link-chip"
              >
                Search on Allrecipes
              </a>
            )}
          </div>

          {loading && (
            <div className="detail-state detail-state-loading">
              <p className="eyebrow">Recipe notebook</p>
              <h2>Loading recipe…</h2>
              <p className="muted-text">Gathering the cover photo, pantry notes, and saved state for this dish.</p>
            </div>
          )}
          {error && (
            <div className="detail-state detail-state-error">
              <p className="eyebrow">Recipe notebook</p>
              <h2>Recipe unavailable</h2>
              <p className="error">{error}</p>
            </div>
          )}

          {recipe && (
            <>
              <div className="detail-hero detail-hero-rich">
                <div className="detail-copy">
                  <p className="eyebrow">Recipe notebook</p>
                  <h1 className="title">{recipe.title}</h1>
                  <p className="subtitle">
                    {displayRecipeSourceName(recipe.source_name)}
                    {recipe.cuisine ? ` • ${recipe.cuisine}` : ""}
                  </p>
                  <div className="detail-stat-strip">
                    <div className="detail-stat-card">
                      <span className="tiny-text">Total time</span>
                      <strong>{recipe.total_minutes ?? "N/A"} min</strong>
                    </div>
                    <div className="detail-stat-card">
                      <span className="tiny-text">Prep / Cook</span>
                      <strong>
                        {recipe.prep_minutes ?? "N/A"} / {recipe.cook_minutes ?? "N/A"} min
                      </strong>
                    </div>
                    <div className="detail-stat-card">
                      <span className="tiny-text">Servings</span>
                      <strong>{recipe.servings ?? "N/A"}</strong>
                    </div>
                    <div className="detail-stat-card">
                      <span className="tiny-text">Rating</span>
                      <strong>
                        {typeof recipe.rating === "number" ? `${recipe.rating.toFixed(1)} / 5` : "Not rated"}
                      </strong>
                    </div>
                  </div>
                  <div className="detail-tag-row">
                    {recipe.current_feedback && (
                      <span
                        className={`inventory-badge ${
                          recipe.current_feedback === "like" ? "detail-badge-favorite" : "detail-badge-dislike"
                        }`}
                      >
                        {recipe.current_feedback === "like" ? "Favorite recipe" : "Disliked"}
                      </span>
                    )}
                    {recipe.dietary_tags.map((tag) => (
                      <span key={tag} className="detail-tag-pill">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="detail-hero-image-wrap">
                  <RecipeDetailImage src={recipe.image_url} alt={recipe.title} />
                </div>
              </div>

              <div className="detail-action-row">
                <button
                  className={recipe.current_feedback === "like" ? "feedback-button-liked" : undefined}
                  onClick={() => void submitFeedback("like")}
                  disabled={feedbackLoading}
                >
                  {recipe.current_feedback === "like" ? "Favorited" : "Add to Favorites"}
                </button>
                <button
                  className={recipe.current_feedback === "dislike" ? "feedback-button-disliked" : undefined}
                  onClick={() => void submitFeedback("dislike")}
                  disabled={feedbackLoading}
                >
                  Dislike
                </button>
                <button onClick={() => void openCookFlow()} disabled={cookLoading || feedbackLoading}>
                  {cookOpen ? "Hide pantry update" : "Update pantry"}
                </button>
              </div>
              {!cookOpen && cookMessage && (
                <div className="app-alert app-alert-success">
                  <p>{cookMessage}</p>
                </div>
              )}
              {!cookOpen && (
                <p className="tiny-text">
                  Used ingredients to make this recipe? Quickly update your inventory here after cooking.
                </p>
              )}

              {cookOpen && (
                <div className="card detail-panel cook-panel">
                  <div className="detail-panel-heading">
                    <div>
                      <p className="eyebrow">After cooking</p>
                      <h2>Update pantry</h2>
                    </div>
                    <span className="section-chip">User review required</span>
                  </div>
                  <p className="muted-text">
                    Used ingredients to make this recipe? Pick how much you cooked, review the suggested pantry changes, and confirm only what should actually change. Nothing updates until you apply.
                  </p>
                  <p className="tiny-text">
                    Tip: choose Ignore if you skipped an ingredient. Choose Remove from pantry, or set the new quantity to `0`, if an item is fully used up.
                  </p>
                  <div className="cook-multiplier-row">
                    {["0.5", "1", "2"].map((value) => (
                      <button
                        key={value}
                        className={cookMultiplier === value ? "feedback-button-liked" : undefined}
                        onClick={() => {
                          setCookMultiplier(value);
                          void loadCookPreview(value);
                        }}
                        type="button"
                      >
                        {value}x
                      </button>
                    ))}
                    <input
                      value={cookMultiplier}
                      onChange={(e) => setCookMultiplier(e.target.value)}
                      type="number"
                      min="0.1"
                      step="0.1"
                      placeholder="Custom"
                    />
                    <button onClick={() => void loadCookPreview()} disabled={cookLoading} type="button">
                      Refresh preview
                    </button>
                  </div>

                  {cookLoading && <p className="muted-text">Building pantry update preview…</p>}
                  {cookError && (
                    <div className="app-alert app-alert-error">
                      <p>{cookError}</p>
                    </div>
                  )}

{cookPreview && (
                    <div className="cook-preview-list">
                      {cookPreview.items.map((item) => {
                        const action = cookActions[item.ingredient_key];
                        const selectedOption =
                          action?.pantryChoice &&
                          action.pantryChoice !== "ignore" &&
                          action.pantryChoice !== "remove"
                            ? inventoryOptionsById.get(Number(action.pantryChoice))
                            : null;

                        const rowWillRemove =
                          action?.pantryChoice === "remove" ||
                          (action?.pantryChoice &&
                            action.pantryChoice !== "ignore" &&
                            action.newQuantity !== "" &&
                            Number(action.newQuantity) <= 0);

                        const quantityDisabled = action?.pantryChoice === "ignore";
                        const unitDisabled = action?.pantryChoice === "ignore" || action?.pantryChoice === "remove";

                        const unitOptions = [
                          ["count", "Count"],
                          ["piece", "Piece"],
                          ["g", "Gram (g)"],
                          ["kg", "Kilogram (kg)"],
                          ["oz", "Ounce (oz)"],
                          ["lb", "Pound (lb)"],
                          ["ml", "Milliliter (ml)"],
                          ["l", "Liter (l)"],
                          ["cup", "Cup"],
                          ["can", "Can"],
                          ["jar", "Jar"],
                          ["bottle", "Bottle"],
                          ["box", "Box"],
                          ["bag", "Bag"],
                          ["carton", "Carton"],
                          ["pack", "Pack"],
                          ["slice", "Slice"],
                          ["other", "Other"],
                        ];

                        const quantityPlaceholder =
                          typeof item.suggested_remaining_quantity === "number"
                            ? String(Math.max(item.suggested_remaining_quantity, 0))
                            : "Set manually";

                        const selectedPantryChoice = action?.pantryChoice ?? "ignore";

                        return (
                          <article key={item.ingredient_key} className="cook-preview-item">
                            <div className="cook-preview-header">
                              <div>
                                <strong>{item.ingredient_raw}</strong>
                                <p className="tiny-text">{item.ingredient_normalized}</p>
                              </div>
                              <span className="detail-tag-pill">
                                {item.match_status === "matched"
                                  ? "Match found"
                                  : item.match_status === "needs_review"
                                    ? "Review suggested"
                                    : "No match yet"}
                              </span>
                            </div>

                            <div className="cook-preview-grid">
                              <div className="list-col">
                                <label className="tiny-text">Pantry item</label>
                                <select
                                  value={selectedPantryChoice}
                                  onChange={(e) => {
                                    const nextChoice = e.target.value;
                                    const matchedOption =
                                      nextChoice !== "ignore" && nextChoice !== "remove"
                                        ? inventoryOptionsById.get(Number(nextChoice))
                                        : null;
                                    updateCookAction(item.ingredient_key, {
                                      pantryChoice: nextChoice,
                                      newQuantity:
                                        nextChoice === "remove"
                                          ? "0"
                                          : typeof item.suggested_remaining_quantity === "number"
                                            ? String(Math.max(item.suggested_remaining_quantity, 0))
                                            : matchedOption
                                              ? String(matchedOption.quantity)
                                              : "",
                                      newUnit:
                                        matchedOption?.unit ||
                                        action?.newUnit ||
                                        item.inventory_item_unit ||
                                        "count",
                                    });
                                  }}
                                >
                                  <option value="ignore">Ignore this ingredient</option>
                                  <option value="remove">Remove from pantry</option>
                                  {cookPreview.inventory_options.map((option) => (
                                    <option key={option.id} value={option.id}>
                                      {option.name} ({option.quantity} {option.unit})
                                    </option>
                                  ))}
                                </select>
                              </div>

                              <div className="list-col">
                                <label className="tiny-text">New quantity</label>
                                <input
                                  value={action?.newQuantity ?? ""}
                                  onChange={(e) =>
                                    updateCookAction(item.ingredient_key, { newQuantity: e.target.value })
                                  }
                                  type="number"
                                  min="0"
                                  step="0.1"
                                  disabled={quantityDisabled}
                                  placeholder={quantityPlaceholder}
                                />
                                <p className="tiny-text">
                                  {selectedOption
                                    ? rowWillRemove
                                      ? `This row will remove ${selectedOption.name} from pantry.`
                                      : `Current: ${selectedOption.quantity} ${selectedOption.unit}`
                                    : selectedPantryChoice === "remove"
                                      ? "Use this if the ingredient should be removed from your pantry."
                                      : "Choose a pantry item if you want to apply this ingredient."}
                                </p>
                              </div>

                              <div className="list-col">
                                <label className="tiny-text">Unit</label>
                                <select
                                  value={action?.newUnit ?? "count"}
                                  onChange={(e) =>
                                    updateCookAction(item.ingredient_key, { newUnit: e.target.value })
                                  }
                                  disabled={unitDisabled}
                                >
                                  {unitOptions.map(([value, label]) => (
                                    <option key={value} value={value}>
                                      {label}
                                    </option>
                                  ))}
                                </select>
                                <p className="tiny-text">
                                  {selectedOption
                                    ? `Change the stored pantry unit for ${selectedOption.name} if needed.`
                                    : "Units stay editable once a pantry item is selected."}
                                </p>
                              </div>
                            </div>

                            <div className="list-col">
                              {item.notes.map((note) => (
                                <p key={note} className="tiny-text">
                                  {note}
                                </p>
                              ))}
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  )}

                  <div className="row-gap">
                    <button onClick={() => void applyCookUpdates()} disabled={cookApplying || cookLoading}>
                      {cookApplying ? "Applying updates…" : "Apply pantry updates"}
                    </button>
                    <button type="button" onClick={() => setCookOpen(false)}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              <div className="detail-grid">
                <div className="card detail-panel detail-panel-ingredients">
                  <div className="detail-panel-heading">
                    <div>
                      <p className="eyebrow">Pantry match</p>
                      <h2>Ingredients</h2>
                    </div>
                    <span className="section-chip">
                      {recipe.ingredients.length} item{recipe.ingredients.length === 1 ? "" : "s"}
                    </span>
                  </div>
                  <div className="detail-ingredient-list">
                    {recipe.ingredients.map((ingredient, index) => (
                      <article key={`${ingredient.ingredient_normalized}-${index}`} className="detail-ingredient-item">
                        <div>
                          <strong>{ingredient.ingredient_raw}</strong>
                          <p className="tiny-text">{ingredient.ingredient_normalized}</p>
                        </div>
                        {ingredient.quantity_text && (
                          <span className="detail-tag-pill">{ingredient.quantity_text}</span>
                        )}
                      </article>
                    ))}
                  </div>
                </div>

                <div className="card detail-panel">
                  <div className="detail-panel-heading">
                    <div>
                      <p className="eyebrow">Kitchen notes</p>
                      <h2>Details</h2>
                    </div>
                  </div>
                  {recipe.instructions_text ? (
                    <p className="muted-text">{recipe.instructions_text}</p>
                  ) : (
                    <div className="detail-note-card">
                      <p className="muted-text">
                        Use the Allrecipes search button above to open the closest live recipe page.
                      </p>
                    </div>
                  )}

                  {Object.keys(recipe.nutrition || {}).length > 0 && (
                    <>
                      <div className="detail-subsection">
                        <h3>Nutrition</h3>
                      </div>
                      <div className="detail-nutrition-list">
                        {Object.entries(recipe.nutrition).map(([key, value]) => (
                          <article key={key} className="detail-nutrition-item">
                            <span className="tiny-text">{key}</span>
                            <strong>{String(value)}</strong>
                          </article>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>
              <p className="tiny-text">
                Recipe discovery data courtesy of the MIT-licensed Kaggle All Recipe Dataset, derived from Allrecipes.com content.
              </p>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
