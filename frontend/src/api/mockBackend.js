/** In-memory mock for offline UI development. Matches REST contract shapes. */

const MOCK_TOKEN = 'mock-jwt-token-for-development'

const MOCK_MOVIES = [
  {
    movie_id: '975900',
    title: 'Titanic',
    year: 1997,
    genres: ['Drama', 'Romance'],
    countries: ['United States'],
    runtime: 194,
    plot_summary:
      'A seventeen-year-old aristocrat falls in love with a kind but poor artist aboard the luxurious, ill-fated R.M.S. Titanic.',
  },
  {
    movie_id: '234567',
    title: 'Eternal Sunshine of the Spotless Mind',
    year: 2004,
    genres: ['Drama', 'Romance', 'Sci-Fi'],
    countries: ['United States'],
    runtime: 108,
    plot_summary:
      'Joel discovers his ex erased their memories and undergoes the same procedure, realizing he still loves her.',
  },
  {
    movie_id: '345678',
    title: 'Inception',
    year: 2010,
    genres: ['Science Fiction', 'Thriller', 'Action'],
    countries: ['United States'],
    runtime: 148,
    plot_summary:
      'Dom Cobb steals secrets from dreams and is offered redemption if he can plant an idea deep in a target subconscious.',
  },
  {
    movie_id: '567890',
    title: 'Arrival',
    year: 2016,
    genres: ['Drama', 'Science Fiction'],
    countries: ['United States'],
    runtime: 116,
    plot_summary:
      'A linguist works to communicate with aliens while experiencing nonlinear visions of her own future.',
  },
]

function plotPreview(plot) {
  return plot.slice(0, 300)
}

let mockUser = {
  id: 1,
  email: 'dev@cinerag.local',
  display_name: 'Alex Rivera',
  created_at: '2026-04-12T10:00:00',
}

let watched = [
  {
    id: 1,
    user_id: 1,
    movie_id: '345678',
    title: 'Inception',
    year: 2010,
    genres: ['Science Fiction', 'Thriller', 'Action'],
    rating: 5,
    created_at: '2026-04-12T10:01:00',
  },
  {
    id: 2,
    user_id: 1,
    movie_id: '975900',
    title: 'Titanic',
    year: 1997,
    genres: ['Drama', 'Romance'],
    rating: 4,
    created_at: '2026-04-12T11:30:00',
  },
]
let nextWatchedId = 3

async function delay(data, ms = 120) {
  await new Promise((r) => setTimeout(r, ms))
  return structuredClone(data)
}

export async function mockSignup(email, _password, displayName) {
  if (email === 'exists@test.com') {
    const err = new Error('Email already registered')
    err.status = 409
    throw err
  }
  mockUser = {
    id: mockUser.id,
    email,
    display_name: displayName,
    created_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
  }
  return delay({
    token: MOCK_TOKEN,
    user: { id: mockUser.id, email, display_name: displayName },
  })
}

export async function mockLogin(email, _password) {
  if (email === 'wrong@test.com') {
    const err = new Error('Invalid email or password')
    err.status = 401
    throw err
  }
  return delay({
    token: MOCK_TOKEN,
    user: {
      id: mockUser.id,
      email: mockUser.email,
      display_name: mockUser.display_name,
    },
  })
}

export async function mockGetMe() {
  return delay(mockUser)
}

export async function mockSearchMovies(q) {
  const ql = q.toLowerCase().trim()
  const results = MOCK_MOVIES.filter((m) => m.title.toLowerCase().includes(ql)).map((m) => ({
    movie_id: m.movie_id,
    title: m.title,
    year: m.year,
    genres: m.genres,
    plot_preview: plotPreview(m.plot_summary),
  }))
  return delay({ results })
}

export async function mockGetMovie(movieId) {
  const m = MOCK_MOVIES.find((x) => x.movie_id === movieId)
  if (!m) {
    const err = new Error('Movie not found')
    err.status = 404
    throw err
  }
  return delay({
    movie_id: m.movie_id,
    title: m.title,
    year: m.year,
    genres: m.genres,
    countries: m.countries,
    runtime: m.runtime,
    plot_summary: m.plot_summary,
  })
}

