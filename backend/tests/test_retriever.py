"""
backend/tests/test_retriever.py
Tests RRF fusion math with mocked retrieve_dense / retrieve_sparse.
Zero disk I/O — runs in milliseconds.

Run: pytest backend/tests/test_retriever.py -v
"""

from unittest.mock import MagicMock


def _movie(mid, score=0.5):
    return {"movie_id": mid, "title": f"Movie {mid}", "year": 2000,
            "genres": [], "countries": [], "runtime": None,
            "plot_summary": "", "score": score}


def _make_retriever():
    from rag.retriever import MovieRetriever
    r = object.__new__(MovieRetriever)
    r._model       = MagicMock()
    r._collection  = MagicMock()
    r._bm25        = MagicMock()
    r._bm25_title  = MagicMock()
    r._movie_ids   = []
    r._movies_lookup = {}
    return r


def _hybrid(retriever, dense_list, sparse_list, rrf_k=60, top_k=50):
    retriever.retrieve_dense  = MagicMock(return_value=dense_list)
    retriever.retrieve_sparse = MagicMock(return_value=sparse_list)
    return retriever.retrieve_hybrid("test", top_k=top_k, rrf_k=rrf_k)


class TestRRF:

    def setup_method(self):
        self.r = _make_retriever()

    def test_score_both_rank1(self):
        results = _hybrid(self.r, [_movie("A")], [_movie("A")], rrf_k=60)
        expected = 2 / (60 + 1)
        assert abs(results[0]["score"] - expected) < 1e-6

    def test_dense_only_score(self):
        results = _hybrid(self.r, [_movie("A"), _movie("B")], [_movie("C")], rrf_k=60)
        by_id = {m["movie_id"]: m["score"] for m in results}
        assert abs(by_id["A"] - 1 / 61) < 1e-6
        assert abs(by_id["B"] - 1 / 62) < 1e-6

    def test_combined_rank_beats_single(self):
        # A: dense rank1 only → 1/61 ≈ 0.01639
        # B: dense rank2 + sparse rank1 → 1/62 + 1/61 ≈ 0.03278
        # B should rank higher than A
        dense  = [_movie("A"), _movie("B")]
        sparse = [_movie("B"), _movie("C"), _movie("A")]
        results = _hybrid(self.r, dense, sparse, rrf_k=60)
        ids = [m["movie_id"] for m in results]
        assert ids.index("B") < ids.index("A")

    def test_deduplication(self):
        results = _hybrid(self.r, [_movie("A"), _movie("B")], [_movie("A"), _movie("C")])
        ids = [m["movie_id"] for m in results]
        assert len(ids) == len(set(ids))

    def test_union_of_both_lists(self):
        results = _hybrid(self.r, [_movie("A"), _movie("B")], [_movie("C"), _movie("D")])
        assert {m["movie_id"] for m in results} == {"A", "B", "C", "D"}

    def test_top_k(self):
        dense  = [_movie(str(i)) for i in range(20)]
        sparse = [_movie(str(i + 10)) for i in range(20)]
        results = _hybrid(self.r, dense, sparse, top_k=5)
        assert len(results) <= 5

    def test_empty_dense(self):
        results = _hybrid(self.r, [], [_movie("A"), _movie("B")])
        assert {m["movie_id"] for m in results} == {"A", "B"}

    def test_empty_sparse(self):
        results = _hybrid(self.r, [_movie("A"), _movie("B")], [])
        assert {m["movie_id"] for m in results} == {"A", "B"}

    def test_both_empty(self):
        assert _hybrid(self.r, [], []) == []

    def test_custom_rrf_k(self):
        results = _hybrid(self.r, [_movie("A")], [_movie("A")], rrf_k=1)
        assert abs(results[0]["score"] - 2 / (1 + 1)) < 1e-6
