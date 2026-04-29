"""
backend/rag/retriever.py
Stage 3: Hybrid retrieval over the CMU movie corpus.

Consumed by Person B (chat orchestrator) and Person C (movies endpoints).
All method signatures match the interface contract exactly.
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

# Allow running from project root or backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import CHROMA_DB_PATH, BM25_INDEX_PATH

EMBEDDING_MODEL   = "all-MiniLM-L6-v2"
CHROMA_COLLECTION = "movies"


class MovieRetriever:
    """
    Initialized once at app startup. Loads ChromaDB and BM25 index from disk.
    All methods return lists of MovieResult dicts as defined in the interface contract.
    """

    def __init__(
        self,
        chroma_db_path: str = CHROMA_DB_PATH,
        bm25_index_path: str = BM25_INDEX_PATH,
    ):
        """
        Load the pre-built ChromaDB collection and BM25 index.
        Load the sentence-transformer embedding model.
        """
        from sentence_transformers import SentenceTransformer
        import chromadb

        # Embedding model
        self._model = SentenceTransformer(EMBEDDING_MODEL)

        # ChromaDB
        client = chromadb.PersistentClient(path=chroma_db_path)
        self._collection = client.get_collection(CHROMA_COLLECTION)

        # BM25
        with open(bm25_index_path, "rb") as f:
            payload = pickle.load(f)

        self._bm25         = payload["bm25"]
        self._bm25_title   = payload["bm25_title"]
        self._movie_ids    = payload["movie_ids"]        # list[str], one per doc
        self._movies_lookup: dict[str, dict] = payload["movies_lookup"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return text.lower().split()

    @staticmethod
    def _chroma_to_movie_result(movie_id: str, meta: dict, score: float) -> dict:
        return {
            "movie_id":     movie_id,
            "title":        meta.get("title", ""),
            "year":         meta.get("year") if meta.get("year", -1) != -1 else None,
            "genres":       json.loads(meta.get("genres", "[]")),
            "countries":    json.loads(meta.get("countries", "[]")),
            "runtime":      meta.get("runtime") if meta.get("runtime", -1.0) != -1.0 else None,
            "plot_summary": meta.get("plot_summary", ""),
            "score":        round(float(score), 6),
        }

    @staticmethod
    def _lookup_to_movie_result(movie: dict, score: float) -> dict:
        return {**movie, "score": round(float(score), 6)}

    # ------------------------------------------------------------------
    # Dense retrieval
    # ------------------------------------------------------------------

    def retrieve_dense(self, query_text: str, top_k: int = 50) -> list[dict]:
        """
        Embed query_text using all-MiniLM-L6-v2, query ChromaDB.
        Returns list of MovieResult dicts sorted by cosine similarity descending.
        Score is cosine similarity normalized to 0-1.
        """
        query_embedding = self._model.encode(query_text).tolist()

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            include=["metadatas", "distances"],
        )

        movie_results = []
        for movie_id, dist, meta in zip(
            results["ids"][0],
            results["distances"][0],
            results["metadatas"][0],
        ):
            # ChromaDB cosine returns distance = 1 - similarity
            similarity = max(0.0, min(1.0, 1.0 - dist))
            movie_results.append(
                self._chroma_to_movie_result(movie_id, meta, similarity)
            )

        return movie_results  # already sorted by similarity desc

    # ------------------------------------------------------------------
    # Sparse retrieval (BM25)
    # ------------------------------------------------------------------

    def retrieve_sparse(self, query_text: str, top_k: int = 50) -> list[dict]:
        """
        Tokenize query_text, query BM25 index.
        Returns list of MovieResult dicts sorted by BM25 score descending.
        Score is BM25 score normalized to 0-1 (divide by max score in results).
        """
        import numpy as np

        tokens     = self._tokenize(query_text)
        raw_scores = self._bm25.get_scores(tokens)

        top_indices = np.argsort(raw_scores)[::-1][:top_k]
        max_score   = float(raw_scores[top_indices[0]]) if len(top_indices) > 0 else 1.0
        if max_score == 0.0:
            max_score = 1.0

        results = []
        for idx in top_indices:
            score = float(raw_scores[idx])
            if score <= 0:
                break
            movie_id = self._movie_ids[idx]
            movie    = self._movies_lookup.get(movie_id)
            if movie is None:
                continue
            results.append(self._lookup_to_movie_result(movie, score / max_score))

        return results

    # ------------------------------------------------------------------
    # Hybrid retrieval (RRF fusion)
    # ------------------------------------------------------------------

    def retrieve_hybrid(
        self,
        query_text: str,
        top_k: int = 50,
        rrf_k: int = 60,
    ) -> list[dict]:
        """
        Run both retrieve_dense and retrieve_sparse.
        Fuse results using Reciprocal Rank Fusion:
            rrf_score(d) = sum(1 / (rrf_k + rank_i(d))) for each method
        Returns list of MovieResult dicts sorted by RRF score descending.
        Score field contains the RRF score. Deduplicates by movie_id.
        """
        dense_results  = self.retrieve_dense(query_text, top_k=top_k)
        sparse_results = self.retrieve_sparse(query_text, top_k=top_k)

        # 1-based rank maps
        dense_rank  = {r["movie_id"]: i + 1 for i, r in enumerate(dense_results)}
        sparse_rank = {r["movie_id"]: i + 1 for i, r in enumerate(sparse_results)}

        # Metadata lookup — dense overwrites sparse (same data, prefer dense)
        meta_lookup: dict[str, dict] = {}
        for r in sparse_results:
            meta_lookup[r["movie_id"]] = r
        for r in dense_results:
            meta_lookup[r["movie_id"]] = r

        # RRF scores over union of both lists
        all_ids = set(dense_rank) | set(sparse_rank)
        rrf_scores: dict[str, float] = {}
        for mid in all_ids:
            score = 0.0
            if mid in dense_rank:
                score += 1.0 / (rrf_k + dense_rank[mid])
            if mid in sparse_rank:
                score += 1.0 / (rrf_k + sparse_rank[mid])
            rrf_scores[mid] = score

        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:top_k]

        results = []
        for mid in sorted_ids:
            entry = meta_lookup[mid].copy()
            entry["score"] = round(rrf_scores[mid], 6)
            results.append(entry)

        return results

    # ------------------------------------------------------------------
    # Single-movie lookup
    # ------------------------------------------------------------------

    def retrieve_by_movie_id(self, movie_id: str) -> dict | None:
        """
        Look up a single movie by its movie_id.
        Returns a MovieResult dict or None if not found.
        Used when Person B needs to look up a reference movie's metadata.
        """
        movie = self._movies_lookup.get(movie_id)
        if movie is not None:
            return self._lookup_to_movie_result(movie, 1.0)

        # Fallback to ChromaDB
        try:
            result = self._collection.get(ids=[movie_id], include=["metadatas"])
            if result["ids"]:
                return self._chroma_to_movie_result(movie_id, result["metadatas"][0], 1.0)
        except Exception:
            pass

        return None

    # ------------------------------------------------------------------
    # Title search (watchlist "Add Movie" feature)
    # ------------------------------------------------------------------

    def search_by_title(self, title_query: str, top_k: int = 10) -> list[dict]:
        """
        Simple title search for the "add to watchlist" feature.
        Uses BM25 over title field only (not full combined_text).
        Returns list of MovieResult dicts.
        """
        import numpy as np

        tokens     = self._tokenize(title_query)
        raw_scores = self._bm25_title.get_scores(tokens)

        top_indices = np.argsort(raw_scores)[::-1][:top_k]
        max_score   = float(raw_scores[top_indices[0]]) if len(top_indices) > 0 else 1.0
        if max_score == 0.0:
            max_score = 1.0

        results = []
        for idx in top_indices:
            score    = float(raw_scores[idx])
            movie_id = self._movie_ids[idx]
            movie    = self._movies_lookup.get(movie_id)
            if movie is None:
                continue
            results.append(self._lookup_to_movie_result(movie, score / max_score))

        return results
