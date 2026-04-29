"""
scripts/index_movies.py
Builds ChromaDB + BM25 index from data/processed/movies.json.
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from config import MOVIES_JSON_PATH, CHROMA_DB_PATH, BM25_INDEX_PATH

EMBEDDING_MODEL   = "all-MiniLM-L6-v2"
CHROMA_COLLECTION = "movies"
BATCH_SIZE        = 512


def load_movies() -> list[dict]:
    print(f"Loading {MOVIES_JSON_PATH}...")
    with open(MOVIES_JSON_PATH, encoding="utf-8") as f:
        movies = json.load(f)
    print(f"  {len(movies):,} movies loaded")
    return movies


def build_chroma(movies: list[dict]):
    import chromadb
    from sentence_transformers import SentenceTransformer
    from tqdm import tqdm

    print(f"\n==> Building ChromaDB index at {CHROMA_DB_PATH}")
    Path(CHROMA_DB_PATH).mkdir(parents=True, exist_ok=True)

    model  = SentenceTransformer(EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # Clean rebuild
    try:
        client.delete_collection(CHROMA_COLLECTION)
        print("    Deleted existing collection.")
    except Exception:
        pass

    collection = client.create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    total     = len(movies)
    n_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_num, start in enumerate(tqdm(range(0, total, BATCH_SIZE), total=n_batches, desc="Indexing batches"), start=1):
        batch = movies[start: start + BATCH_SIZE]

        ids       = [m["movie_id"] for m in batch]
        texts     = [m["combined_text"] for m in batch]
        metadatas = [
            {
                "title":        m["title"],
                "year":         m["year"] if m["year"] is not None else -1,
                "genres":       json.dumps(m["genres"]),
                "countries":    json.dumps(m["countries"]),
                "runtime":      m["runtime"] if m["runtime"] is not None else -1.0,
                "plot_summary": m["plot_summary"],
            }
            for m in batch
        ]

        embeddings = model.encode(texts, show_progress_bar=False, batch_size=64).tolist()
        collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)

    print(f"\n    Done — {collection.count():,} documents indexed")


def build_bm25(movies: list[dict]):
    from rank_bm25 import BM25Okapi
    from tqdm import tqdm

    print(f"\n==> Building BM25 index...")

    def tok(text: str) -> list[str]:
        return text.lower().split()

    movie_ids  = [m["movie_id"] for m in movies]

    print("    Tokenizing combined_text...")
    corpus_tok = [tok(m["combined_text"]) for m in tqdm(movies, desc="BM25 corpus")]

    print("    Tokenizing titles...")
    title_tok  = [tok(m["title"]) for m in tqdm(movies, desc="BM25 titles")]

    print("    Fitting BM25Okapi...")
    bm25       = BM25Okapi(corpus_tok)
    bm25_title = BM25Okapi(title_tok)

    movies_lookup = {
        m["movie_id"]: {
            "movie_id":     m["movie_id"],
            "title":        m["title"],
            "year":         m["year"],
            "genres":       m["genres"],
            "countries":    m["countries"],
            "runtime":      m["runtime"],
            "plot_summary": m["plot_summary"],
        }
        for m in movies
    }

    payload = {
        "bm25":          bm25,
        "bm25_title":    bm25_title,
        "movie_ids":     movie_ids,
        "movies_lookup": movies_lookup,
    }

    Path(BM25_INDEX_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(payload, f)

    size_mb = Path(BM25_INDEX_PATH).stat().st_size / 1e6
    print(f"    Saved to {BM25_INDEX_PATH} ({size_mb:.1f} MB)")


def main():
    if not MOVIES_JSON_PATH.exists():
        print(f"ERROR: {MOVIES_JSON_PATH} not found. Run process_data.py first.")
        sys.exit(1)

    movies = load_movies()
    build_chroma(movies)
    build_bm25(movies)

    print("\n==> All indices built.")
    print(f"    ChromaDB : {CHROMA_DB_PATH}")
    print(f"    BM25     : {BM25_INDEX_PATH}")


if __name__ == "__main__":
    main()
