import { toast } from "sonner";

// Hardcoded to relative paths: requests like "/api/..." go to the same
// origin the page was loaded from (the Vite dev/preview server), which
// then proxies "/api/..." to the backend via VITE_BACKEND_PROXY_TARGET.
// Earlier code read VITE_API_BASE_URL, but the value gets baked into
// the production bundle at build time; stale values from a leftover
// shell export caused CORS-blocked cross-origin fetches against the
// Nuvolos backend proxy. Keep this hardcoded for the demo; the proxy
// target stays configurable on the Vite server side.
const BASE_URL = "";

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
  const token = localStorage.getItem("token");
  const method = (options.method || "GET").toUpperCase();

  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  let res;
  try {
    res = await fetch(`${BASE_URL}${endpoint}`, { ...options, headers });
  } catch (e) {
    const err = new Error(e?.message || "Network error");
    err.status = 0;
    err.body = null;
    throw err;
  }

  if (res.status === 401 && !isPublicAuthEndpoint(endpoint, method)) {
    localStorage.removeItem("token");
    toast.error("Session expired. Please sign in again.");
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

export const sendMessage = (message, sessionId, { silent = false } = {}) =>
  apiFetch("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message, session_id: sessionId, silent }),
  });

export const getChats = () => apiFetch("/api/chats");

export const createChat = () =>
  apiFetch("/api/chats", { method: "POST" });

export const getChat = (chatId) =>
  apiFetch(`/api/chats/${encodeURIComponent(chatId)}`);

export const deleteChat = (chatId) =>
  apiFetch(`/api/chats/${encodeURIComponent(chatId)}`, { method: "DELETE" });

/** @deprecated Use getChats */
export const getChatSessions = () => apiFetch("/api/chat/sessions");

/** @deprecated Use getChat */
export const getChatSessionHistory = (sessionId) =>
  apiFetch(`/api/chat/sessions/${encodeURIComponent(sessionId)}`);
