"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useSlidingSession } from "../../lib/session";

const API_BASE = "/api/proxy";

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
  favorite_tags: string[];
  nutrition: Record<string, string | number | boolean | null>;
};

type RecipeBookResponse = {
  available_tags: string[];
  results: RecipeSummary[];
};

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

export default function SavedRecipesPage() {
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [availableTags, setAvailableTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [tagFilter, setTagFilter] = useState("");
  const [editingRecipeId, setEditingRecipeId] = useState<number | null>(null);
  const [tagDraft, setTagDraft] = useState("");
  const handleSessionExpired = useCallback(() => {
    setRecipes([]);
    setAvailableTags([]);
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
      setError("Log in first to view saved recipes.");
      setLoading(false);
    }
  }, [sessionReady, token]);

  useEffect(() => {
    if (!token) return;

    async function loadSavedRecipes() {
      setLoading(true);
      const res = await fetch(`${API_BASE}/recipes/book`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        if (res.status === 401) {
          clearSessionToken();
          handleSessionExpired();
          return;
        }
        setError(`Saved recipes could not be loaded (${res.status}).`);
        setLoading(false);
        return;
      }
      const payload = (await res.json()) as RecipeBookResponse;
      setAvailableTags(payload.available_tags);
      setRecipes(payload.results);
      setLoading(false);
    }

    void loadSavedRecipes();
  }, [clearSessionToken, handleSessionExpired, token]);

  async function removeFavorite(recipeId: number) {
    if (!token) return;
    setError(null);
    setMessage(null);
    const res = await fetch(`${API_BASE}/recipes/${recipeId}/feedback`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      setError(`Favorite could not be removed (${res.status}).`);
      return;
    }
    const nextRecipes = recipes.filter((recipe) => recipe.id !== recipeId);
    setRecipes(nextRecipes);
    setAvailableTags(
      Array.from(new Set(nextRecipes.flatMap((recipe) => recipe.favorite_tags))).sort((a, b) =>
        a.localeCompare(b)
      )
    );
    if (editingRecipeId === recipeId) {
      setEditingRecipeId(null);
      setTagDraft("");
    }
    setMessage("Removed from Favorites.");
  }

  async function saveRecipeTags(recipeId: number, nextTags: string[]) {
    if (!token) return;
    setError(null);
    setMessage(null);
    const res = await fetch(`${API_BASE}/recipes/${recipeId}/tags`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ tags: nextTags }),
    });
    if (!res.ok) {
      setError(`Tags could not be updated (${res.status}).`);
      return;
    }
    const payload = (await res.json()) as { recipe_id: number; tags: string[] };
    setRecipes((prev) =>
      prev.map((recipe) =>
        recipe.id === recipeId ? { ...recipe, favorite_tags: payload.tags } : recipe
      )
    );
    setAvailableTags((prev) => Array.from(new Set([...prev, ...payload.tags])).sort((a, b) => a.localeCompare(b)));
    setMessage(payload.tags.length > 0 ? "Favorite tags updated." : "Favorite tags cleared.");
  }

  async function addTagToRecipe(recipeId: number, rawTag: string) {
    const normalized = rawTag.trim().replace(/^#+/, "").toLowerCase().replace(/\s+/g, "-");
    if (!normalized) return;
    const recipe = recipes.find((item) => item.id === recipeId);
    if (!recipe) return;
    const nextTags = Array.from(new Set([...recipe.favorite_tags, normalized]));
    await saveRecipeTags(recipeId, nextTags);
    setTagDraft("");
  }

  async function removeTagFromRecipe(recipeId: number, tagToRemove: string) {
    const recipe = recipes.find((item) => item.id === recipeId);
    if (!recipe) return;
    await saveRecipeTags(
      recipeId,
      recipe.favorite_tags.filter((tag) => tag !== tagToRemove)
    );
  }

  const normalizedFilter = tagFilter.trim().replace(/^#+/, "").toLowerCase();
  const filteredRecipes = useMemo(() => {
    if (!normalizedFilter) return recipes;
    return recipes.filter((recipe) => {
      const inTitle = recipe.title.toLowerCase().includes(normalizedFilter);
      const inTags = recipe.favorite_tags.some((tag) => tag.includes(normalizedFilter));
      return inTitle || inTags;
    });
  }, [normalizedFilter, recipes]);

  return (
    <main className="app-wrap">
      <section className="shell">
        <div className="card detail-shell">
          <div className="detail-nav">
            <Link href="/" className="header-link-chip">Dashboard</Link>
            <Link href="/account" className="header-link-chip">Account</Link>
          </div>

          <div className="favorite-hero">
            <p className="eyebrow">Recipe notebook</p>
            <h1 className="title">Favorite Recipes</h1>
            <p className="subtitle">
              Keep your go-to dishes in one tidy place. Add optional hashtags like #breakfast or #quick so they are easier to revisit later.
            </p>
            <div className="favorite-summary-row">
              <div className="detail-stat-card">
                <span className="tiny-text">Saved recipes</span>
                <strong>{recipes.length}</strong>
              </div>
              <div className="detail-stat-card">
                <span className="tiny-text">Saved hashtags</span>
                <strong>{availableTags.length}</strong>
              </div>
            </div>
            <div className="favorite-filter-panel">
              <label className="tiny-text" htmlFor="favorite-tag-filter">
                Search by recipe name or hashtag
              </label>
              <input
                id="favorite-tag-filter"
                value={tagFilter}
                onChange={(e) => setTagFilter(e.target.value)}
                placeholder="Try #breakfast or orange"
              />
              {availableTags.length > 0 && (
                <div className="detail-tag-row">
                  {availableTags.map((tag) => (
                    <button
                      key={tag}
                      className={`detail-tag-pill detail-tag-pill-button${
                        normalizedFilter === tag ? " detail-tag-pill-active" : ""
                      }`}
                      onClick={() => setTagFilter(normalizedFilter === tag ? "" : `#${tag}`)}
                    >
                      #{tag}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {loading && (
            <div className="detail-state detail-state-loading">
              <p className="eyebrow">Recipe notebook</p>
              <h2>Loading favorites…</h2>
              <p className="muted-text">Pulling in the recipes you liked most recently.</p>
            </div>
          )}
          {error && (
            <div className="detail-state detail-state-error">
              <p className="eyebrow">Recipe notebook</p>
              <h2>Favorites unavailable</h2>
              <p className="error">{error}</p>
            </div>
          )}
          {message && !error && (
            <div className="app-alert app-alert-success">
              <p>{message}</p>
            </div>
          )}

          {!loading && !error && recipes.length === 0 && (
            <div className="detail-state">
              <p className="eyebrow">Recipe notebook</p>
              <h2>No favorites yet</h2>
              <p className="muted-text">
                Like a recipe from recommendations and it will show up here as part of your personal cookbook.
              </p>
              <div className="row-gap">
                <Link href="/" className="header-link-chip">Back to recommendations</Link>
              </div>
            </div>
          )}

          {!loading && !error && recipes.length > 0 && filteredRecipes.length === 0 && (
            <div className="detail-state">
              <p className="eyebrow">Recipe notebook</p>
              <h2>No favorites match that search</h2>
              <p className="muted-text">Try another recipe name or hashtag, or clear the filter to see everything again.</p>
            </div>
          )}

          {filteredRecipes.length > 0 && (
            <div className="recipe-grid favorite-grid">
              {filteredRecipes.map((recipe) => (
                <article key={recipe.id} className="recipe-card recipe-card-like favorite-card">
                  <RecipeCardImage src={recipe.image_url} alt={recipe.title} />

                  <div className="recipe-meta">
                    <div>
                      <h3>{recipe.title}</h3>
                      <p className="tiny-text">
                        {displayRecipeSourceName(recipe.source_name)}
                        {recipe.cuisine ? ` - ${recipe.cuisine}` : ""}
                      </p>
                    </div>
                    {typeof recipe.rating === "number" && (
                      <p className="tiny-text">Rating: {recipe.rating.toFixed(1)} / 5</p>
                    )}
                    <p className="tiny-text">
                      Time: {recipe.total_minutes ?? "N/A"} min
                      {recipe.prep_minutes ? ` | Prep ${recipe.prep_minutes}` : ""}
                      {recipe.cook_minutes ? ` | Cook ${recipe.cook_minutes}` : ""}
                    </p>
                    <div className="detail-tag-row">
                      <button
                        className="inventory-badge detail-badge-favorite favorite-toggle-button"
                        onClick={() => void removeFavorite(recipe.id)}
                      >
                        Favorited
                      </button>
                      {recipe.favorite_tags.map((tag) => (
                        <button
                          key={tag}
                          className="detail-tag-pill detail-tag-pill-button"
                          onClick={() => setTagFilter(`#${tag}`)}
                        >
                          #{tag}
                        </button>
                      ))}
                      {recipe.dietary_tags.slice(0, 2).map((tag) => (
                        <span key={tag} className="detail-tag-pill">{tag}</span>
                      ))}
                    </div>
                    <div className="favorite-tag-editor">
                      <div className="row-gap">
                        <button
                          className="header-link-chip"
                          onClick={() => {
                            setEditingRecipeId((prev) => (prev === recipe.id ? null : recipe.id));
                            setTagDraft("");
                          }}
                        >
                          {editingRecipeId === recipe.id ? "Done tagging" : "Edit hashtags"}
                        </button>
                      </div>
                      {editingRecipeId === recipe.id && (
                        <div className="favorite-tag-editor-panel">
                          <p className="tiny-text">
                            Add optional hashtags to organize this recipe inside Favorites. Reuse existing tags or make your own.
                          </p>
                          <div className="favorite-tag-input-row">
                            <input
                              value={tagDraft}
                              onChange={(e) => setTagDraft(e.target.value)}
                              placeholder="#breakfast"
                            />
                            <button onClick={() => void addTagToRecipe(recipe.id, tagDraft)}>Add tag</button>
                          </div>
                          <div className="detail-tag-row">
                            {recipe.favorite_tags.map((tag) => (
                              <button
                                key={tag}
                                className="detail-tag-pill detail-tag-pill-button"
                                onClick={() => void removeTagFromRecipe(recipe.id, tag)}
                              >
                                #{tag} ×
                              </button>
                            ))}
                          </div>
                          {availableTags.length > 0 && (
                            <div className="detail-tag-row">
                              {availableTags
                                .filter((tag) => !recipe.favorite_tags.includes(tag))
                                .slice(0, 8)
                                .map((tag) => (
                                  <button
                                    key={tag}
                                    className="detail-tag-pill detail-tag-pill-button"
                                    onClick={() => void addTagToRecipe(recipe.id, tag)}
                                  >
                                    Use #{tag}
                                  </button>
                                ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="row-gap">
                      <Link href={`/recipes/${recipe.id}`} className="header-link-chip">Open Recipe</Link>
                      <a
                        href={buildAllrecipesSearchUrl(recipe.title)}
                        target="_blank"
                        rel="noreferrer"
                        className="header-link-chip"
                      >
                        Search on Allrecipes
                      </a>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
          <p className="tiny-text">
            Recipe discovery data courtesy of the MIT-licensed Kaggle All Recipe Dataset, derived from Allrecipes.com content.
          </p>
        </div>
      </section>
    </main>
  );
}
