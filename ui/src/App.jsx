import { useState } from 'react'
import Header from './components/Header.jsx'
import InputForm from './components/InputForm.jsx'
import Pipeline from './components/Pipeline.jsx'
import DisputePredictorPage from './components/DisputePredictorPage.jsx'

const initialPipeline = {
  visible: false,
  intake:        { status: 'idle', result: null },
  planner:       { status: 'idle', result: null },
  investigation: { status: 'idle', result: null },
}

const TABS = [
  { id: 'pipeline',         label: 'The Ops Room'     },
  { id: 'dispute-predictor', label: 'Predictive Pulse' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('pipeline')
  const [emp, setEmp] = useState('')
  const [query, setQuery] = useState('')
  const [running, setRunning] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState(null)
  const [pipeline, setPipeline] = useState(initialPipeline)

  const handleChange = (field, value) => {
    if (field === 'emp') setEmp(value)
    if (field === 'query') setQuery(value)
  }

  const handleReset = () => {
    setEmp('')
    setQuery('')
    setError(null)
    setRunning(false)
    setSubmitted(false)
    setPipeline(initialPipeline)
  }

  const runPipeline = async () => {
    if (!emp || !query.trim()) return

    setError(null)
    setRunning(true)
    setSubmitted(true)
    setPipeline({
      ...initialPipeline,
      visible: true,
      intake: { status: 'running', result: null },
    })

    try {
      const response = await fetch('/investigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ employee_number: parseInt(emp, 10), query_text: query }),
      })

      if (!response.ok) {
        const text = await response.text()
        throw new Error(`Server error ${response.status}: ${text}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // keep incomplete last line

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data:')) continue

          const jsonStr = trimmed.slice(5).trim()
          if (!jsonStr) continue

          let event
          try {
            event = JSON.parse(jsonStr)
          } catch {
            continue
          }

          if (event.stage === 'intake') {
            setPipeline(prev => ({
              ...prev,
              intake:  { status: 'done',    result: event.result },
              planner: { status: 'running', result: null },
            }))
          } else if (event.stage === 'planner') {
            setPipeline(prev => ({
              ...prev,
              planner:       { status: 'done',    result: event.result },
              investigation: { status: 'running', result: null },
            }))
          } else if (event.stage === 'investigation') {
            setPipeline(prev => ({
              ...prev,
              investigation: { status: 'done', result: event.result },
            }))
          } else if (event.stage === 'done') {
            // All stages complete
          } else if (event.stage === 'error') {
            setError(event.error || 'An unknown error occurred')
            setPipeline(prev => ({
              ...prev,
              intake:        prev.intake.status === 'running'        ? { status: 'error', result: null } : prev.intake,
              planner:       prev.planner.status === 'running'       ? { status: 'error', result: null } : prev.planner,
              investigation: prev.investigation.status === 'running' ? { status: 'error', result: null } : prev.investigation,
            }))
          }
        }
      }
    } catch (err) {
      setError(err.message)
      setPipeline(prev => ({
        ...prev,
        intake:        prev.intake.status === 'running'        ? { status: 'error', result: null } : prev.intake,
        planner:       prev.planner.status === 'running'       ? { status: 'error', result: null } : prev.planner,
        investigation: prev.investigation.status === 'running' ? { status: 'error', result: null } : prev.investigation,
      }))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      {/* Tab bar */}
      <div className="border-b border-slate-200 bg-white">
        <div className="max-w-5xl mx-auto px-4">
          <nav className="flex gap-1 -mb-px">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8 space-y-8">
        <div className={activeTab === 'pipeline' ? '' : 'hidden'}>
          <div className="space-y-8">
            <InputForm
              emp={emp}
              query={query}
              running={running}
              submitted={submitted}
              onChange={handleChange}
              onSubmit={runPipeline}
              onReset={handleReset}
            />

            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700 flex items-start gap-3">
                <span className="mt-0.5 text-red-500 flex-shrink-0">
                  <svg width="16" height="16" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12zm0-9a1 1 0 011 1v3a1 1 0 11-2 0V8a1 1 0 011-1zm0 6a1 1 0 100 2 1 1 0 000-2z" clipRule="evenodd" />
                  </svg>
                </span>
                <div>
                  <p className="font-semibold">Pipeline Error</p>
                  <p className="mt-0.5 text-red-600">{error}</p>
                </div>
              </div>
            )}

            {pipeline.visible && (
              <Pipeline pipeline={pipeline} emp={emp} query={query} />
            )}
          </div>
        </div>

        <div className={activeTab === 'dispute-predictor' ? '' : 'hidden'}>
          <DisputePredictorPage />
        </div>
      </main>
    </div>
  )
}
