import { BookmarkPlus, Trash2 } from "lucide-react";
import { RatingStars } from "./RatingStars.jsx";

export function MovieCard({
  movieId,
  title,
  year,
  genres,
  plotPreview = null,
  matchReasons = null,
  userRating = null,
  mode,
  onMarkWatched,
  onRemove,
  onRatingChange,
}) {
  const layoutClass =
    mode === "chat"
      ? "rec-card flex-[1_1_17rem] min-w-[15rem] max-w-[19rem]"
      : "max-w-[min(100%,24rem)] w-full bg-[var(--color-surface)]";

  const showPlot = mode === "chat" && plotPreview;

  return (
    <article
      className={`rounded-[var(--radius-card)] border overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:border-amber-600/30 ${layoutClass}`}
      style={{ boxShadow: "var(--shadow-card)" }}
    >
      <div className="p-3 flex flex-col gap-2 h-full">
        <div className="min-w-0 flex flex-col gap-1.5">
          <div>
            <h3 className="font-semibold text-[var(--color-fg)] leading-snug truncate">
              {title}
            </h3>
            <p className="text-xs text-[var(--color-muted)]">
              {year != null ? year : "—"}{" "}
              {genres?.length ? (
                <span className="text-[var(--color-fg-secondary)]">
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
                  className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full bg-[var(--color-chip-bg)] border border-[var(--color-chip-border)] text-[var(--color-muted)]"
                >
                  {r}
                </li>
              ))}
            </ul>
          ) : null}
          {showPlot ? (
            <blockquote className="border-l-2 border-amber-600/50 pl-2.5 text-xs text-[var(--color-muted)] leading-relaxed line-clamp-5 italic">
              {plotPreview}
            </blockquote>
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
                className="inline-flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:text-red-500 dark:hover:text-red-300 ml-auto rounded-lg px-2 py-1 hover:bg-[var(--color-border-subtle)]"
              >
                <Trash2 size={14} aria-hidden /> Remove
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}
