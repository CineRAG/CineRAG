"""
backend/tests/test_reranker.py
Run: pytest backend/tests/test_reranker.py -v
"""

from rag.reranker import rerank, _parse_era_range


def _intent(genre=None, era=None, exclusions=None, mood=None):
    return {"intent": "find_by_mood", "reference_movie": None,
            "attributes": {"genre": genre, "era": era, "exclusions": exclusions, "mood": mood},
            "refinement": None}


def _movie(mid, year=None, genres=None, score=0.5):
    return {"movie_id": mid, "title": f"Movie {mid}", "year": year,
            "genres": genres or [], "score": score}


class TestParseEraRange:
    def test_1990s(self):   assert _parse_era_range("1990s") == (1990, 1999)
    def test_2000s(self):   assert _parse_era_range("2000s") == (2000, 2009)
    def test_90s(self):     assert _parse_era_range("90s")   == (1990, 1999)
    def test_80s(self):     assert _parse_era_range("80s")   == (1980, 1989)
    def test_00s(self):     assert _parse_era_range("00s")   == (2000, 2009)
    def test_unknown(self): assert _parse_era_range("recent") is None


class TestRerank:

    def test_genre_boost(self):
        movies = [_movie("A", genres=["Drama"], score=0.5),
                  _movie("B", genres=["Sci-Fi"], score=0.5)]
        result = rerank(movies, _intent(genre="sci-fi"), top_k=2)
        assert result[0]["movie_id"] == "B"

    def test_era_boost(self):
        movies = [_movie("A", year=2005, score=0.5),
                  _movie("B", year=1995, score=0.5)]
        result = rerank(movies, _intent(era="1990s"), top_k=2)
        assert result[0]["movie_id"] == "B"

    def test_cumulative_boost(self):
        movies = [_movie("A", year=1995, genres=["Sci-Fi"], score=0.5),
                  _movie("B", year=1995, genres=["Drama"],  score=0.5),
                  _movie("C", year=2005, genres=["Sci-Fi"], score=0.5)]
        result = rerank(movies, _intent(genre="sci-fi", era="1990s"), top_k=3)
        assert result[0]["movie_id"] == "A"

    def test_exclusion_removes(self):
        movies = [_movie("A", genres=["Horror"], score=0.9),
                  _movie("B", genres=["Drama"],  score=0.5)]
        result = rerank(movies, _intent(exclusions="no horror"), top_k=2)
        assert all(m["movie_id"] != "A" for m in result)

    def test_no_attributes_preserves_order(self):
        movies = [_movie("A", score=0.9), _movie("B", score=0.7), _movie("C", score=0.5)]
        result = rerank(movies, _intent(), top_k=3)
        assert [m["movie_id"] for m in result] == ["A", "B", "C"]

    def test_top_k_respected(self):
        movies = [_movie(str(i), score=1.0 - i * 0.05) for i in range(10)]
        assert len(rerank(movies, _intent(), top_k=3)) == 3

    def test_empty_candidates(self):
        assert rerank([], _intent(genre="drama"), top_k=5) == []

    def test_genre_score_formula(self):
        movies = [_movie("A", genres=["Drama"], score=0.5)]
        result = rerank(movies, _intent(genre="drama"), top_k=1)
        assert abs(result[0]["score"] - 0.5 * 1.20) < 1e-5

    def test_era_score_formula(self):
        movies = [_movie("A", year=1993, score=0.6)]
        result = rerank(movies, _intent(era="1990s"), top_k=1)
        assert abs(result[0]["score"] - 0.6 * 1.15) < 1e-5
