import { useState, useEffect, useCallback } from 'react'

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtDuration(ms) {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

// ── Badge configs ──────────────────────────────────────────────────────────────

const ACTION_STYLES = {
  investigate:       'bg-indigo-100 text-indigo-700',
  slack_investigate: 'bg-violet-100 text-violet-700',
  employee_lookup:   'bg-sky-100 text-sky-700',
  dispute_predictor: 'bg-amber-100 text-amber-700',
}
const ACTION_LABELS = {
  investigate:       'Investigate',
  slack_investigate: 'Slack Investigate',
  employee_lookup:   'Employee Lookup',
  dispute_predictor: 'Dispute Predictor',
}

const SOURCE_STYLES = {
  web:   'bg-slate-100 text-slate-600',
  slack: 'bg-emerald-100 text-emerald-700',
  api:   'bg-orange-100 text-orange-700',
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, accent }) {
  const borders = {
    indigo:  'border-l-indigo-400',
    emerald: 'border-l-emerald-400',
    amber:   'border-l-amber-400',
    red:     'border-l-red-400',
  }
  return (
    <div className={`bg-white rounded-xl border border-slate-200 border-l-4 ${borders[accent] ?? 'border-l-slate-300'} px-5 py-4 shadow-sm`}>
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-1">{label}</p>
      <p className="text-2xl font-bold text-slate-800">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
    </div>
  )
}

