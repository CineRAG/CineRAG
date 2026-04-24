# CineRAG

CineRAG is a conversational movie recommendation system built for the Retrieval-Augmented Generation (RAG) course (FS 2026, University of Zurich).

The project combines:
- FastAPI backend + SQLite + JWT auth
- Hybrid retrieval (BM25 + dense embeddings + RRF)
- LLM-driven intent parsing, query expansion, and grounded recommendation generation
- React frontend for auth, chat, and watched-movie management

## Scope (from project docs)

MVP scope is based on the `docs/` plans and contracts:
- Dataset: CMU Movie Summary Corpus
- Retrieval: BM25 + dense + RRF
- Query pre-processing + semantic expansion
- Watched-movie filtering + attribute-based reranking
- Grounded generation with citations
- FastAPI + SQLite + JWT
- React frontend
- Offline retrieval eval (`MRR@5`, `NDCG@5`)

## Current Backend Status

`Person C - Week 1` work is implemented:
- FastAPI backend shell
- Config + database setup
- SQLAlchemy models (`User`, `WatchedMovieDB`, `ConversationMessage`)
- Auth system (password hashing, JWT, current-user dependency)
- Auth endpoints (`/api/auth/signup`, `/api/auth/login`, `/api/users/me`)
- Movies/watchlist endpoints (`/api/movies/search`, `/api/movies/{movie_id}`, watched CRUD)
- Chat endpoint shell (`/api/chat`) with conversation-history/watched wiring

Note: `/api/movies/*` and `/api/chat` rely on Person A/B integrations in later weeks. Until those components are present, they return service-unavailable behavior for missing retriever/chat service.

## Project Structure

Planned structure from docs includes:
- `backend/` for API, auth, movies, chat orchestration wiring
- `frontend/` for React app
- `scripts/` for data processing/indexing/eval
- `data/` for processed/index artifacts

This repository currently contains the backend Week 1 implementation and docs.

## Backend Environment Setup (Docs-aligned)

Use the backend-local dependency file as defined in docs.

1. Create and activate a virtual environment from project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install backend dependencies from the backend directory:

```bash
cd backend
pip install -r requirements.txt
```

3. Run backend:

```bash
uvicorn main:app --reload
```

Backend base URL: `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`

## Full Local Run (Target Week 2+ / Week 3)

From docs, final local run is expected to use three terminals:

1. Ollama:

```bash
ollama serve
```

2. Backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

3. Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Backend API Contract (Summary)

Auth:
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/users/me`

Movies:
- `GET /api/movies/search?q=...`
- `GET /api/movies/{movie_id}`

Watched list:
- `GET /api/watched`
- `POST /api/watched`
- `DELETE /api/watched/{movie_id}`
- `PUT /api/watched/{movie_id}`

Chat:
- `POST /api/chat` (requires `session_id`)

