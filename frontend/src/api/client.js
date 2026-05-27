import { toast } from "sonner";

// Detect Nuvolos-style proxy prefix at runtime. The frontend is served
// at /proxy/<port>/, but fetch("/api/...") with a leading slash resolves
// to the host root (skipping the prefix), so the request hits the
// proxy at /api/* which Nuvolos returns 405 for. Reading the prefix
// from window.location.pathname makes the same bundle work locally
// (no prefix → "") and under any /proxy/<port>/ proxy automatically.
const BASE_URL = (() => {
  if (typeof window === "undefined") return "";
  const match = window.location.pathname.match(/^(\/proxy\/\d+)/);
  return match ? match[1] : "";
})();

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
