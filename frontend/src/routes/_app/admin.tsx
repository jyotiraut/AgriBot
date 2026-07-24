import { Fragment, useMemo, useState } from 'react'
import { createFileRoute, redirect } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table'
import { getAdminFarmers } from '@/lib/api'
import { ADMIN_EMAIL, useAuth } from '@/lib/auth'
import type { AdminFarmerProfile } from '@/lib/types'
import { Card, CardBody } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'

export const Route = createFileRoute('/_app/admin')({
  beforeLoad: () => {
    if (useAuth.getState().email !== ADMIN_EMAIL) {
      throw redirect({ to: '/market' })
    }
  },
  component: AdminPage,
})

const RISK_STYLES: Record<string, string> = {
  low: 'bg-moss-50 text-moss-700',
  medium: 'bg-terracotta-100 text-terracotta-600',
  high: 'bg-red-50 text-critical',
}

const RECOMMENDATION_STYLES: Record<string, string> = {
  approve: 'bg-moss-50 text-moss-700',
  review: 'bg-terracotta-100 text-terracotta-600',
  decline: 'bg-red-50 text-critical',
}

const columnHelper = createColumnHelper<AdminFarmerProfile>()

function AdminPage() {
  const [globalFilter, setGlobalFilter] = useState('')
  const [sorting, setSorting] = useState<SortingState>([{ id: 'credit_score', desc: true }])
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const farmersQuery = useQuery({
    queryKey: ['admin-farmers'],
    queryFn: () => getAdminFarmers(0, 500),
    staleTime: 60 * 1000,
  })

  const farmers = farmersQuery.data?.farmers ?? []
  const scoredCount = farmers.filter((f) => f.credit_score != null).length
  const highRiskCount = farmers.filter((f) => f.risk_level === 'high').length

  const columns = useMemo(
    () => [
      columnHelper.accessor((f) => f.name ?? '—', {
        id: 'name',
        header: 'Farmer',
        cell: (info) => (
          <div>
            <div className="font-medium text-ink">{info.getValue()}</div>
            <div className="text-xs text-ink-muted">{info.row.original.email ?? 'no email'}</div>
          </div>
        ),
      }),
      columnHelper.accessor((f) => f.district ?? '—', {
        id: 'district',
        header: 'District / Zone',
        cell: (info) => (
          <div>
            <div className="capitalize text-ink">{info.getValue()}</div>
            <div className="text-xs text-ink-muted">{info.row.original.zone ?? ''}</div>
          </div>
        ),
      }),
      columnHelper.accessor((f) => f.crop ?? '—', {
        id: 'crop',
        header: 'Crop',
        cell: (info) => <span className="capitalize">{info.getValue()}</span>,
      }),
      columnHelper.accessor((f) => f.land_size_hectares ?? null, {
        id: 'land',
        header: 'Land (ha)',
        cell: (info) => (info.getValue() != null ? info.getValue()!.toFixed(2) : '—'),
      }),
      columnHelper.accessor((f) => f.credit_score ?? -1, {
        id: 'credit_score',
        header: 'Credit Score',
        cell: (info) => {
          const v = info.row.original.credit_score
          return v != null ? <span className="font-semibold text-ink">{v}</span> : (
            <span className="text-xs text-ink-muted">Not scored</span>
          )
        },
      }),
      columnHelper.accessor((f) => f.risk_level ?? '', {
        id: 'risk_level',
        header: 'Risk',
        cell: (info) => {
          const v = info.getValue()
          if (!v) return null
          return (
            <span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${RISK_STYLES[v] ?? ''}`}>
              {v}
            </span>
          )
        },
      }),
      columnHelper.accessor((f) => f.recommendation ?? '', {
        id: 'recommendation',
        header: 'Decision',
        cell: (info) => {
          const v = info.getValue()
          if (!v) return null
          return (
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${RECOMMENDATION_STYLES[v] ?? ''}`}
            >
              {v}
            </span>
          )
        },
      }),
      columnHelper.accessor((f) => f.scored_at ?? '', {
        id: 'scored_at',
        header: 'Scored',
        cell: (info) => {
          const v = info.getValue()
          return v ? new Date(v).toLocaleDateString() : '—'
        },
      }),
    ],
    [],
  )

  const table = useReactTable({
    data: farmers,
    columns,
    state: { globalFilter, sorting },
    onGlobalFilterChange: setGlobalFilter,
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    globalFilterFn: (row, _columnId, filterValue) => {
      const f = row.original
      const haystack = `${f.name ?? ''} ${f.email ?? ''} ${f.district ?? ''} ${f.crop ?? ''}`.toLowerCase()
      return haystack.includes(String(filterValue).toLowerCase())
    },
  })

  return (
    <div className="mx-auto max-w-7xl px-8 py-8">
      <header className="mb-8">
        <h1 className="font-display text-3xl font-semibold text-ink">Admin Dashboard</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Every registered farmer and their credit-readiness score, computed from their own
          conversation.
        </p>
      </header>

      <section className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatTile label="Total farmers" value={farmersQuery.data?.total ?? '—'} />
        <StatTile label="Scored" value={scoredCount} />
        <StatTile label="High risk" value={highRiskCount} accent={highRiskCount > 0 ? 'critical' : undefined} />
      </section>

      <div className="mb-4">
        <Input
          placeholder="Search by name, email, district, or crop…"
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          className="max-w-sm"
        />
      </div>

      {farmersQuery.isLoading ? (
        <div className="h-64 animate-pulse rounded-lg border border-hairline bg-paper-raised" />
      ) : farmersQuery.isError ? (
        <p className="text-sm text-critical">Could not load farmers — admin access may be required.</p>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id} className="border-b border-hairline">
                    {hg.headers.map((header) => (
                      <th
                        key={header.id}
                        onClick={header.column.getToggleSortingHandler()}
                        className="cursor-pointer select-none px-4 py-3 text-left text-xs font-medium
                          uppercase tracking-wide text-ink-muted hover:text-ink"
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {{ asc: ' ↑', desc: ' ↓' }[header.column.getIsSorted() as string] ?? ''}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => {
                  const f = row.original
                  const isExpanded = expandedId === f.id
                  return (
                    <Fragment key={row.id}>
                      <tr
                        onClick={() => setExpandedId(isExpanded ? null : f.id)}
                        className="cursor-pointer border-b border-hairline last:border-0 hover:bg-paper"
                      >
                        {row.getVisibleCells().map((cell) => (
                          <td key={cell.id} className="px-4 py-3">
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </td>
                        ))}
                      </tr>
                      {isExpanded && (
                        <tr className="border-b border-hairline bg-paper">
                          <td colSpan={columns.length} className="px-4 py-4">
                            <FarmerDetail farmer={f} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
          {table.getRowModel().rows.length === 0 && (
            <p className="px-4 py-8 text-center text-sm text-ink-muted">No farmers match your search.</p>
          )}
        </Card>
      )}
    </div>
  )
}

function StatTile({
  label,
  value,
  accent,
}: {
  label: string
  value: string | number
  accent?: 'critical'
}) {
  return (
    <Card>
      <CardBody>
        <div className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</div>
        <div className={`mt-1 text-2xl font-semibold ${accent === 'critical' ? 'text-critical' : 'text-ink'}`}>
          {value}
        </div>
      </CardBody>
    </Card>
  )
}

function FarmerDetail({ farmer }: { farmer: AdminFarmerProfile }) {
  const b = farmer.score_breakdown
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Score breakdown
        </h3>
        {b ? (
          <ul className="space-y-1 text-sm text-ink-soft">
            <li>DTI: {b.dti_score}</li>
            <li>Irrigation: {b.irrigation_score}</li>
            <li>Land: {b.land_score}</li>
            <li>Experience: {b.experience_score}</li>
            <li>Crop: {b.crop_score}</li>
            <li className="font-medium text-ink">
              Total: {b.total} / {b.max_possible}
            </li>
          </ul>
        ) : (
          <p className="text-sm text-ink-muted">Not scored yet.</p>
        )}
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Loan &amp; income
        </h3>
        <ul className="space-y-1 text-sm text-ink-soft">
          {farmer.estimated_income_npr != null && (
            <li>Est. income: Rs. {farmer.estimated_income_npr.toLocaleString()}</li>
          )}
          {farmer.loan_amount != null && <li>Requested loan: Rs. {farmer.loan_amount.toLocaleString()}</li>}
          {farmer.max_safe_loan_npr != null && (
            <li>Max safe loan: Rs. {farmer.max_safe_loan_npr.toLocaleString()}</li>
          )}
          {farmer.dti_ratio != null && <li>DTI ratio: {(farmer.dti_ratio * 100).toFixed(1)}%</li>}
          {farmer.monthly_burden_pct != null && (
            <li>Monthly burden: {farmer.monthly_burden_pct.toFixed(1)}%</li>
          )}
        </ul>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Notes &amp; watch points
        </h3>
        {farmer.decision_note && <p className="mb-2 text-sm text-ink-soft">{farmer.decision_note}</p>}
        {farmer.watch_points && farmer.watch_points.length > 0 ? (
          <ul className="list-inside list-disc space-y-1 text-sm text-ink-soft">
            {farmer.watch_points.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        ) : (
          !farmer.decision_note && <p className="text-sm text-ink-muted">No notes.</p>
        )}
      </div>
    </div>
  )
}
