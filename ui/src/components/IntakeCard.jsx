import AgentCard from './AgentCard.jsx'
import Skeleton from './Skeleton.jsx'

const QUERY_TYPE_LABELS = {
  commission_not_received:      { label: 'Commission Not Received', color: 'bg-red-100 text-red-700 border-red-200' },
  incorrect_commission_received: { label: 'Incorrect Commission',    color: 'bg-amber-100 text-amber-700 border-amber-200' },
  how_much_commission:           { label: 'How Much Commission',     color: 'bg-blue-100 text-blue-700 border-blue-200' },
  other:                         { label: 'Other',                   color: 'bg-amber-100 text-amber-700 border-amber-200' },
}

function KV({ label, value, mono = false }) {
  return (
    <div className="mb-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-0.5">{label}</p>
      <p className={`text-sm text-slate-700 ${mono ? 'font-mono' : ''}`}>{value}</p>
    </div>
  )
}

export default function IntakeCard({ status, result, emp, query }) {
  const inputPanel = (
    <div>
      <KV label="Employee #" value={emp} mono />
      <div className="mb-1">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-0.5">Raw Query</p>
        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap break-words">
          {query || <span className="text-slate-400 italic">No query entered</span>}
        </p>
      </div>
    </div>
  )

  let outputPanel
  if (status === 'idle' || status === 'running') {
    outputPanel = <Skeleton lines={4} />
  } else if (result) {
    const typeInfo = QUERY_TYPE_LABELS[result.query_type] || QUERY_TYPE_LABELS.other
    outputPanel = (
      <div>
        <div className="mb-3">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1.5">Query Type</p>
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${typeInfo.color}`}>
            {typeInfo.label}
          </span>
        </div>
        <KV label="Sale Date" value={result.sale_date ?? '—'} mono />
        <div className="mb-1">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-0.5">Summary</p>
          <p className="text-sm text-slate-700 leading-relaxed">{result.summary}</p>
        </div>
      </div>
    )
  } else {
    outputPanel = <Skeleton lines={4} />
  }

  return (
    <AgentCard
      num={1}
      name="Intake Agent"
      desc="Parses and classifies the query"
      accent="#7c3aed"
      status={status}
      inputPanel={inputPanel}
      outputPanel={outputPanel}
    />
  )
}
