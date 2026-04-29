export function moviePosterSrc(movie) {
  const fromApi = movie.poster_url ?? movie.posterUrl;
  if (typeof fromApi === "string" && /^https?:\/\//i.test(fromApi.trim())) {
    return fromApi.trim();
  }
  const seed = encodeURIComponent(
    String(movie.movie_id ?? movie.title ?? "movie").slice(0, 96),
  );
  return `https://picsum.photos/seed/${seed}/176/264`;
}
