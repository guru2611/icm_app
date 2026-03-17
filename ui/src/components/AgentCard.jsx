import StatusBadge from './StatusBadge.jsx'

export default function AgentCard({ num, name, desc, accent, status, inputPanel, outputPanel }) {
  const isActive = status === 'running' || status === 'done'

  return (
    <div
      className={`bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden transition-all duration-300
        ${isActive ? 'shadow-md' : 'opacity-60'}`}
      style={{ borderLeftWidth: '4px', borderLeftColor: accent }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-100">
        {/* Number badge */}
        <div
          className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold shadow-sm"
          style={{ backgroundColor: accent }}
        >
          {num}
        </div>

        {/* Name + desc */}
        <div className="flex-1 min-w-0">
          <span className="text-sm font-semibold text-slate-800">{name}</span>
          <span className="ml-2 text-xs text-slate-500">{desc}</span>
        </div>

        {/* Status badge */}
        <StatusBadge status={status} />
      </div>

      {/* Body: two-column grid */}
      <div className="grid grid-cols-2 divide-x divide-slate-100">
        {/* Input column */}
        <div className="p-5">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-3">
            Input
          </p>
          <div className="transition-all duration-300">
            {inputPanel}
          </div>
        </div>

        {/* Output column */}
        <div className="p-5">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-3">
            Output
          </p>
          <div className="transition-all duration-300">
            {outputPanel}
          </div>
        </div>
      </div>
    </div>
  )
}
