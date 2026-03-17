import AgentCard from './AgentCard.jsx'
import Skeleton from './Skeleton.jsx'

const CONFIDENCE_COLORS = {
  HIGH:   'bg-emerald-100 text-emerald-700 border-emerald-200',
  MEDIUM: 'bg-amber-100 text-amber-700 border-amber-200',
  LOW:    'bg-red-100 text-red-700 border-red-200',
}

function EvidenceList({ evidence }) {
  if (!evidence || evidence.length === 0) return (
    <p className="text-xs text-slate-400 italic">No evidence collected</p>
  )

  return (
    <ol className="space-y-2">
      {evidence.map((item, i) => (
        <li key={i} className="flex items-start gap-2.5">
          <span className="flex-shrink-0 mt-0.5 w-4 h-4 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 text-xs font-bold">
            {i + 1}
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center flex-wrap gap-1.5">
              <span className="inline-block px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 text-xs font-mono border border-slate-200">
                {item.tool}
              </span>
              {item.error ? (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-red-50 border border-red-200 text-xs font-semibold text-red-600">
                  <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                  ERR
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-50 border border-emerald-200 text-xs font-semibold text-emerald-600">
                  <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                  OK
                </span>
              )}
            </div>
            {item.description && (
              <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{item.description}</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}

function ForensicSummary({ summary, queryType }) {
  if (!summary) return <Skeleton lines={4} />

  if (queryType === 'other') {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-4">
        <div className="flex items-center gap-2 mb-2">
          <svg className="w-4 h-4 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <span className="text-sm font-semibold text-amber-800">Forwarded to Compensation Admin</span>
        </div>
        <p className="text-sm text-amber-700 leading-relaxed">
          This query has been forwarded to the Compensation Administration team for manual review.
        </p>
        {summary.recommendation && (
          <p className="text-sm text-amber-700 mt-2 leading-relaxed">{summary.recommendation}</p>
        )}
      </div>
    )
  }

  const confidence = summary.confidence?.toUpperCase()
  const confColor = CONFIDENCE_COLORS[confidence] || CONFIDENCE_COLORS.MEDIUM

  return (
    <div className="space-y-3">
      {/* Expected */}
      {summary.expected && (
        <div className="rounded-lg border-l-4 border-blue-400 bg-blue-50/60 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-blue-500 mb-1">Expected</p>
          <p className="text-sm text-slate-700 leading-relaxed">{summary.expected}</p>
        </div>
      )}

      {/* Actual */}
      {summary.actual && (
        <div className="rounded-lg border-l-4 border-amber-400 bg-amber-50/60 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-amber-500 mb-1">Actual</p>
          <p className="text-sm text-slate-700 leading-relaxed">{summary.actual}</p>
        </div>
      )}

      {/* Root Cause */}
      {summary.root_cause && (
        <div className="rounded-lg border-l-4 border-red-400 bg-red-50/60 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-red-500 mb-1">Root Cause</p>
          <p className="text-sm text-slate-700 leading-relaxed">{summary.root_cause}</p>
        </div>
      )}

      {/* Recommendation */}
      {summary.recommendation && (
        <div className="rounded-lg border-l-4 border-emerald-400 bg-emerald-50/60 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-emerald-500 mb-1">Recommendation</p>
          <p className="text-sm text-slate-700 leading-relaxed">{summary.recommendation}</p>
        </div>
      )}

      {/* Confidence */}
      {confidence && (
        <div className="flex items-center gap-2 pt-1">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Confidence:</p>
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${confColor}`}>
            {confidence}
          </span>
        </div>
      )}
    </div>
  )
}

export default function InvestigationCard({ status, result, plannerResult }) {
  const evidence = result?.evidence
  const summary  = result?.summary
  const queryType = result?.query_type || plannerResult?.query_type

  const inputPanel = (
    <div>
      {(status === 'idle') && <Skeleton lines={4} />}
      {(status === 'running') && (
        <div>
          <p className="text-xs text-emerald-600 font-medium mb-3 animate-pulse-soft">
            Executing investigation steps…
          </p>
          <EvidenceList evidence={evidence || []} />
        </div>
      )}
      {(status === 'done' || status === 'error') && (
        <EvidenceList evidence={evidence || []} />
      )}
    </div>
  )

  const outputPanel = (
    <div>
      {(status === 'idle' || status === 'running') && <Skeleton lines={5} />}
      {(status === 'done' || status === 'error') && (
        <ForensicSummary summary={summary} queryType={queryType} />
      )}
    </div>
  )

  return (
    <AgentCard
      num={3}
      name="Investigation Agent"
      desc="Executes tools and synthesises findings"
      accent="#059669"
      status={status}
      inputPanel={inputPanel}
      outputPanel={outputPanel}
    />
  )
}
