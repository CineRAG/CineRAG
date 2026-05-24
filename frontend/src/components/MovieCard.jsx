import { useEffect, useRef, useState } from "react";
import { BookmarkPlus, ChevronDown, Trash2 } from "lucide-react";
import { RatingStars } from "./RatingStars.jsx";

function cleanPlotText(text) {
  if (!text) return "";
  return text.replace(/^\{\{Plot\}\}\s*/i, "").trim();
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
  const whyPanelRef = useRef(null);
  const cleanedExplanation = cleanPlotText(explanation);
  const cleanedPlotPreview = cleanPlotText(plotPreview);
  const showWhy = mode === "chat" && (cleanedExplanation || cleanedPlotPreview);

  useEffect(() => {
    if (!whyOpen || !whyPanelRef.current) return;
    whyPanelRef.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [whyOpen]);

  const layoutClass =
    mode === "chat"
      ? "rec-card flex-[1_1_17rem] min-w-[15rem] max-w-[19rem]"
      : "max-w-[min(100%,24rem)] w-full";

  return (
    <article
      className={`rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] transition-[transform,border-color,box-shadow] duration-300 hover:-translate-y-0.5 hover:border-amber-600/35 ${layoutClass}`}
      style={{ boxShadow: "var(--shadow-card)" }}
    >
      <div className="p-3">
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
      {showWhy ? (
        <div className="border-t border-[var(--color-border-subtle)]">
          <button
            type="button"
            className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-xs font-medium text-[var(--color-muted)] hover:bg-[var(--color-border-subtle)] ${whyOpen ? "" : "rounded-b-[var(--radius-card)]"}`}
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
            <div
              ref={whyPanelRef}
              className="px-3 pb-3 pt-2 space-y-2 text-sm text-[var(--color-fg-secondary)] leading-relaxed max-h-60 overflow-y-auto border-t border-[var(--color-border-subtle)] rounded-b-[var(--radius-card)] scroll-mb-36"
            >
              {cleanedExplanation ? <p>{cleanedExplanation}</p> : null}
              {cleanedPlotPreview ? (
                <blockquote className="border-l-2 border-amber-600/70 pl-3 text-[var(--color-muted)] text-xs italic leading-relaxed">
                  {cleanedPlotPreview}
                  {cleanedPlotPreview.length >= 298 ? "…" : ""}
                </blockquote>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
