const KEY = "cinerag-theme";

export const THEMES = ["dark", "light", "neon"];

export function isValidTheme(value) {
  return THEMES.includes(value);
}

export function getStoredTheme() {
  if (typeof window === "undefined") return "dark";
  try {
    const s = localStorage.getItem(KEY);
    if (s === "cinema") return "neon";
    if (isValidTheme(s)) return s;
  } catch {}
  return window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

export function applyTheme(theme) {
  if (typeof document === "undefined") return;
  const resolved = isValidTheme(theme) ? theme : "dark";
  document.documentElement.dataset.theme = resolved;
  try {
    localStorage.setItem(KEY, resolved);
  } catch {}
}

export function nextTheme(current) {
  const idx = THEMES.indexOf(current);
  return THEMES[(idx + 1) % THEMES.length];
}
