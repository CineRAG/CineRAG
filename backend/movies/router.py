"""Movie search/detail endpoints and watched-movie CRUD endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth.utils import get_current_user
from backend.database import get_db
from backend.movies.models import WatchedMovieDB
from backend.movies.schemas import (
    DetailResponse,
    MovieDetailResponse,
    MovieSearchItem,
    MovieSearchResponse,
    RatingUpdateRequest,
    WatchedCreateRequest,
    WatchedListResponse,
    WatchedMovieResponse,
)

router = APIRouter(tags=["movies"])


def _to_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            return []
    return []


def _serialize_watched(item: WatchedMovieDB) -> WatchedMovieResponse:
    return WatchedMovieResponse(
        id=item.id,
        movie_id=item.movie_id,
        title=item.title,
        year=item.year,
        genres=_to_string_list(item.genres),
        rating=item.rating,
        created_at=item.created_at,
    )


def _get_retriever(request: Request):
    retriever = getattr(request.app.state, "retriever", None)
    if retriever is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Movie retriever is not available yet")
    return retriever


@router.get("/api/movies/search", response_model=MovieSearchResponse)
def search_movies(
    request: Request,
    q: str = Query(..., min_length=1),
    user_id: int = Depends(get_current_user),
) -> MovieSearchResponse:
    _ = user_id
    retriever = _get_retriever(request)

    if not hasattr(retriever, "search_by_title"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Movie retriever is not available yet")

    raw_results = retriever.search_by_title(q, top_k=10) or []
    results = []
    for movie in raw_results:
        plot_summary = str(movie.get("plot_summary", ""))
        results.append(
            MovieSearchItem(
                movie_id=str(movie.get("movie_id", "")),
                title=str(movie.get("title", "")),
                year=movie.get("year"),
                genres=_to_string_list(movie.get("genres")),
                plot_preview=plot_summary[:300],
            )
        )

    return MovieSearchResponse(results=results)


@router.get("/api/movies/{movie_id}", response_model=MovieDetailResponse)
def get_movie_by_id(movie_id: str, request: Request, user_id: int = Depends(get_current_user)) -> MovieDetailResponse:
    _ = user_id
    retriever = _get_retriever(request)

    if not hasattr(retriever, "retrieve_by_movie_id"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Movie retriever is not available yet")

    movie = retriever.retrieve_by_movie_id(movie_id)
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    return MovieDetailResponse(
        movie_id=str(movie.get("movie_id", "")),
        title=str(movie.get("title", "")),
        year=movie.get("year"),
        genres=_to_string_list(movie.get("genres")),
        countries=_to_string_list(movie.get("countries")),
        runtime=movie.get("runtime"),
        plot_summary=str(movie.get("plot_summary", "")),
    )


@router.get("/api/watched", response_model=WatchedListResponse)
def list_watched_movies(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)) -> WatchedListResponse:
    watched_rows = (
        db.query(WatchedMovieDB)
        .filter(WatchedMovieDB.user_id == user_id)
        .order_by(WatchedMovieDB.created_at.desc())
        .all()
    )
    watched = [_serialize_watched(row) for row in watched_rows]
    return WatchedListResponse(watched=watched, total=len(watched))


@router.post("/api/watched", response_model=WatchedMovieResponse, status_code=status.HTTP_201_CREATED)
def add_watched_movie(
    payload: WatchedCreateRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WatchedMovieResponse:
    existing = (
        db.query(WatchedMovieDB)
        .filter(WatchedMovieDB.user_id == user_id, WatchedMovieDB.movie_id == payload.movie_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Movie already in watched list")

    watched = WatchedMovieDB(
        user_id=user_id,
        movie_id=payload.movie_id,
        title=payload.title,
        year=payload.year,
        genres=json.dumps(payload.genres),
        rating=payload.rating,
    )
    db.add(watched)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Movie already in watched list")

    db.refresh(watched)
    return _serialize_watched(watched)


@router.delete("/api/watched/{movie_id}", response_model=DetailResponse)
def remove_watched_movie(
    movie_id: str,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DetailResponse:
    watched = (
        db.query(WatchedMovieDB)
        .filter(WatchedMovieDB.user_id == user_id, WatchedMovieDB.movie_id == movie_id)
        .first()
    )
    if watched is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not in watched list")

    db.delete(watched)
    db.commit()
    return DetailResponse(detail="Removed from watched list")


@router.put("/api/watched/{movie_id}", response_model=WatchedMovieResponse)
def update_watched_movie_rating(
    movie_id: str,
    payload: RatingUpdateRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WatchedMovieResponse:
    watched = (
        db.query(WatchedMovieDB)
        .filter(WatchedMovieDB.user_id == user_id, WatchedMovieDB.movie_id == movie_id)
        .first()
    )
    if watched is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not in watched list")

    watched.rating = payload.rating
    db.commit()
    db.refresh(watched)
    return _serialize_watched(watched)
