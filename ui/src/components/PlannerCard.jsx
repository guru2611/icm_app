import AgentCard from './AgentCard.jsx'
import Skeleton from './Skeleton.jsx'

const QUERY_TYPE_LABELS = {
  commission_not_received:       'Commission Not Received',
  incorrect_commission_received:  'Incorrect Commission',
  how_much_commission:            'How Much Commission',
  other:                          'Other',
}

function IntakeResultFields({ intakeResult }) {
  if (!intakeResult) return <Skeleton lines={3} />
  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-0.5">Employee #</p>
        <p className="text-sm font-mono text-slate-700">{intakeResult.employee_number}</p>
      </div>
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-0.5">Query Type</p>
        <p className="text-sm text-slate-700">{QUERY_TYPE_LABELS[intakeResult.query_type] || intakeResult.query_type}</p>
      </div>
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-0.5">Sale Date</p>
        <p className="text-sm font-mono text-slate-700">{intakeResult.sale_date ?? '—'}</p>
      </div>
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-0.5">Summary</p>
        <p className="text-sm text-slate-700 leading-relaxed">{intakeResult.summary}</p>
      </div>
    </div>
  )
}

function StepList({ steps }) {
  if (!steps || steps.length === 0) return (
    <p className="text-xs text-slate-400 italic">No steps planned</p>
  )

  return (
    <ol className="space-y-4">
      {steps.map((s, i) => (
        <li key={i} className="flex gap-3">
          <div className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold mt-0.5">
            {i + 1}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center flex-wrap gap-1.5 mb-1">
              <span className="inline-block px-2 py-0.5 rounded bg-blue-50 border border-blue-200 text-blue-700 text-xs font-mono font-semibold">
                {s.tool}
              </span>
            </div>
            <p className="text-sm text-slate-700 mb-1">{s.description}</p>
            {s.args && Object.keys(s.args).length > 0 && (
              <div className="rounded bg-slate-50 border border-slate-200 px-2.5 py-1.5 overflow-x-auto custom-scroll">
                <pre className="text-xs text-slate-500 font-mono whitespace-pre-wrap break-all">
                  {JSON.stringify(s.args, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}

export default function PlannerCard({ status, result, intakeResult }) {
  const inputPanel = (
    <div>
      <p className="text-xs font-semibold text-slate-500 mb-3 italic">IntakeResult</p>
      <IntakeResultFields intakeResult={intakeResult} />
    </div>
  )

  let outputPanel
  if (status === 'idle' || status === 'running') {
    outputPanel = (
      <div>
        {status === 'running' && (
          <p className="text-xs text-blue-600 font-medium mb-3 animate-pulse-soft">
            Planning investigation steps…
          </p>
        )}
        <Skeleton lines={5} />
      </div>
    )
  } else if (result) {
    outputPanel = (
      <div>
        <div className="flex items-center gap-2 mb-4">
          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-xs font-mono font-semibold border border-slate-200">
            FY{result.fiscal_year}
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-xs font-mono font-semibold border border-slate-200">
            Q{result.quarter_number}
          </span>
          <span className="text-xs text-slate-400">{result.steps?.length ?? 0} steps</span>
        </div>
        <StepList steps={result.steps} />
      </div>
    )
  } else {
    outputPanel = <Skeleton lines={5} />
  }

  return (
    <AgentCard
      num={2}
      name="Planner Agent"
      desc="Builds the investigation plan"
      accent="#2563eb"
      status={status}
      inputPanel={inputPanel}
      outputPanel={outputPanel}
    />
  )
}
