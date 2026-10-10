import { useState } from 'react'
import { ms, num, pct } from '../lib/format'

function Chip({ label, value, tone = 'text-slate-200' }) {
  return (
    <div className="flex flex-col leading-tight px-3 border-l border-slate-800">
      <span className="text-[9px] uppercase tracking-widest text-slate-500">{label}</span>
      <span className={`mono text-sm font-semibold ${tone}`}>{value}</span>
    </div>
  )
}

export default function Header({ connected, frame, campaigns, api }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const campaign = frame?.campaign
  const running = campaign?.status === 'RUNNING'
  const sli = frame?.user_sli || {}
  const failure = sli.failure_ratio
  const last = campaigns?.find((c) => c.report)
  const autopilot = frame?.autopilot

  const act = async (fn) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <header className="shrink-0 px-4 py-2 flex items-center gap-4 border-b border-slate-800 bg-[#0b1220]">
      <div className="flex items-center gap-2 min-w-[250px]">
        <img src="/favicon.svg" alt="" className="w-6 h-6" />
        <div className="leading-tight">
          <div className="text-base font-extrabold tracking-tight text-white">NovaSurge</div>
          <div className="text-[10px] text-slate-500">Autonomous chaos engineering &amp; self-healing</div>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs">
        <span className={`flex items-center gap-1.5 font-semibold ${connected ? 'text-emerald-400' : 'text-red-400'}`}>
          <span className={`inline-block w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
          {connected ? 'LIVE' : 'RECONNECTING'}
        </span>
        {frame && !frame.prometheus_ok && (
          <span className="px-2 py-0.5 rounded bg-red-900 text-red-200 font-semibold">PROMETHEUS DOWN</span>
        )}
      </div>

      <div className="flex items-stretch">
        <Chip label="user req/s" value={num(sli.rps, 1)} />
        <Chip label="user failures" value={pct(failure, 2)}
          tone={failure > 0.05 ? 'text-red-400' : failure > 0.005 ? 'text-amber-300' : 'text-emerald-300'} />
        <Chip label="user p99" value={ms(sli.p99_ms)} tone={sli.p99_ms > 1000 ? 'text-red-400' : 'text-slate-200'} />
        {last?.report && (
          <Chip label="last resilience score" value={`${last.report.resilience_score}/100`}
            tone={last.report.resilience_score >= 75 ? 'text-emerald-300' : 'text-amber-300'} />
        )}
      </div>

      <div className="flex-1 text-center text-xs">
        {running ? (
          <span className="text-slate-300">
            Round <b className="text-white">{campaign.round}/{campaign.total_rounds}</b>
            {campaign.injector && <> · <span className="text-fuchsia-300">{campaign.injector}</span></>}
            {campaign.target && <> → <span className="text-blue-300">{campaign.target}</span></>}
            {' · '}<span className="text-amber-300 font-semibold">{campaign.phase}</span>
          </span>
        ) : (
          <span className="text-slate-500">No campaign running{autopilot?.healing ? ' · autopilot healing…' : ''}</span>
        )}
        {error && <span className="ml-3 text-red-400">{error}</span>}
      </div>

      <div className="flex items-center gap-2 text-xs">
        <button
          type="button"
          disabled={!connected || busy}
          onClick={() => act(() => api('/api/autopilot', { enabled: !autopilot?.enabled }))}
          className={`px-3 py-1.5 rounded font-semibold border ${autopilot?.enabled ? 'border-pink-500 text-pink-300' : 'border-slate-600 text-slate-400'} disabled:opacity-40`}
          title="Autopilot heals anomalies that occur outside campaigns"
        >
          Autopilot {autopilot?.enabled ? 'ON' : 'OFF'}
        </button>
        {running ? (
          <button type="button" disabled={busy} onClick={() => act(() => api('/api/campaign/stop'))}
            className="px-3 py-1.5 rounded font-semibold bg-slate-700 hover:bg-slate-600 disabled:opacity-40">
            Stop after round
          </button>
        ) : (
          <button type="button" disabled={!connected || busy} onClick={() => act(() => api('/api/campaign/start'))}
            className="px-3 py-1.5 rounded font-semibold bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-40">
            Run 5-round campaign
          </button>
        )}
      </div>
    </header>
  )
}
