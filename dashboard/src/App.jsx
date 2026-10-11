import useAutoHeal from './hooks/useAutoHeal'
import Panel from './components/Panel'
import Header from './components/Header'
import AnomalyScoreChart from './components/AnomalyScoreChart'
import ReasoningFeed from './components/ReasoningFeed'
import HealthGrid from './components/HealthGrid'
import DecisionTraceTable from './components/DecisionTraceTable'
import DependencyGraph from './components/DependencyGraph'
import ForecastChart from './components/ForecastChart'

export default function App() {
  const { connected, frame, buffer, events, meta, rounds, campaigns, api } = useAutoHeal()
  const threshold = frame?.threshold ?? meta?.model?.threshold ?? null

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden">
      <Header connected={connected} frame={frame} campaigns={campaigns} api={api} />

      {!connected && (
        <div className="shrink-0 bg-red-950 text-red-200 text-xs px-4 py-1.5">
          Not connected to the AutoHeal server — start it with <code className="mono">python -m novasurge serve</code>.
          Retrying automatically; no data is simulated.
        </div>
      )}

      <main className="flex-1 min-h-0 p-2 grid grid-cols-12 grid-rows-2 gap-2">
        <Panel title="Anomaly score (Isolation Forest)" className="col-span-4">
          <AnomalyScoreChart buffer={buffer} threshold={threshold} />
        </Panel>

        <Panel title="⚡ Autonomous reasoning" accent className="col-span-5"
          right={<span className="text-[10px] text-slate-500">{events.length} events</span>}>
          <ReasoningFeed events={events} />
        </Panel>

        <Panel title="System health" className="col-span-3">
          <HealthGrid frame={frame} />
        </Panel>

        <Panel title="Decision trace" className="col-span-6"
          right={rounds?.[0]?.campaign_id && <span className="mono text-[10px] text-slate-500">{rounds[0].campaign_id}</span>}>
          <DecisionTraceTable rounds={rounds} />
        </Panel>

        <Panel title="Service dependency graph" className="col-span-4">
          <DependencyGraph meta={meta} frame={frame} />
        </Panel>

        <Panel title="LSTM 60s forecast" className="col-span-2">
          <ForecastChart buffer={buffer} frame={frame} threshold={threshold} />
        </Panel>
      </main>
    </div>
  )
}
