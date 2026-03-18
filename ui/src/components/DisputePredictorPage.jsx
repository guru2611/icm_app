import { useState, useEffect, useCallback } from 'react'

const fmt = (n) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)

const JOB_LABELS = { REP: 'Rep', SREP: 'Sr. Rep', MGR: 'Manager', DM: 'Dist. Mgr', UNKNOWN: 'Unknown' }
const JOB_COLORS = {
  REP:     'bg-slate-100 text-slate-700',
  SREP:    'bg-indigo-100 text-indigo-700',
  MGR:     'bg-amber-100  text-amber-700',
  DM:      'bg-rose-100   text-rose-700',
  UNKNOWN: 'bg-gray-100   text-gray-500',
}

function StatCard({ label, value, sub, accent }) {
  const borders = {
    red:    'border-l-red-400',
    amber:  'border-l-amber-400',
    indigo: 'border-l-indigo-400',
    emerald:'border-l-emerald-400',
  }
  return (
    <div className={`bg-white rounded-xl border border-slate-200 border-l-4 ${borders[accent] ?? 'border-l-slate-300'} px-5 py-4 shadow-sm`}>
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-1">{label}</p>
      <p className="text-2xl font-bold text-slate-800">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
    </div>
  )
}

function JobBreakdownBar({ items }) {
  if (!items || items.length === 0) return null
  const total = items.reduce((s, i) => s + i.discrepancy, 0) || 1
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-4">Discrepancy by Job Level</p>
      <div className="space-y-3">
        {items.map((item) => {
          const pct = Math.round((item.discrepancy / total) * 100)
          return (
            <div key={item.job_code}>
              <div className="flex justify-between items-center mb-1">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${JOB_COLORS[item.job_code] ?? JOB_COLORS.UNKNOWN}`}>
                    {JOB_LABELS[item.job_code] ?? item.job_code}
                  </span>
                  <span className="text-xs text-slate-400">{item.employees} employee{item.employees !== 1 ? 's' : ''} · {item.plan_gaps} gap{item.plan_gaps !== 1 ? 's' : ''}</span>
                </div>
                <span className="text-sm font-semibold text-slate-700">{fmt(item.discrepancy)}</span>
              </div>
              <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-red-400 rounded-full" style={{ width: `${pct}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function DisputeTable({ disputes }) {
  const [sortKey, setSortKey] = useState('discrepancy')
  const [sortDir, setSortDir] = useState('desc')
  const [filter, setFilter] = useState('')

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const filtered = disputes.filter(d =>
    !filter ||
    d.employee_name.toLowerCase().includes(filter.toLowerCase()) ||
    String(d.employee_number).includes(filter) ||
    d.comp_plan_name.toLowerCase().includes(filter.toLowerCase()) ||
    d.job_code.toLowerCase().includes(filter.toLowerCase())
  )

  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey]
    if (typeof av === 'number') return sortDir === 'asc' ? av - bv : bv - av
    return sortDir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av))
  })

  const cols = [
    { key: 'employee_number', label: 'Emp #',       align: 'left'  },
    { key: 'employee_name',   label: 'Name',         align: 'left'  },
    { key: 'job_code',        label: 'Level',        align: 'left'  },
    { key: 'comp_plan_name',  label: 'Plan',         align: 'left'  },
    { key: 'fiscal_year',     label: 'Period',       align: 'left'  },
    { key: 'eligible_sales',  label: 'Eligible Sales', align: 'right'},
    { key: 'estimated_commission', label: 'Owed',    align: 'right' },
    { key: 'total_paid',      label: 'Paid',         align: 'right' },
    { key: 'discrepancy',     label: 'Gap',          align: 'right' },
  ]

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return <span className="text-slate-300 ml-1">↕</span>
    return <span className="text-indigo-500 ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-4 flex-wrap">
        <p className="text-sm font-semibold text-slate-700">
          {sorted.length} dispute record{sorted.length !== 1 ? 's' : ''}
          {filter && <span className="text-slate-400 font-normal"> (filtered from {disputes.length})</span>}
        </p>
        <input
          type="text"
          placeholder="Filter by name, ID, plan, level…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 w-64 focus:outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-100">
              {cols.map(col => (
                <th
                  key={col.key}
                  onClick={() => toggleSort(col.key)}
                  className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400 cursor-pointer select-none whitespace-nowrap hover:text-slate-600 ${col.align === 'right' ? 'text-right' : 'text-left'}`}
                >
                  {col.label}<SortIcon col={col.key} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={cols.length} className="px-4 py-8 text-center text-slate-400 text-sm">
                  No records match your filter.
                </td>
              </tr>
            ) : (
              sorted.map((d, i) => (
                <tr key={`${d.employee_number}-${d.comp_plan_id}-${d.fiscal_year}-${d.quarter_number}`}
                    className={`hover:bg-slate-50 transition-colors ${i % 2 === 0 ? '' : 'bg-slate-50/40'}`}>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">{d.employee_number}</td>
                  <td className="px-4 py-3 font-medium text-slate-800 whitespace-nowrap">{d.employee_name}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${JOB_COLORS[d.job_code] ?? JOB_COLORS.UNKNOWN}`}>
                      {JOB_LABELS[d.job_code] ?? d.job_code}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{d.comp_plan_name}</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className="text-xs font-mono text-slate-500">FY{d.fiscal_year} Q{d.quarter_number}</span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-slate-500">{fmt(d.eligible_sales)}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-blue-600">{fmt(d.estimated_commission)}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-emerald-600">
                    {d.total_paid > 0 ? fmt(d.total_paid) : <span className="text-slate-300">—</span>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className="inline-block font-mono text-xs font-semibold text-red-600 bg-red-50 border border-red-100 rounded px-2 py-0.5">
                      {fmt(d.discrepancy)}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function DisputePredictorPage() {
  const [state, setState] = useState({ status: 'idle', data: null, error: null })

  const load = useCallback(async () => {
    setState({ status: 'loading', data: null, error: null })
    try {
      const res = await fetch('/dispute-predictor')
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setState({ status: 'done', data, error: null })
    } catch (err) {
      setState({ status: 'error', data: null, error: err.message })
    }
  }, [])

  useEffect(() => { load() }, [load])

  const { status, data, error } = state

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Dispute Predictor</h2>
          <p className="text-sm text-slate-400 mt-0.5">
            Employees with qualifying sales and active comp plans who were not fully paid
          </p>
        </div>
        <button
          onClick={load}
          disabled={status === 'loading'}
          className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {status === 'loading' ? (
            <>
              <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Running…
            </>
          ) : (
            <>
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h5M20 20v-5h-5" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M20 9A8 8 0 005.07 7M4 15a8 8 0 0014.93 2" />
              </svg>
              Refresh
            </>
          )}
        </button>
      </div>

      {/* Loading skeleton */}
      {status === 'loading' && (
        <div className="space-y-6 animate-pulse">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-slate-100 rounded-xl" />
            ))}
          </div>
          <div className="h-40 bg-slate-100 rounded-xl" />
          <div className="h-64 bg-slate-100 rounded-xl" />
        </div>
      )}

      {/* Error */}
      {status === 'error' && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700 flex items-start gap-3">
          <svg className="w-4 h-4 mt-0.5 flex-shrink-0 text-red-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12zm0-9a1 1 0 011 1v3a1 1 0 11-2 0V8a1 1 0 011-1zm0 6a1 1 0 100 2 1 1 0 000-2z" clipRule="evenodd" />
          </svg>
          <div>
            <p className="font-semibold">Analysis failed</p>
            <p className="mt-0.5 text-red-600">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {status === 'done' && data && (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard
              label="Affected Employees"
              value={data.summary.affected_employees}
              sub="with payment gaps"
              accent="red"
            />
            <StatCard
              label="Total Discrepancy"
              value={fmt(data.summary.total_discrepancy)}
              sub="owed but not paid"
              accent="amber"
            />
            <StatCard
              label="Total Owed"
              value={fmt(data.summary.total_owed)}
              sub="across all affected periods"
              accent="indigo"
            />
            <StatCard
              label="Total Paid"
              value={fmt(data.summary.total_paid)}
              sub="partial payments included"
              accent="emerald"
            />
          </div>

          {/* Job breakdown */}
          <JobBreakdownBar items={data.summary.by_job_code} />

          {/* Disputes table */}
          {data.disputes.length === 0 ? (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-6 py-8 text-center">
              <p className="text-emerald-700 font-semibold text-sm">No payment gaps detected</p>
              <p className="text-emerald-500 text-xs mt-1">All employees with qualifying sales have been fully compensated.</p>
            </div>
          ) : (
            <DisputeTable disputes={data.disputes} />
          )}
        </>
      )}
    </div>
  )
}
