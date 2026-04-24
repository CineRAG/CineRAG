"""Pydantic schemas for movie, watched-list, and helper responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MovieSearchItem(BaseModel):
    movie_id: str
    title: str
    year: int | None = None
    genres: list[str]
    plot_preview: str


class MovieSearchResponse(BaseModel):
    results: list[MovieSearchItem]


class MovieDetailResponse(BaseModel):
    movie_id: str
    title: str
    year: int | None = None
    genres: list[str]
    countries: list[str]
    runtime: float | None = None
    plot_summary: str


class WatchedCreateRequest(BaseModel):
    movie_id: str
    title: str
    year: int | None = None
    genres: list[str] = Field(default_factory=list)
    rating: float | None = Field(default=None, ge=1.0, le=5.0)


class RatingUpdateRequest(BaseModel):
    rating: float = Field(ge=1.0, le=5.0)


class WatchedMovieResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    movie_id: str
    title: str
    year: int | None = None
    genres: list[str]
    rating: float | None = None
    created_at: datetime


class WatchedListResponse(BaseModel):
    watched: list[WatchedMovieResponse]
    total: int


class DetailResponse(BaseModel):
    detail: str
