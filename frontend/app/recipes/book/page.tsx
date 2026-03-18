"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

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
  nutrition: Record<string, string | number | boolean | null>;
};

function buildAllrecipesSearchUrl(title: string): string {
  return `https://www.allrecipes.com/search?q=${encodeURIComponent(title)}`;
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
  const [token, setToken] = useState("");
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const savedToken = localStorage.getItem("smartpantry_token");
    if (!savedToken) {
      setError("Log in first to view saved recipes.");
      setLoading(false);
      return;
    }
    setToken(savedToken);
  }, []);

  useEffect(() => {
    if (!token) return;

    async function loadSavedRecipes() {
      setLoading(true);
      const res = await fetch(`${API_BASE}/recipes/book`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError(`Saved recipes could not be loaded (${res.status}).`);
        setLoading(false);
        return;
      }
      const payload = (await res.json()) as { results: RecipeSummary[] };
      setRecipes(payload.results);
      setLoading(false);
    }

    void loadSavedRecipes();
  }, [token]);

  return (
    <main className="app-wrap">
      <section className="shell">
        <div className="card detail-shell">
          <div className="row-gap">
            <Link href="/">Back to Dashboard</Link>
          </div>

          <div>
            <h1 className="title">Saved Recipes</h1>
            <p className="subtitle">Your liked recipes, kept in one place for easy revisiting.</p>
          </div>

          {loading && <p className="muted-text">Loading saved recipes...</p>}
          {error && <p className="error">{error}</p>}

          {!loading && !error && recipes.length === 0 && (
            <p className="muted-text">No saved recipes yet. Like a recipe from recommendations to add it here.</p>
          )}

          {recipes.length > 0 && (
            <div className="recipe-grid">
              {recipes.map((recipe) => (
                <article key={recipe.id} className="recipe-card">
                  <RecipeCardImage src={recipe.image_url} alt={recipe.title} />

                  <div className="recipe-meta">
                    <div>
                      <h3>{recipe.title}</h3>
                      <p className="tiny-text">
                        {recipe.source_name || "Unknown source"}
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
                    <p className="tiny-text">Saved state: Liked</p>
                    <div className="row-gap">
                      <Link href={`/recipes/${recipe.id}`}>View Details</Link>
                      <a
                        href={buildAllrecipesSearchUrl(recipe.title)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Search on Allrecipes
                      </a>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
