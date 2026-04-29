"""
scripts/process_data.py
Parses CMU corpus → data/processed/movies.json

Run from project root:
    python scripts/process_data.py
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from config import RAW_DATA_DIR, MOVIES_JSON_PATH

METADATA_PATH  = RAW_DATA_DIR / "movie.metadata.tsv"
SUMMARIES_PATH = RAW_DATA_DIR / "plot_summaries.txt"
MIN_PLOT_CHARS = 50


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_freebase_json(raw: str) -> list[str]:
    """CMU encodes multi-valued fields as {"/m/abc": "Drama", ...}"""
    if not raw or raw.strip() in ("", "{}"):
        return []
    try:
        return list(json.loads(raw).values())
    except (json.JSONDecodeError, TypeError):
        return []


def parse_year(date_str: str) -> int | None:
    if not date_str:
        return None
    m = re.search(r"\b(1[89]\d{2}|20[0-2]\d)\b", date_str)
    return int(m.group(1)) if m else None


def parse_runtime(s: str) -> float | None:
    try:
        v = float(s)
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


# ------------------------------------------------------------------
# Loaders
# ------------------------------------------------------------------

def load_summaries() -> dict[str, str]:
    print(f"Loading summaries from {SUMMARIES_PATH}...")
    summaries: dict[str, str] = {}
    with open(SUMMARIES_PATH, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t", 1)
            if len(parts) != 2:
                continue
            mid, plot = parts
            plot = clean_text(plot)
            if len(plot) >= MIN_PLOT_CHARS:
                summaries[mid.strip()] = plot
    print(f"  {len(summaries):,} summaries loaded")
    return summaries


def load_metadata() -> dict[str, dict]:
    """
    Columns: 0=WikiID 1=FreebaseID 2=Title 3=ReleaseDate
             4=BoxOffice 5=Runtime 6=Languages 7=Countries 8=Genres
    """
    print(f"Loading metadata from {METADATA_PATH}...")
    metadata: dict[str, dict] = {}
    with open(METADATA_PATH, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9:
                continue
            mid = parts[0].strip()
            if not mid:
                continue
            metadata[mid] = {
                "title":        clean_text(parts[2]) if parts[2] else "Unknown",
                "release_date": parts[3].strip(),
                "runtime_raw":  parts[5].strip(),
                "countries_raw":parts[7].strip(),
                "genres_raw":   parts[8].strip(),
            }
    print(f"  {len(metadata):,} metadata entries loaded")
    return metadata


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    for p in (METADATA_PATH, SUMMARIES_PATH):
        if not p.exists():
            print(f"ERROR: {p} not found. Run scripts/download_data.sh first.")
            sys.exit(1)

    MOVIES_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

    summaries = load_summaries()
    metadata  = load_metadata()

    print("Joining...")
    movies: list[dict] = []
    for mid, plot in summaries.items():
        meta = metadata.get(mid)
        if meta is None:
            continue

        title    = meta["title"]
        year     = parse_year(meta["release_date"])
        genres   = parse_freebase_json(meta["genres_raw"])
        countries= parse_freebase_json(meta["countries_raw"])
        runtime  = parse_runtime(meta["runtime_raw"])

        year_str   = f" ({year})" if year else ""
        genres_str = ", ".join(genres) if genres else "Unknown"
        combined   = f"{title}{year_str} | Genres: {genres_str} | {plot}"

        movies.append({
            "movie_id":      mid,
            "title":         title,
            "year":          year,
            "genres":        genres,
            "countries":     countries,
            "runtime":       runtime,
            "plot_summary":  plot,
            "combined_text": combined,
        })

    print(f"  {len(movies):,} movies joined")
    with open(MOVIES_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)
    print(f"Done → {MOVIES_JSON_PATH}")


if __name__ == "__main__":
    main()
