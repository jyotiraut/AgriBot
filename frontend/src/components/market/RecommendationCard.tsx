import type { CropRecommendation } from '@/lib/types'
import { Card } from '@/components/ui/Card'

const RISK_STYLES: Record<string, string> = {
  low: 'bg-moss-50 text-moss-700',
  medium: 'bg-terracotta-100 text-terracotta-600',
  high: 'bg-red-50 text-critical',
}

export function RecommendationCard({ rec }: { rec: CropRecommendation }) {
  const riskClass = RISK_STYLES[rec.risk_tier?.toLowerCase()] ?? 'bg-paper text-ink-soft'

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-ink-muted">
            #{rec.rank}
          </div>
          <h3 className="font-display text-lg font-semibold text-ink">{rec.crop_name}</h3>
        </div>
        <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${riskClass}`}>
          {rec.risk_tier} risk
        </span>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-soft">
        <span>Rs. {rec.forecasted_price?.toFixed(1)}/kg</span>
        <span>·</span>
        <span>{rec.weeks_to_grow} weeks to grow</span>
        <span>·</span>
        <span>Harvest: {rec.best_harvest_month}</span>
      </div>

      <p className="text-sm text-ink-soft">{rec.feasibility_reason}</p>

      {rec.scoring_notes && (
        <p className="rounded-md bg-moss-50 px-3 py-2 text-sm text-moss-700">
          💡 {rec.scoring_notes}
        </p>
      )}
    </Card>
  )
}
