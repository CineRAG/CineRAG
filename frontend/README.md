# CineRAG frontend

React (Vite) + Tailwind CSS UI for the CineRAG project: JWT auth (login/signup), profile with watched titles and ratings, a movie-search modal, and a chat view that mirrors the rag chat API—with an optional offline mock layer for local demos.

## Prerequisites

- **Node.js** 18+ recommended (matching what your team uses).

## Run in development

From this directory (`frontend/`):

```bash
npm install
npm run dev
```

Open the printed URL (usually `http://localhost:5173`).

In dev mode, **`/api`** is proxied to **`http://127.0.0.1:8000`** (`vite.config.js`). By default **`VITE_USE_MOCK`** keeps mock responses unless you set **`false`** (see [`src/api/client.js`](src/api/client.js)). For the live API, run the backend on port **8000** (follow the backend setup in `../backend`).

Create a **`frontend/.env`** as needed:

| Variable              | Purpose                                                                                                 |
| --------------------- | ------------------------------------------------------------------------------------------------------- |
| `VITE_USE_MOCK=false` | Call the FastAPI backend instead of mocks.                                                              |
| `VITE_API_BASE_URL`   | Optional. Leave unset in dev to use the Vite `/api` proxy; set for a full API URL in production builds. |

## Other scripts

```bash
npm run build   # production bundle to dist/
npm run preview # serve production build locally
npm run lint    # ESLint
```
