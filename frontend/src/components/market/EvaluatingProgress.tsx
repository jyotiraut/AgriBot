import { useEffect, useState } from 'react'

/**
 * /recommendations has no server-sent progress — it's one long uncached call
 * (~40-45s). A static "loading" skeleton with no movement reads as stuck long
 * before 45s is up, so this ticks a visible elapsed-seconds counter plus a
 * spinner, and swaps in a reassuring message once we're past the typical
 * duration instead of leaving the user guessing whether it's hung.
 */
export function EvaluatingProgress({ monthName }: { monthName: string }) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <div>
      <div className="mb-3 flex items-center gap-2 text-sm text-ink-soft">
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-moss-300 border-t-moss-600" />
        <span>
          Evaluating crops for {monthName} — checking feasibility, risk and price for every
          candidate ({seconds}s{seconds > 50 ? ', almost there…' : '…'})
        </span>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="h-44 animate-pulse rounded-lg border border-hairline bg-paper-raised"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </div>
    </div>
  )
}
