export default function Header() {
  return (
    <header className="bg-slate-900 border-b border-slate-700/60 shadow-lg">
      <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-4">
        {/* Icon */}
        <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center shadow-md">
          <svg width="20" height="20" fill="none" stroke="white" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>

        {/* Text */}
        <div>
          <h1 className="text-white font-semibold text-lg leading-tight tracking-tight">
            ICM Investigation Pipeline
          </h1>
          <p className="text-slate-400 text-xs mt-0.5">
            AI-powered compensation query investigation
          </p>
        </div>

        {/* Spacer + badge */}
        <div className="ml-auto">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-xs text-slate-400 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            Live
          </span>
        </div>
      </div>
    </header>
  )
}