function ActionBreakdown({ items }) {
  if (!items || items.length === 0) return null
  const max = Math.max(...items.map(i => i.count), 1)
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-4">Activity by Type</p>
      <div className="space-y-3">
        {items.map(item => {
          const pct = Math.round((item.count / max) * 100)
          const style = ACTION_STYLES[item.action] ?? 'bg-slate-100 text-slate-600'
          const label = ACTION_LABELS[item.action] ?? item.action
          const barColor = {
            investigate:       'bg-indigo-400',
            slack_investigate: 'bg-violet-400',
            employee_lookup:   'bg-sky-400',
            dispute_predictor: 'bg-amber-400',
          }[item.action] ?? 'bg-slate-400'
          return (
            <div key={item.action}>
              <div className="flex items-center justify-between mb-1">
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${style}`}>{label}</span>
                <span className="text-sm font-bold text-slate-600">{item.count}</span>
              </div>
              <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function EventsTable({ events }) {
  const [filter, setFilter] = useState('')
  const [actionFilter, setActionFilter] = useState('all')

  const actions = ['all', ...Array.from(new Set(events.map(e => e.action)))]

  const filtered = events.filter(e => {
    const matchesAction = actionFilter === 'all' || e.action === actionFilter
    const q = filter.toLowerCase()
    const matchesSearch = !q ||
      (e.actor || '').toLowerCase().includes(q) ||
      String(e.target_employee_number ?? '').includes(q) ||
      (e.query_text || '').toLowerCase().includes(q) ||
      (e.ip_address || '').includes(q)
    return matchesAction && matchesSearch
  })

  if (events.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-6 py-12 text-center">
        <svg className="w-10 h-10 text-slate-300 mx-auto mb-3" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3-10.5H18a2.25 2.25 0 012.25 2.25V19.5A2.25 2.25 0 0118 21.75H6A2.25 2.25 0 013.75 19.5V7.5A2.25 2.25 0 016 5.25h.75" />
        </svg>
        <p className="text-slate-500 font-medium text-sm">No audit events for this date</p>
        <p className="text-slate-400 text-xs mt-1">Activity will appear here once requests are made</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Table toolbar */}
      <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between gap-3 flex-wrap bg-slate-50/60">
        <p className="text-sm font-semibold text-slate-700">
          {filtered.length} event{filtered.length !== 1 ? 's' : ''}
          {(filter || actionFilter !== 'all') && (
            <span className="text-slate-400 font-normal"> (filtered from {events.length})</span>
          )}
        </p>
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={actionFilter}
            onChange={e => setActionFilter(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-600 focus:outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
          >
            {actions.map(a => (
              <option key={a} value={a}>
                {a === 'all' ? 'All actions' : (ACTION_LABELS[a] ?? a)}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Search actor, employee, query…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 w-56 focus:outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
          />
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100">
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400 whitespace-nowrap">Time</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Actor</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Action</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Source</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400 whitespace-nowrap">Employee</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Query</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Status</th>
              <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-400 whitespace-nowrap">Duration</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-slate-400 text-sm">
                  No events match your filter.
                </td>
              </tr>
            ) : (
              filtered.map(e => (
                <tr key={e.log_id} className="hover:bg-slate-50/70 transition-colors">
                  {/* Time */}
                  <td className="px-4 py-3 font-mono text-xs text-slate-400 whitespace-nowrap">
                    {fmtTime(e.timestamp)}
                  </td>

                  {/* Actor */}
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="flex items-center gap-1.5">
                      <div className="w-5 h-5 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                        <svg className="w-3 h-3 text-indigo-500" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <span className="text-xs text-slate-700 font-medium">{e.actor || 'anonymous'}</span>
                    </div>
                  </td>

                  {/* Action badge */}
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${ACTION_STYLES[e.action] ?? 'bg-slate-100 text-slate-600'}`}>
                      {ACTION_LABELS[e.action] ?? e.action}
                    </span>
                  </td>

                  {/* Source badge */}
                  <td className="px-4 py-3">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${SOURCE_STYLES[e.source] ?? 'bg-slate-100 text-slate-500'}`}>
                      {e.source || '—'}
                    </span>
                  </td>

                  {/* Employee # */}
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {e.target_employee_number ?? <span className="text-slate-300">—</span>}
                  </td>

                  {/* Query text (truncated) */}
                  <td className="px-4 py-3 max-w-xs">
                    {e.query_text ? (
                      <span className="text-xs text-slate-500 line-clamp-1" title={e.query_text}>
                        {e.query_text}
                      </span>
                    ) : (
                      <span className="text-slate-300 text-xs">—</span>
                    )}
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3">
                    {e.result_status === 'success' ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 bg-emerald-50 border border-emerald-100 rounded-full px-2 py-0.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        OK
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-600 bg-red-50 border border-red-100 rounded-full px-2 py-0.5" title={e.error_message ?? ''}>
                        <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                        Error
                      </span>
                    )}
                  </td>

                  {/* Duration */}
                  <td className="px-4 py-3 text-right font-mono text-xs text-slate-400 whitespace-nowrap">
                    {fmtDuration(e.duration_ms)}
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

// ── Main page ──────────────────────────────────────────────────────────────────

export default function AuditPage() {
  const [date, setDate] = useState(today())
  const [state, setState] = useState({ status: 'idle', data: null, error: null })

  const load = useCallback(async (d) => {
    setState({ status: 'loading', data: null, error: null })
    try {
      const res = await fetch(`/audit-log?date=${d}`)
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setState({ status: 'done', data, error: null })
    } catch (err) {
      setState({ status: 'error', data: null, error: err.message })
    }
  }, [])

  useEffect(() => { load(date) }, [load, date])

  const handleDateChange = (e) => {
    setDate(e.target.value)
  }

  const { status, data, error } = state

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Audit Log</h2>
          <p className="text-sm text-slate-400 mt-0.5">
            Immutable record of all data access and investigation activity
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={date}
            max={today()}
            onChange={handleDateChange}
            className="text-sm border border-slate-200 rounded-lg px-3 py-2 text-slate-700 focus:outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200 bg-white shadow-sm"
          />
          <button
            onClick={() => load(date)}
            disabled={status === 'loading'}
            className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
          >
            {status === 'loading' ? (
              <>
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Loading…
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
      </div>

      {/* Loading skeleton */}
      {status === 'loading' && (
        <div className="space-y-6 animate-pulse">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => <div key={i} className="h-24 bg-slate-100 rounded-xl" />)}
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
            <p className="font-semibold">Failed to load audit log</p>
            <p className="mt-0.5 text-red-600">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {status === 'done' && data && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard
              label="Total Events"
              value={data.summary.total_events}
              sub={`on ${date}`}
              accent="indigo"
            />
            <StatCard
              label="Unique Actors"
              value={data.summary.unique_actors}
              sub="distinct identities"
              accent="emerald"
            />
            <StatCard
              label="Investigations"
              value={data.summary.investigations}
              sub="queries run"
              accent="amber"
            />
            <StatCard
              label="Errors"
              value={data.summary.errors}
              sub="failed requests"
              accent="red"
            />
          </div>

          {/* Action breakdown */}
          {data.summary.by_action.length > 0 && (
            <ActionBreakdown items={data.summary.by_action} />
          )}

          {/* Events table */}
          <EventsTable events={data.events} />
        </>
      )}
    </div>
  )
}
