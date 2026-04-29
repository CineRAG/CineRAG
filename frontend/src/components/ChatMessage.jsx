import { MovieCard } from "./MovieCard.jsx";

export function ChatMessage({ role, content, recommendations, onMarkWatched }) {
  const isUser = role === "user";

  return (
    <div
      className={`flex w-full mb-6 animate-fade-in-up ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[min(100%,48rem)] transition-all duration-200 ${
          isUser
            ? "rounded-3xl rounded-br-md bg-zinc-800/90 text-zinc-50 px-4 py-3 shadow-md border border-zinc-600/30 hover:border-amber-700/25"
            : "w-full flex flex-col gap-4 items-stretch text-left"
        }`}
      >
        {content ? (
          <div
            className={`${isUser ? "text-[15px] leading-relaxed" : "text-[15px] leading-relaxed text-zinc-100 whitespace-pre-wrap"}`}
          >
            {content}
          </div>
        ) : null}
        {!isUser && recommendations?.length ? (
          <div className="flex flex-wrap gap-3 stagger-children">
            {recommendations.map((rec) => (
              <MovieCard
                key={rec.movie_id}
                movieId={rec.movie_id}
                title={rec.title}
                year={rec.year}
                genres={rec.genres || []}
                explanation={rec.explanation}
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
