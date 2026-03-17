export default function InputForm({ emp, query, running, onChange, onSubmit }) {
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
          <input
            type="number"
            value={emp}
            onChange={e => onChange('emp', e.target.value)}
            placeholder="e.g. 141"
            disabled={running}
            className="w-44 px-3 py-2 rounded-lg border border-slate-300 text-sm text-slate-800 placeholder-slate-400
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500
                       disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed
                       transition-colors"
          />
        </div>

        {/* Query text */}
        <div>
          <label className="block text-xs font-medium uppercase tracking-wide text-slate-500 mb-1.5">
            Query
          </label>
          <textarea
            rows={3}
            value={query}
            onChange={e => onChange('query', e.target.value)}
            placeholder="e.g. I didn't receive my commission for the Apple vendor bonus in January 2026..."
            disabled={running}
            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm text-slate-800 placeholder-slate-400
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500
                       disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed
                       resize-none transition-colors"
          />
        </div>

        {/* Submit button */}
        <button
          type="submit"
          disabled={running || !emp || !query.trim()}
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
              Investigating…
            </>
          ) : (
            <>
              Investigate
              <span className="text-indigo-300">→</span>
            </>
          )}
        </button>
      </form>
    </div>
  )
}
