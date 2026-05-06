/**
 * Normalize API / fetch errors into a single user-facing string.
 */
export function getApiErrorMessage(err, fallback = 'Something went wrong') {
  if (err?.body?.detail != null) {
    const d = err.body.detail
    if (typeof d === 'string') return d
    if (Array.isArray(d)) {
      return d
        .map((item) => (typeof item === 'object' && item?.msg ? item.msg : String(item)))
        .join(', ')
    }
  }
  if (typeof err?.message === 'string' && err.message) return err.message
  return fallback
}

export function isNetworkError(err) {
  const raw = typeof err?.message === 'string' ? err.message : ''
  return raw === 'Failed to fetch' || /network|load failed|fetch/i.test(raw)
}
