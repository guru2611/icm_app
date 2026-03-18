import { useState, useEffect, useRef } from 'react'

const JOB_LABELS = { REP: 'Rep', SREP: 'Sr. Rep', MGR: 'Manager', DM: 'Dist. Mgr' }
const JOB_COLORS = {
  REP:  'bg-slate-100 text-slate-700',
  SREP: 'bg-indigo-100 text-indigo-700',
  MGR:  'bg-amber-100 text-amber-700',
  DM:   'bg-rose-100 text-rose-700',
}

function ProfileCard({ profile }) {
  const jc = profile.job_code
  return (
    <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm">
      <div className="flex items-center gap-2 mb-2">
        <svg className="w-4 h-4 text-emerald-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
        </svg>
        <span className="font-semibold text-emerald-800">{profile.name}</span>
        {jc && (
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${JOB_COLORS[jc] ?? 'bg-slate-100 text-slate-600'}`}>
            {JOB_LABELS[jc] ?? jc}
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-emerald-700">
        {profile.store_name && (
          <div><span className="font-medium text-emerald-600">Store</span> · {profile.store_name}</div>
        )}
        {profile.location_name && (
          <div><span className="font-medium text-emerald-600">Location</span> · {profile.location_name}</div>
        )}
        {profile.district && (
          <div><span className="font-medium text-emerald-600">District</span> · {profile.district}</div>
        )}
        {profile.market && (
          <div><span className="font-medium text-emerald-600">Market</span> · {profile.market}</div>
        )}
        {profile.territory && (
          <div><span className="font-medium text-emerald-600">Territory</span> · {profile.territory}</div>
        )}
        {profile.supervisor && (
          <div><span className="font-medium text-emerald-600">Supervisor</span> · {profile.supervisor}</div>
        )}
      </div>
    </div>
  )
}

export default function InputForm({ emp, query, running, submitted, onChange, onSubmit, onReset }) {
  const [lookup, setLookup] = useState({ status: 'idle', profile: null })
  const debounceRef = useRef(null)

  useEffect(() => {
    const num = parseInt(emp, 10)
    if (!emp || isNaN(num) || num < 1) {
      setLookup({ status: 'idle', profile: null })
      return
    }

    setLookup({ status: 'loading', profile: null })
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`/employee/${num}`)
        if (res.ok) {
          const data = await res.json()
          setLookup({ status: 'found', profile: data })
        } else {
          setLookup({ status: 'notfound', profile: null })
        }
      } catch {
        setLookup({ status: 'idle', profile: null })
      }
    }, 400)

    return () => clearTimeout(debounceRef.current)
  }, [emp])

  const employeeValid = lookup.status === 'found'
  const frozen = submitted
  const queryDisabled = frozen || running || !employeeValid

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit()
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
      <h2 className="text-base font-semibold text-slate-800 mb-1">Submit Compensation Query</h2>
      <p className="text-xs text-slate-500 mb-5">
        Enter an employee number and describe the compensation issue in natural language.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Employee number */}
        <div>
          <label className="block text-xs font-medium uppercase tracking-wide text-slate-500 mb-1.5">
            Employee Number
          </label>
          <div className="flex items-center gap-3">
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={emp}
              onChange={e => onChange('emp', e.target.value.replace(/\D/g, ''))}
              placeholder="e.g. 141"
              disabled={frozen || running}
              className="w-44 px-3 py-2 rounded-lg border border-slate-300 text-sm text-slate-800 placeholder-slate-400
                         focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500
                         disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed
                         transition-colors"
            />
            {lookup.status === 'loading' && (
              <span className="flex items-center gap-1.5 text-xs text-slate-400">
                <svg className="animate-spin w-3 h-3" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Looking up…
              </span>
            )}
            {lookup.status === 'notfound' && (
              <span className="flex items-center gap-1.5 text-xs text-red-500 font-medium">
                <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12zm0-9a1 1 0 011 1v3a1 1 0 11-2 0V8a1 1 0 011-1zm0 6a1 1 0 100 2 1 1 0 000-2z" clipRule="evenodd" />
                </svg>
                Employee not found
              </span>
            )}
          </div>

          {/* Profile details card */}
          {lookup.status === 'found' && lookup.profile && (
            <ProfileCard profile={lookup.profile} />
          )}
        </div>

        {/* Query text */}
        <div>
          <label className={`block text-xs font-medium uppercase tracking-wide mb-1.5 ${queryDisabled ? 'text-slate-300' : 'text-slate-500'}`}>
            Query
          </label>
          <textarea
            rows={3}
            value={query}
            onChange={e => onChange('query', e.target.value)}
            placeholder={employeeValid ? "e.g. I didn't receive my commission for the Apple vendor bonus in January 2026…" : 'Enter a valid employee number first…'}
            disabled={queryDisabled}
            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm text-slate-800 placeholder-slate-400
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500
                       disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed
                       resize-none transition-colors"
          />
        </div>

        {/* Submit / Reset button */}
        {frozen ? (
          <button
            type="button"
            onClick={onReset}
            disabled={running}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg
                       bg-slate-700 hover:bg-slate-800 active:bg-slate-900
                       text-white text-sm font-semibold
                       disabled:bg-slate-300 disabled:text-slate-500 disabled:cursor-not-allowed
                       transition-all duration-150 shadow-sm hover:shadow-md"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New Consultation
          </button>
        ) : (
          <button
            type="submit"
            disabled={running || !employeeValid || !query.trim()}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg
                       bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800
                       text-white text-sm font-semibold
                       disabled:bg-slate-300 disabled:text-slate-500 disabled:cursor-not-allowed
                       transition-all duration-150 shadow-sm hover:shadow-md"
          >
            {running ? (
              <>
                <svg className="animate-spin w-4 h-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Consulting Agents…
              </>
            ) : (
              <>
                Consult Agents
                <span className="text-indigo-300">→</span>
              </>
            )}
          </button>
        )}
      </form>
    </div>
  )
}
