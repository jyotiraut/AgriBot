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
  calendar: Record<string, MarketCalendarRow[]>
  selectedMonthName: string
}

interface Datum {
  month: string
  crop: string
  price: number
}

export function YearOverviewChart({ calendar, selectedMonthName }: Props) {
  const CHART = useChartTokens()
  const data: Datum[] = Object.entries(calendar).map(([month, rows]) => {
    const top = rows[0]
    return {
      month,
      crop: top ? top.crop : '—',
      price: top ? top.price_avg : 0,
    }
  })

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 28, right: 12, left: 4, bottom: 4 }} barCategoryGap="20%">
        <CartesianGrid vertical={false} stroke={CHART.hairline} />
        <XAxis
          dataKey="month"
          tickLine={false}
          axisLine={{ stroke: CHART.hairline }}
          tick={{ fill: CHART.inkMuted, fontSize: 12 }}
          interval={0}
        />
        <YAxis hide />
        <Tooltip
          cursor={{ fill: CHART.moss100, opacity: 0.4 }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const d = payload[0].payload as Datum
            return (
              <div className="rounded-md border border-hairline bg-paper-raised px-3 py-2 text-sm shadow-sm">
                <div className="font-medium capitalize text-ink">{d.crop}</div>
                <div className="text-ink-soft">
                  {d.month} · Rs. {d.price.toFixed(1)}/kg
                </div>
              </div>
            )
          }}
        />
        <Bar dataKey="price" radius={[4, 4, 0, 0]} maxBarSize={28}>
          {data.map((d) => (
            <Cell
              key={d.month}
              fill={d.month === selectedMonthName ? CHART.terracotta500 : CHART.moss500}
            />
          ))}
          <LabelList
            dataKey="crop"
            position="top"
            style={{ fontSize: 11, fill: CHART.inkSoft, textTransform: 'capitalize' }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
