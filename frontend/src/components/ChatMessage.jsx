import { Workflow } from "lucide-react";
import { MovieCard } from "./MovieCard.jsx";

export function ChatMessage({ role, content, recommendations, debug, onMarkWatched, onViewDebug }) {
  const isUser = role === "user";

  return (
    <div
      className={`flex w-full mb-6 animate-fade-in-up ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`transition-all duration-200 ${
          isUser
            ? "max-w-[min(100%,48rem)] rounded-3xl rounded-br-md px-4 py-3 border shadow-md hover:border-amber-600/30"
            : "w-full max-w-full flex flex-col gap-4 items-stretch text-left"
        }`}
        style={
          isUser
            ? {
                background: "var(--color-user-bubble-bg)",
                borderColor: "var(--color-user-bubble-border)",
                boxShadow: "var(--shadow-card)",
              }
            : undefined
        }
      >
        {content ? (
          <div
            className={`${isUser ? "text-[15px] leading-relaxed text-[var(--color-fg)]" : "text-[15px] leading-relaxed text-[var(--color-assistant-text)] whitespace-pre-wrap"}`}
          >
            {content}
          </div>
        ) : null}
        {!isUser && debug ? (
          <button
            type="button"
            onClick={() => onViewDebug?.(debug)}
            className="btn-toolbar self-start inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-chip-bg)] px-3 py-1.5 text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-fg)] hover:border-amber-600/35 transition-all duration-200"
          >
            <Workflow size={14} className="text-amber-600/90 shrink-0" aria-hidden />
            Pipeline debug
          </button>
        ) : null}
        {!isUser && recommendations?.length ? (
          <div className="recommendations-row stagger-children">
            {recommendations.map((rec) => (
              <MovieCard
                key={rec.movie_id}
                movieId={rec.movie_id}
                title={rec.title}
                year={rec.year}
                genres={rec.genres || []}
                plotPreview={rec.plot_preview}
                matchReasons={rec.match_reasons}
                userRating={null}
                mode="chat"
                onMarkWatched={onMarkWatched}
              />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
