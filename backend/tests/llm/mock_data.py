"""Mock retrieval data — copied verbatim from Contest/interface_contract.md §8."""
from __future__ import annotations

MOCK_RETRIEVAL_RESULTS = [
    {
        "movie_id": "975900",
        "title": "Titanic",
        "year": 1997,
        "genres": ["Drama", "Romance"],
        "countries": ["United States"],
        "runtime": 194.0,
        "plot_summary": (
            "A seventeen-year-old aristocrat falls in love with a kind but poor "
            "artist aboard the luxurious, ill-fated R.M.S. Titanic. When the ship "
            "strikes an iceberg, their love is tested as they fight for survival "
            "amidst the chaos of the sinking vessel."
        ),
        "score": 0.92,
    },
    {
        "movie_id": "234567",
        "title": "The Notebook",
        "year": 2004,
        "genres": ["Drama", "Romance"],
        "countries": ["United States"],
        "runtime": 123.0,
        "plot_summary": (
            "A young couple from different social backgrounds fall deeply in love "
            "during one summer in the 1940s. Decades later, an elderly man reads "
            "their story from a notebook to a woman in a nursing home, hoping to "
            "rekindle her fading memories of their life together."
        ),
        "score": 0.87,
    },
    {
        "movie_id": "345678",
        "title": "Eternal Sunshine of the Spotless Mind",
        "year": 2004,
        "genres": ["Drama", "Romance", "Science Fiction"],
        "countries": ["United States"],
        "runtime": 108.0,
        "plot_summary": (
            "Joel Barish discovers that his ex-girlfriend Clementine has undergone "
            "a medical procedure to erase all memories of their relationship. "
            "Devastated, he decides to undergo the same procedure, but as his "
            "memories of Clementine are being erased, he realizes he still loves "
            "her and fights to preserve them."
        ),
        "score": 0.84,
    },
    {
        "movie_id": "456789",
        "title": "Inception",
        "year": 2010,
        "genres": ["Science Fiction", "Thriller", "Action"],
        "countries": ["United States", "United Kingdom"],
        "runtime": 148.0,
        "plot_summary": (
            "Dom Cobb is a skilled thief who steals secrets from people's "
            "subconscious during dream states. Offered a chance to have his "
            "criminal record erased, he must perform inception: planting an idea "
            "in a target's mind. As the team descends deeper into layers of "
            "dreams, Cobb confronts his own guilt over his wife's death."
        ),
        "score": 0.81,
    },
    {
        "movie_id": "567890",
        "title": "Arrival",
        "year": 2016,
        "genres": ["Drama", "Science Fiction"],
        "countries": ["United States"],
        "runtime": 116.0,
        "plot_summary": (
            "When mysterious spacecraft land around the world, linguist Louise "
            "Banks is recruited by the military to communicate with the alien "
            "visitors. As she deciphers their language, she begins experiencing "
            "visions of the future that challenge her understanding of time and "
            "force her to confront a deeply personal choice about love and loss."
        ),
        "score": 0.78,
    },
]
