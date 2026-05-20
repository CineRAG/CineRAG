import { useEffect, useState } from 'react'
import { Braces, Filter, Search, Sparkles, X } from 'lucide-react'

function formatIntent(intent) {
  if (!intent) return 'Unknown'
  return intent
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function StatCard({ label, value, sub }) {
  return (
    <div className="rounded-2xl border border-[var(--color-border-subtle)] bg-[var(--color-card-row-bg)] px-4 py-3">
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--color-muted)]">{label}</p>
      <p className="mt-1 text-xl font-semibold text-[var(--color-fg)] tabular-nums">{value}</p>
      {sub ? <p className="mt-0.5 text-[11px] text-[var(--color-muted)]">{sub}</p> : null}
    </div>
  )
}

function AttributeChip({ label, value }) {
  if (!value) return null
  return (
    <span className="inline-flex flex-col gap-0.5 rounded-xl border border-[var(--color-chip-border)] bg-[var(--color-chip-bg)] px-3 py-2 min-w-[7rem]">
      <span className="text-[10px] uppercase tracking-wider text-[var(--color-muted)]">{label}</span>
      <span className="text-sm font-medium text-[var(--color-fg)] leading-snug">{value}</span>
    </span>
  )
}

export function PipelineDebugModal({ isOpen, onClose, debug }) {
  const [showRaw, setShowRaw] = useState(false)

  useEffect(() => {
    if (!isOpen) return
    setShowRaw(false)
    function onKey(e) {
      if (e.key === 'Escape') onClose?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isOpen, onClose])

  if (!isOpen || !debug) return null

  const intent = debug.parsed_intent
  const attrs = intent?.attributes || {}
  const filteredOut =
    debug.num_candidates_before_filter != null && debug.num_candidates_after_filter != null
      ? debug.num_candidates_before_filter - debug.num_candidates_after_filter
      : null

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 backdrop-blur-sm bg-[var(--color-overlay)] animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="pipeline-debug-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.()
      }}
    >
      <div
        className="w-full max-w-2xl max-h-[min(90vh,720px)] flex flex-col rounded-[1.5rem] bg-[var(--color-surface)] border border-[var(--color-border)] overflow-hidden animate-fade-in-up"
        style={{ boxShadow: 'var(--shadow-modal)' }}
      >
        <div className="relative shrink-0 border-b border-[var(--color-border-subtle)] px-5 py-4 pr-12">
          <div
            className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-transparent via-amber-500/70 to-transparent"
            aria-hidden
          />
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 border border-amber-500/25 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-accent-deep)]">
              <Sparkles size={12} aria-hidden />
              RAG pipeline
            </span>
            {debug.retrieval_method ? (
              <span className="text-[10px] uppercase tracking-wider text-[var(--color-muted)]">
                {debug.retrieval_method.replace(/_/g, ' ')}
              </span>
            ) : null}
          </div>
          <h2 id="pipeline-debug-title" className="text-lg font-semibold text-[var(--color-fg)] tracking-tight">
            Pipeline debug
          </h2>
          <p className="text-sm text-[var(--color-muted)] mt-0.5">
            How your last message was parsed, expanded, and retrieved.
          </p>
          <button
            type="button"
            className="btn-toolbar absolute right-3 top-3 p-2 rounded-xl hover:bg-[var(--color-border-subtle)] text-[var(--color-muted)] hover:text-[var(--color-fg)]"
            onClick={() => onClose?.()}
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
          {intent ? (
            <section>
              <div className="flex items-center gap-2 mb-3">
                <Search size={16} className="text-amber-600/90 shrink-0" aria-hidden />
                <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-[var(--color-muted)]">
                  Parsed intent
                </h3>
              </div>
              <div className="rounded-2xl border border-[var(--color-border-subtle)] bg-[var(--color-card-row-bg)] p-4 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-[var(--color-accent)]/15 border border-amber-500/30 px-3 py-1 text-sm font-semibold text-[var(--color-fg)]">
                    {formatIntent(intent.intent)}
                  </span>
                  {intent.reference_movie ? (
                    <span className="text-sm text-[var(--color-fg-secondary)]">
                      Ref: <span className="font-medium text-[var(--color-fg)]">{intent.reference_movie}</span>
                    </span>
                  ) : null}
                  {intent.refinement ? (
                    <span className="text-sm text-[var(--color-muted)] italic">“{intent.refinement}”</span>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  <AttributeChip label="Genre" value={attrs.genre} />
                  <AttributeChip label="Mood" value={attrs.mood} />
                  <AttributeChip label="Era" value={attrs.era} />
                  <AttributeChip label="Exclusions" value={attrs.exclusions} />
                </div>
              </div>
            </section>
          ) : null}

          {debug.expanded_query ? (
            <section>
              <div className="flex items-center gap-2 mb-3">
                <Filter size={16} className="text-amber-600/90 shrink-0" aria-hidden />
                <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-[var(--color-muted)]">
                  Expanded query
                </h3>
              </div>
              <blockquote className="rounded-2xl border-l-[3px] border-amber-500/60 bg-[var(--color-debug-bg)] px-4 py-3.5 text-sm leading-relaxed text-[var(--color-fg-secondary)]">
                {debug.expanded_query}
              </blockquote>
            </section>
          ) : null}

          <section>
            <div className="flex items-center gap-2 mb-3">
              <Braces size={16} className="text-amber-600/90 shrink-0" aria-hidden />
              <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-[var(--color-muted)]">
                Retrieval
              </h3>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <StatCard
                label="Before filter"
                value={debug.num_candidates_before_filter ?? '—'}
              />
              <StatCard
                label="After filter"
                value={debug.num_candidates_after_filter ?? '—'}
              />
              <StatCard
                label="Filtered out"
                value={filteredOut != null ? filteredOut : '—'}
                sub={filteredOut === 0 ? 'All kept' : undefined}
              />
            </div>
          </section>

          <div className="pt-1 border-t border-[var(--color-border-subtle)]">
            <button
              type="button"
              onClick={() => setShowRaw((v) => !v)}
              className="btn-toolbar text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-accent)] transition-colors"
            >
              {showRaw ? 'Hide raw JSON' : 'Show raw JSON'}
            </button>
            {showRaw ? (
              <pre className="mt-3 text-[11px] leading-relaxed text-[var(--color-debug-fg)] overflow-x-auto rounded-xl bg-[var(--color-debug-bg)] p-4 border border-[var(--color-border-subtle)] max-h-48 overflow-y-auto font-mono">
                {JSON.stringify(debug, null, 2)}
              </pre>
            ) : null}
          </div>
        </div>

        <div className="shrink-0 px-5 py-4 border-t border-[var(--color-border-subtle)] bg-[var(--color-surface-elevated)]/50">
          <button
            type="button"
            onClick={() => onClose?.()}
            className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-chip-bg)] py-2.5 text-sm font-medium text-[var(--color-fg)] hover:border-amber-600/30 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
