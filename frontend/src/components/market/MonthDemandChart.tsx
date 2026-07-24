import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { MarketCalendarRow } from '@/lib/types'
import { useChartTokens } from '@/lib/chartTokens'

interface Props {
  rows: MarketCalendarRow[]
}

export function MonthDemandChart({ rows }: Props) {
  const CHART = useChartTokens()
  // Sorted by price (what the bar length shows) so length and position agree —
  // the "best pick" by seasonal demand_score is called out separately below,
  // since it isn't always the highest-priced crop (a rare expensive crop can
  // out-price a more seasonally-significant one; see engine/market_calendar.py).
  const data = [...rows].sort((a, b) => b.price_avg - a.price_avg)

  if (!data.length) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-ink-muted">
        No harvest-ready crops with forecast data for this month.
      </div>
    )
  }

  const bestPick = data.reduce((best, r) => (r.demand_score > best.demand_score ? r : best), data[0])

  return (
    <div>
      <p className="mb-2 text-xs text-ink-muted">
        ★ = this month's best seasonal opportunity ({bestPick.crop}), not just the highest price
      </p>
      <ResponsiveContainer width="100%" height={Math.max(180, data.length * 44)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 48, left: 8, bottom: 4 }}
          barCategoryGap="28%"
        >
          <CartesianGrid horizontal={false} stroke={CHART.hairline} />
          <XAxis type="number" hide />
          <YAxis
            dataKey="crop"
            type="category"
            tickLine={false}
            axisLine={false}
            width={116}
            tick={{ fill: CHART.ink, fontSize: 13 }}
            tickFormatter={(v: string) => {
              const label = v.length > 12 ? v.slice(0, 11) + '…' : v
              return v === bestPick.crop ? `★ ${label}` : label
            }}
            style={{ textTransform: 'capitalize' }}
          />
          <Tooltip
            cursor={{ fill: CHART.moss100, opacity: 0.4 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload as MarketCalendarRow
              const trend =
                d.trend_pct == null
                  ? ''
                  : d.trend_pct > 0
                    ? ` · next month up ${Math.abs(d.trend_pct).toFixed(1)}%`
                    : ` · next month down ${Math.abs(d.trend_pct).toFixed(1)}%`
              return (
                <div className="rounded-md border border-hairline bg-paper-raised px-3 py-2 text-sm shadow-sm">
                  <div className="font-medium capitalize text-ink">
                    {d.crop === bestPick.crop ? '★ ' : ''}
                    {d.crop}
                  </div>
                  <div className="text-ink-soft">
                    Rs. {d.price_avg.toFixed(1)}/kg (range {d.price_low.toFixed(0)}–{d.price_high.toFixed(0)})
                    {trend}
                  </div>
                </div>
              )
            }}
          />
          <Bar dataKey="price_avg" radius={[0, 4, 4, 0]} maxBarSize={22}>
            {data.map((d) => (
              <Cell
                key={d.crop}
                fill={d.crop === bestPick.crop ? CHART.terracotta500 : CHART.moss500}
              />
            ))}
            <LabelList
              dataKey="price_avg"
              position="right"
              formatter={(v) => `Rs. ${Number(v).toFixed(0)}`}
              style={{ fontSize: 12, fill: CHART.inkSoft }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
