import { Star } from 'lucide-react'

/** @param {{ value: number, onChange?: (rating: number) => void, readonly?: boolean, className?: string }} props */
export function RatingStars({
  value,
  onChange,
  readonly = false,
  className = '',
}) {
  const stars = Math.min(5, Math.max(0, Math.round(value || 0)))
  const unrated = !value || value === 0

  return (
    <div className={`inline-flex items-center gap-0.5 ${className}`} role={readonly ? 'img' : 'group'}>
      {[1, 2, 3, 4, 5].map((star) => {
        const filled = !unrated && star <= stars
        return (
          <button
            key={star}
            type="button"
            disabled={readonly}
            onClick={() => onChange?.(star)}
            className={`rounded-sm p-0.5 transition-colors ${
              readonly ? 'cursor-default' : 'cursor-pointer hover:bg-white/10'
            }`}
            aria-label={`Rate ${star} out of 5`}
          >
            <Star
              size={18}
              className={
                filled
                  ? 'fill-amber-400 text-amber-300'
                  : 'fill-transparent text-zinc-600'
              }
              strokeWidth={filled ? 0 : 1.5}
            />
          </button>
        )
      })}
      {!readonly && unrated ? (
        <span className="text-xs text-[#737373]">Rate</span>
      ) : null}
    </div>
  )
}
