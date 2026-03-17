import IntakeCard from './IntakeCard.jsx'
import PlannerCard from './PlannerCard.jsx'
import InvestigationCard from './InvestigationCard.jsx'
import Connector from './Connector.jsx'

export default function Pipeline({ pipeline, emp, query }) {
  const { intake, planner, investigation } = pipeline

  return (
    <div className="space-y-0">
      <IntakeCard
        status={intake.status}
        result={intake.result}
        emp={emp}
        query={query}
      />

      <Connector />

      <PlannerCard
        status={planner.status}
        result={planner.result}
        intakeResult={intake.result}
      />

      <Connector />

      <InvestigationCard
        status={investigation.status}
        result={investigation.result}
        plannerResult={planner.result}
      />
    </div>
  )
}
