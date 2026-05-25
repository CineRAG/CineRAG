"""
scripts/generate_eval_queries.py
Generates a diverse eval query set from the actual movie database.
Run from project root: python scripts/generate_eval_queries.py
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from config import MOVIES_JSON_PATH

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
MODEL           = "gpt-oss:120b-cloud"
OUTPUT_PATH     = Path(__file__).resolve().parent.parent / "data" / "eval" / "queries2.json"
SAMPLES_PER_GENRE = 5
MIN_PLOT_LEN    = 200

TARGET_GENRES = [
    "Drama", "Comedy", "Thriller", "Action", "Romance", "Horror",
    "Science Fiction", "Animation", "Crime", "Adventure", "Mystery",
    "Biography", "Fantasy", "War", "Western",
]


def sample_movies(movies: list[dict]) -> list[dict]:
    sampled: dict[str, dict] = {}
    for genre in TARGET_GENRES:
        candidates = [
            m for m in movies
            if any(genre.lower() in g.lower() for g in m.get("genres", []))
            and len(m.get("plot_summary", "")) >= MIN_PLOT_LEN
            and m.get("year") is not None
        ]
        if not candidates:
            continue

        # Stratify by era within each genre
        eras: dict[str, list] = {"pre-1980": [], "1980s-1990s": [], "2000s+": []}
        for m in candidates:
            year = m["year"]
            if year < 1980:
                eras["pre-1980"].append(m)
            elif year < 2000:
                eras["1980s-1990s"].append(m)
            else:
                eras["2000s+"].append(m)

        per_era = max(1, SAMPLES_PER_GENRE // 3)
        for era_movies in eras.values():
            if era_movies:
                for m in random.sample(era_movies, min(per_era, len(era_movies))):
                    sampled[m["movie_id"]] = m

    return list(sampled.values())


def generate_query(movie: dict) -> str | None:
    prompt = (
        "You are building a movie retrieval evaluation dataset.\n\n"
        "Given the movie details below, write a natural search query a user might type "
        "when looking for this movie WITHOUT knowing the title.\n\n"
        "Rules:\n"
        "- 1-2 sentences only\n"
        "- Describe plot themes, mood, setting, or character dynamics\n"
        "- Do NOT mention the movie title\n"
        "- Do NOT copy sentences from the plot verbatim\n"
        "- Sound like a natural user request\n\n"
        f"Title: {movie['title']} ({movie.get('year', '?')})\n"
        f"Genres: {', '.join(movie.get('genres', []))}\n"
        f"Plot: {movie['plot_summary'][:500]}\n\n"
        "Write ONLY the query, nothing else."
    )
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": False,
                "options": {"temperature": 0.7}},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["response"].strip()
    except Exception as e:
        print(f"  LLM error for {movie['title']}: {e}")
        return None


def main():
    random.seed(42)

    print(f"Loading movies from {MOVIES_JSON_PATH}...")
    with open(MOVIES_JSON_PATH, encoding="utf-8") as f:
        movies = json.load(f)
    print(f"  {len(movies):,} movies loaded")

    print("Sampling diverse movies...")
    sampled = sample_movies(movies)
    print(f"  {len(sampled)} movies sampled across genres and eras")

    queries = []
    for i, movie in enumerate(sampled, 1):
        print(f"  [{i}/{len(sampled)}] {movie['title']} ({movie.get('year')})")
        query_text = generate_query(movie)
        if query_text:
            queries.append({
                "query_id":           f"q{i:03d}",
                "query":              query_text,
                "expected_movie_ids": [movie["movie_id"]],
                "title":              movie["title"],
                "year":               movie.get("year"),
                "genres":             movie.get("genres", []),
            })
            print(f"    → {query_text[:80]}...")
        time.sleep(0.3)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(queries, f, indent=2, ensure_ascii=False)
    print(f"\nDone — {len(queries)} queries saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()