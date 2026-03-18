"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

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
  nutrition: Record<string, string | number | boolean | null>;
  instructions_text?: string | null;
  ingredients: RecipeIngredient[];
};

function buildAllrecipesSearchUrl(title: string): string {
  return `https://www.allrecipes.com/search?q=${encodeURIComponent(title)}`;
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
  const [token, setToken] = useState("");
  const [recipe, setRecipe] = useState<RecipeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  useEffect(() => {
    const savedToken = localStorage.getItem("smartpantry_token");
    if (!savedToken) {
      setError("Log in first to view recipe details.");
      setLoading(false);
      return;
    }
    setToken(savedToken);
  }, []);

  useEffect(() => {
    if (!token || !params?.id) return;

    async function loadRecipe() {
      setLoading(true);
      const res = await fetch(`${API_BASE}/recipes/${params.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError(`Recipe ${params.id} could not be loaded.`);
        setLoading(false);
        return;
      }
      setRecipe((await res.json()) as RecipeDetail);
      setLoading(false);
    }

    void loadRecipe();
  }, [params?.id, token]);

  async function submitFeedback(feedbackType: "like" | "dislike") {
    if (!token || !recipe) return;
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

  return (
    <main className="app-wrap">
      <section className="shell">
        <div className="card detail-shell">
          <div className="row-gap">
            <Link href="/">Back to Dashboard</Link>
            <Link href="/recipes/book">Saved Recipes</Link>
            {recipe && (
              <a href={buildAllrecipesSearchUrl(recipe.title)} target="_blank" rel="noreferrer">
                Search on Allrecipes
              </a>
            )}
          </div>

          {loading && <p className="muted-text">Loading recipe...</p>}
          {error && <p className="error">{error}</p>}

          {recipe && (
            <>
              <div className="detail-hero">
                <div>
                  <h1 className="title">{recipe.title}</h1>
                  <p className="subtitle">
                    {recipe.source_name || "Unknown source"}
                    {recipe.cuisine ? ` - ${recipe.cuisine}` : ""}
                  </p>
                  {typeof recipe.rating === "number" && (
                    <p className="tiny-text">Rating: {recipe.rating.toFixed(1)} / 5</p>
                  )}
                  {recipe.current_feedback && (
                    <p className="tiny-text">
                      Saved state: {recipe.current_feedback === "like" ? "Liked" : "Disliked"}
                    </p>
                  )}
                  <p className="tiny-text">
                    Total {recipe.total_minutes ?? "N/A"} min
                    {recipe.prep_minutes ? ` | Prep ${recipe.prep_minutes}` : ""}
                    {recipe.cook_minutes ? ` | Cook ${recipe.cook_minutes}` : ""}
                    {recipe.servings ? ` | Servings ${recipe.servings}` : ""}
                  </p>
                </div>

                <RecipeDetailImage src={recipe.image_url} alt={recipe.title} />
              </div>

              <div className="row-gap">
                <button
                  className={recipe.current_feedback === "like" ? "feedback-button-liked" : undefined}
                  onClick={() => void submitFeedback("like")}
                  disabled={feedbackLoading}
                >
                  {recipe.current_feedback === "like" ? "Liked" : "Like"}
                </button>
                <button
                  className={recipe.current_feedback === "dislike" ? "feedback-button-disliked" : undefined}
                  onClick={() => void submitFeedback("dislike")}
                  disabled={feedbackLoading}
                >
                  Dislike
                </button>
              </div>

              {recipe.dietary_tags.length > 0 && (
                <p className="tiny-text">Tags: {recipe.dietary_tags.join(", ")}</p>
              )}

              <div className="detail-grid">
                <div className="card">
                  <h2>Ingredients</h2>
                  <div className="list-col">
                    {recipe.ingredients.map((ingredient, index) => (
                      <article key={`${ingredient.ingredient_normalized}-${index}`} className="list-item">
                        <div>
                          <strong>{ingredient.ingredient_raw}</strong>
                          <p className="tiny-text">{ingredient.ingredient_normalized}</p>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>

                <div className="card">
                  <h2>Details</h2>
                  {recipe.instructions_text ? (
                    <p className="muted-text">{recipe.instructions_text}</p>
                  ) : (
                    <p className="muted-text">
                      This recipe dataset provides ingredients, time, rating, and image metadata for
                      discovery. Use the Allrecipes search link above to find the closest live recipe page.
                    </p>
                  )}

                  {Object.keys(recipe.nutrition || {}).length > 0 && (
                    <>
                      <h3 className="title" style={{ fontSize: "1.1rem", marginTop: "1rem" }}>
                        Nutrition
                      </h3>
                      <div className="list-col">
                        {Object.entries(recipe.nutrition).map(([key, value]) => (
                          <article key={key} className="list-item">
                            <strong>{key}</strong>
                            <span className="muted-text">{String(value)}</span>
                          </article>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
