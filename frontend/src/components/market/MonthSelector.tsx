import { NEPALI_MONTHS } from '@/lib/types'

export function approxCurrentBsMonth(): number {
  const d = new Date()
  const gm = d.getMonth() + 1
  const gd = d.getDate()
  // BS new year falls ~Apr 13-14; Baisakh(1) starts then. Rough offset only —
  // good enough as an initial default, the farmer can pick any month.
  let bs = gm - 3
  if (gd < 14) bs -= 1
  return ((((bs - 1) % 12) + 12) % 12) + 1
}

interface Props {
  value: number
  onChange: (month: number) => void
}

export function MonthSelector({ value, onChange }: Props) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {NEPALI_MONTHS.map((name, i) => {
        const month = i + 1
        const active = month === value
        return (
          <button
            key={name}
            onClick={() => onChange(month)}
            className={`rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors
              ${
                active
                  ? 'border-terracotta-500 bg-terracotta-500 text-paper-raised'
                  : 'border-hairline-strong bg-paper-raised text-ink-soft hover:border-moss-500 hover:text-moss-700'
              }`}
          >
            {name}
          </button>
        )
      })}
    </div>
  )
}
