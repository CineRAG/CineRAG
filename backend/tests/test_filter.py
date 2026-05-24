"""
backend/tests/test_filter.py
Run: pytest backend/tests/test_filter.py -v
"""

from rag.filter import filter_watched


def _movies(*ids):
    return [{"movie_id": mid, "title": f"Movie {mid}", "score": 1.0} for mid in ids]


class TestFilterWatched:

    def test_removes_watched(self):
        result = filter_watched(_movies("A", "B", "C"), {"B"})
        assert [m["movie_id"] for m in result] == ["A", "C"]

    def test_preserves_order(self):
        result = filter_watched(_movies("X", "Y", "Z"), {"Y"})
        assert [m["movie_id"] for m in result] == ["X", "Z"]

    def test_empty_watched_returns_all(self):
        candidates = _movies("A", "B", "C")
        assert filter_watched(candidates, set()) == candidates

    def test_all_watched_returns_empty(self):
        assert filter_watched(_movies("A", "B"), {"A", "B"}) == []

    def test_empty_candidates_returns_empty(self):
        assert filter_watched([], {"A"}) == []

    def test_no_overlap_returns_all(self):
        candidates = _movies("A", "B")
        assert filter_watched(candidates, {"X"}) == candidates

    def test_does_not_mutate_input(self):
        candidates = _movies("A", "B", "C")
        filter_watched(candidates, {"B"})
        assert len(candidates) == 3

    def test_scores_preserved(self):
        candidates = [{"movie_id": "A", "score": 0.9}, {"movie_id": "B", "score": 0.8}]
        result = filter_watched(candidates, {"B"})
        assert result[0]["score"] == 0.9


class TestFilterExcluded:

    def test_removes_excluded_ids(self):
        from rag.filter import filter_excluded

        result = filter_excluded(_movies("A", "B", "C"), {"B", "C"})
        assert [m["movie_id"] for m in result] == ["A"]

    def test_empty_excluded_returns_all(self):
        from rag.filter import filter_excluded

        candidates = _movies("A", "B")
        assert filter_excluded(candidates, set()) == candidates
