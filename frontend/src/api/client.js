import {
  mockSignup,
  mockLogin,
  mockGetMe,
  mockSearchMovies,
  mockGetMovie,
  mockGetWatched,
  mockAddWatched,
  mockRemoveWatched,
  mockUpdateRating,
  mockChat,
} from "./mockBackend.js";

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.DEV ? "" : "http://localhost:8000");

/** Set VITE_USE_MOCK=false in .env when the FastAPI backend is running. */
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";

function isPublicAuthEndpoint(endpoint, method = "GET") {
  const m = method.toUpperCase();
  return (
    (endpoint.startsWith("/api/auth/login") && m === "POST") ||
    (endpoint.startsWith("/api/auth/signup") && m === "POST")
  );
}

function formatDetail(detail, fallback = "Request failed") {
  if (detail === undefined || detail === null) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) =>
        typeof item === "object" && item.msg ? item.msg : String(item),
      )
      .join(", ");
  }
  return String(detail);
}

async function parseJsonSafe(res) {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

async function apiFetch(endpoint, options = {}) {
  if (USE_MOCK) {
    return mockDispatch(endpoint, options);
  }
  const token = localStorage.getItem("token");
  const method = (options.method || "GET").toUpperCase();

  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${BASE_URL}${endpoint}`, { ...options, headers });

  if (res.status === 401 && !isPublicAuthEndpoint(endpoint, method)) {
    localStorage.removeItem("token");
    window.location.href = "/login";
    const err = new Error("Unauthorized");
    err.status = 401;
    throw err;
  }

  const data = await parseJsonSafe(res);

  if (!res.ok) {
    const err = new Error(
      formatDetail(data?.detail, res.statusText || "Request failed"),
    );
    err.status = res.status;
    err.body = data;
    throw err;
  }
  return data;
}

async function mockDispatch(endpoint, options = {}) {
  const method = options.method || "GET";
  if (endpoint.startsWith("/api/auth/signup") && method === "POST") {
    const body = JSON.parse(options.body || "{}");
    return mockSignup(body.email, body.password, body.display_name);
  }
  if (endpoint.startsWith("/api/auth/login") && method === "POST") {
    const body = JSON.parse(options.body || "{}");
    return mockLogin(body.email, body.password);
  }
  if (endpoint === "/api/users/me") return mockGetMe();
  if (endpoint.startsWith("/api/movies/search")) {
    const q = new URLSearchParams(endpoint.split("?")[1] || "").get("q") || "";
    return mockSearchMovies(q);
  }
  const movieDetailMatch = endpoint.match(/^\/api\/movies\/([^/]+)$/);
  if (movieDetailMatch && method === "GET") {
    return mockGetMovie(movieDetailMatch[1]);
  }
  if (endpoint === "/api/watched" && method === "GET") return mockGetWatched();
  if (endpoint === "/api/watched" && method === "POST") {
    return mockAddWatched(JSON.parse(options.body || "{}"));
  }
  const delMatch = endpoint.match(/^\/api\/watched\/([^/]+)$/);
  if (delMatch && method === "DELETE") return mockRemoveWatched(delMatch[1]);
  if (delMatch && method === "PUT") {
    return mockUpdateRating(
      delMatch[1],
      JSON.parse(options.body || "{}").rating,
    );
  }
  if (endpoint === "/api/chat" && method === "POST") {
    const body = JSON.parse(options.body || "{}");
    return mockChat(body.message, body.session_id);
  }
  throw new Error(`Mock not implemented: ${method} ${endpoint}`);
}

export const signup = (email, password, displayName) =>
  apiFetch("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name: displayName }),
  });

export const login = (email, password) =>
  apiFetch("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

export const getMe = () => apiFetch("/api/users/me");

export const searchMovies = (query) =>
  apiFetch(`/api/movies/search?q=${encodeURIComponent(query)}`);

export const getMovie = (movieId) => apiFetch(`/api/movies/${movieId}`);

export const getWatched = () => apiFetch("/api/watched");

export const addWatched = (movieId, title, year, genres, rating) =>
  apiFetch("/api/watched", {
    method: "POST",
    body: JSON.stringify({ movie_id: movieId, title, year, genres, rating }),
  });

export const removeWatched = (movieId) =>
  apiFetch(`/api/watched/${movieId}`, { method: "DELETE" });

export const updateRating = (movieId, rating) =>
  apiFetch(`/api/watched/${movieId}`, {
    method: "PUT",
    body: JSON.stringify({ rating }),
  });

export const sendMessage = (message, sessionId) =>
  apiFetch("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message, session_id: sessionId }),
  });
