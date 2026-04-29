import { useMemo, useState } from "react";
import { BookmarkPlus, ChevronDown, Trash2 } from "lucide-react";
import { RatingStars } from "./RatingStars.jsx";

function posterGradient(title) {
  let h = 0;
  for (let i = 0; i < title.length; i++)
    h = (h + title.charCodeAt(i) * (i + 1)) % 360;
  return `linear-gradient(145deg, hsl(${h} 42% 22%), hsl(${(h + 52) % 360} 38% 12%))`;
}

function initials(title) {
  const parts = title.trim().split(/\s+/).slice(0, 2);
  return (
    parts
      .map((p) => p[0])
      .join("")
      .toUpperCase()
      .slice(0, 3) || "?"
  );
}

export function MovieCard({
  movieId,
  title,
  year,
  genres,
  explanation = null,
  plotPreview = null,
  matchReasons = null,
  userRating = null,
  mode,
  onMarkWatched,
  onRemove,
  onRatingChange,
}) {
  const [whyOpen, setWhyOpen] = useState(false);
  const showWhy = mode === "chat" && explanation;

  const style = useMemo(() => ({ background: posterGradient(title) }), [title]);

  return (
    <article className="rounded-[var(--radius-card)] border border-white/[0.08] bg-[var(--color-surface)] overflow-hidden shadow-lg shadow-black/30 max-w-[min(100%,24rem)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-amber-950/20 hover:border-amber-900/30">
      <div className="flex gap-3 p-3">
        <div
          className="aspect-[2/3] w-[5.25rem] shrink-0 rounded-xl flex items-center justify-center text-xs font-semibold tracking-wide text-white/90 shadow-inner ring-1 ring-white/10"
          style={style}
        >
          {initials(title)}
        </div>
        <div className="min-w-0 flex-1 flex flex-col gap-1.5">
          <div>
            <h3 className="font-semibold text-white leading-snug truncate">
              {title}
            </h3>
            <p className="text-xs text-[var(--color-muted)]">
              {year != null ? year : "—"}{" "}
              {genres?.length ? (
                <span className="text-white/70">
                  {"· "}
                  {genres.slice(0, 3).join(" · ")}
                </span>
              ) : null}
            </p>
          </div>
          {matchReasons?.length ? (
            <ul className="flex flex-wrap gap-1">
              {matchReasons.map((r) => (
                <li
                  key={r}
                  className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-[var(--color-muted)]"
                >
                  {r}
                </li>
              ))}
            </ul>
          ) : null}
          {mode === "chat" ? (
            <button
              type="button"
              onClick={() => onMarkWatched?.(movieId)}
              className="mt-auto inline-flex items-center justify-center gap-2 rounded-xl btn-neon-accent text-sm font-medium py-2 px-3 w-fit"
            >
              <BookmarkPlus size={16} aria-hidden />
              Mark as watched
            </button>
          ) : null}
          {mode === "profile" ? (
            <div className="flex flex-wrap items-center gap-2 mt-auto">
              <RatingStars
                value={userRating ?? 0}
                onChange={(rating) => onRatingChange?.(movieId, rating)}
                readonly={false}
              />
              <button
                type="button"
                onClick={() => onRemove?.(movieId)}
                className="inline-flex items-center gap-1 text-xs text-red-400 hover:text-red-300 ml-auto rounded-lg px-2 py-1 hover:bg-white/5"
              >
                <Trash2 size={14} aria-hidden /> Remove
              </button>
            </div>
          ) : null}
        </div>
      </div>
      {showWhy ? (
        <div className="border-t border-white/10">
          <button
            type="button"
            className="w-full flex items-center justify-between gap-2 px-3 py-2 text-xs font-medium text-[var(--color-muted)] hover:bg-white/[0.04]"
            onClick={() => setWhyOpen((v) => !v)}
            aria-expanded={whyOpen}
          >
            Why this movie?
            <ChevronDown
              size={16}
              className={`transition-transform shrink-0 ${whyOpen ? "rotate-180" : ""}`}
            />
          </button>
          {whyOpen ? (
            <div className="px-3 pb-3 space-y-2 text-sm text-white/85 leading-relaxed">
              <p>{explanation}</p>
              {plotPreview ? (
                <blockquote className="border-l-2 border-amber-600/70 pl-3 text-[var(--color-muted)] text-xs italic leading-relaxed">
                  {plotPreview}
                  {plotPreview.length >= 298 ? "…" : ""}
                </blockquote>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
