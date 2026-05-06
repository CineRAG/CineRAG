# CineRAG frontend

React (Vite) + Tailwind CSS UI for the CineRAG project: JWT auth (login/signup), profile with watched titles and ratings, a movie-search modal, and a chat view wired to the FastAPI backend. Errors surface as **Sonner** toasts (top-right).

## Prerequisites

- **Node.js** 18+ recommended (matching what your team uses).

## Run in development

From this directory (`frontend/`):

```bash
npm install
npm run dev
```

Open the printed URL (usually `http://localhost:5173`).

In dev mode, **`/api`** is proxied to **`http://127.0.0.1:8000`** (`vite.config.js`). Start the backend on port **8000** (see `../README.md`).

Create a **`frontend/.env`** as needed:

| Variable              | Purpose                                                                                                 |
| --------------------- | ------------------------------------------------------------------------------------------------------- |
| `VITE_API_BASE_URL`   | Optional. Leave unset in dev to use the Vite `/api` proxy; set for a full API URL in production builds. |

## Other scripts

```bash
npm run build   # production bundle to dist/
npm run preview # serve production build locally
npm run lint    # ESLint
```
