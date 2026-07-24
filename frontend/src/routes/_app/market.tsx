import { useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { getMarketCalendar, getRecommendations } from '@/lib/api'
import { NEPALI_MONTHS } from '@/lib/types'
import { MonthSelector, approxCurrentBsMonth } from '@/components/market/MonthSelector'
import { YearOverviewChart } from '@/components/market/YearOverviewChart'
import { MonthDemandChart } from '@/components/market/MonthDemandChart'
import { RecommendationCard } from '@/components/market/RecommendationCard'
import { EvaluatingProgress } from '@/components/market/EvaluatingProgress'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'

export const Route = createFileRoute('/_app/market')({
  component: MarketPage,
})

function MarketPage() {
  const [month, setMonth] = useState(approxCurrentBsMonth)
  const monthName = NEPALI_MONTHS[month - 1]

  const calendarQuery = useQuery({
    queryKey: ['market-calendar'],
    queryFn: () => getMarketCalendar(6),
    staleTime: 10 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  })

  // /recommendations runs a full feasibility+risk+price evaluation per crop
  // uncached server-side (~40s cold) — cache aggressively per month client-side
  // so switching months and coming back doesn't re-pay that cost.
  const recommendationsQuery = useQuery({
    queryKey: ['recommendations', month],
    queryFn: () => getRecommendations(month, 'en'),
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  })

  const monthRows = calendarQuery.data?.calendar[monthName] ?? []

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <header className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold text-ink">Market Analysis</h1>
          <p className="mt-1 text-sm text-ink-soft">
            Harvest calendar and Kalimati price outlook, month by month.
          </p>
        </div>
        {calendarQuery.data?.generated_at && (
          <p className="text-xs text-ink-muted">
            Forecast updated {new Date(calendarQuery.data.generated_at).toLocaleDateString()}
          </p>
        )}
      </header>

      <section className="mb-8">
        <MonthSelector value={month} onChange={setMonth} />
      </section>

      <section className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <h2 className="text-sm font-semibold text-ink">Best crop by month, across the year</h2>
            <p className="text-xs text-ink-muted">Top-ranked crop's forecasted price each Nepali month</p>
          </CardHeader>
          <CardBody>
            {calendarQuery.isLoading ? (
              <ChartSkeleton />
            ) : calendarQuery.data ? (
              <YearOverviewChart calendar={calendarQuery.data.calendar} selectedMonthName={monthName} />
            ) : null}
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <h2 className="text-sm font-semibold text-ink">Harvest & sell now — {monthName}</h2>
            <p className="text-xs text-ink-muted">Ranked by seasonal demand opportunity</p>
          </CardHeader>
          <CardBody>
            {calendarQuery.isLoading ? (
              <ChartSkeleton />
            ) : (
              <MonthDemandChart rows={monthRows} />
            )}
          </CardBody>
        </Card>
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-xl font-semibold text-ink">
            What to plant in {monthName}
          </h2>
          {recommendationsQuery.data && (
            <span className="text-xs text-ink-muted">
              {recommendationsQuery.data.context.season} season ·{' '}
              {recommendationsQuery.data.total} crops evaluated
            </span>
          )}
        </div>

        {recommendationsQuery.isLoading ? (
          <EvaluatingProgress monthName={monthName} />
        ) : recommendationsQuery.isError ? (
          <p className="text-sm text-critical">
            Could not load recommendations for this month.{' '}
            <button
              onClick={() => recommendationsQuery.refetch()}
              className="font-medium text-moss-600 hover:underline"
            >
              Try again
            </button>
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recommendationsQuery.data?.recommendations.map((rec) => (
              <RecommendationCard key={rec.crop_key} rec={rec} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function ChartSkeleton() {
  return <div className="h-64 animate-pulse rounded-md bg-paper" />
}