export async function mockGetWatched() {
  const list = watched.map(({ user_id: _uid, ...rest }) => rest)
  return delay({ watched: list, total: list.length })
}

export async function mockAddWatched(body) {
  const dup = watched.find((w) => w.movie_id === body.movie_id)
  if (dup) {
    const err = new Error('Movie already in watched list')
    err.status = 409
    throw err
  }
  const row = {
    id: nextWatchedId++,
    user_id: 1,
    movie_id: body.movie_id,
    title: body.title,
    year: body.year ?? null,
    genres: body.genres ?? [],
    rating: body.rating ?? null,
    created_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
  }
  watched = [...watched, row]
  const { user_id: _uid, ...pub } = row
  return delay(pub, 200)
}

export async function mockRemoveWatched(movieId) {
  const before = watched.length
  watched = watched.filter((w) => w.movie_id !== movieId)
  if (watched.length === before) {
    const err = new Error('Movie not in watched list')
    err.status = 404
    throw err
  }
  return delay({ detail: 'Removed from watched list' })
}

export async function mockUpdateRating(movieId, rating) {
  const idx = watched.findIndex((w) => w.movie_id === movieId)
  if (idx === -1) {
    const err = new Error('Movie not in watched list')
    err.status = 404
    throw err
  }
  watched[idx] = { ...watched[idx], rating }
  const { user_id: _uidRow, ...pub } = watched[idx]
  return delay(pub)
}

export async function mockChat(message, sessionId) {
  const nick = mockUser.display_name?.split(' ')[0] || 'hey'
  const snippet =
    message.length > 180 ? `${message.slice(0, 180).trim()}…` : message.trim()
  const response_text = `[Mock assistant — no live LLM]\n${nick}, here’s a demo reply. You wrote: “${snippet}”\n\nI’ve picked three sample films that plausibly fit the vibe (placeholders for the real RAG pipeline). Open “Why this movie?” on a card to see mock plot groundings.`

  return delay({
    session_id: sessionId,
    response_text,
    recommendations: [
      {
        movie_id: '234567',
        title: 'Eternal Sunshine of the Spotless Mind',
        year: 2004,
        genres: ['Drama', 'Romance', 'Sci-Fi'],
        explanation:
          'Memory, identity, and emotional stakes align with cerebral yet intimate stories—you asked something in that lane.',
        plot_preview: plotPreview(
          MOCK_MOVIES.find((m) => m.movie_id === '234567')?.plot_summary ?? ''
        ),
        match_reasons: ['shared theme: memory', 'emotional depth', 'non-linear narrative'],
      },
      {
        movie_id: '567890',
        title: 'Arrival',
        year: 2016,
        genres: ['Drama', 'Science Fiction'],
        explanation:
          'If you want thoughtful sci-fi with a human core, this balances ideas and feeling on the same scale.',
        plot_preview: plotPreview(
          MOCK_MOVIES.find((m) => m.movie_id === '567890')?.plot_summary ?? ''
        ),
        match_reasons: ['cerebral sci-fi', 'emotional core', 'perception of time'],
      },
      {
        movie_id: '345678',
        title: 'Inception',
        year: 2010,
        genres: ['Science Fiction', 'Thriller', 'Action'],
        explanation:
          'For layered reality and propulsive stakes, this remains a strong anchor while staying grounded in character.',
        plot_preview: plotPreview(
          MOCK_MOVIES.find((m) => m.movie_id === '345678')?.plot_summary ?? ''
        ),
        match_reasons: ['layered narrative', 'dream logic', 'tension and catharsis'],
      },
    ],
    debug: {
      parsed_intent: {
        intent: 'find_by_mood',
        reference_movie: null,
        attributes: { genre: null, mood: null, era: null, exclusions: null },
        refinement: null,
      },
      expanded_query: message.slice(0, 80) + ' …',
      num_candidates_before_filter: 50,
      num_candidates_after_filter: 47,
      retrieval_method: 'hybrid_rrf (mock)',
    },
  }, 400)
}
