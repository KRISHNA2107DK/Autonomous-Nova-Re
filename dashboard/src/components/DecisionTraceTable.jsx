import { pct, shortName } from '../lib/format'

const STATUS_PILL = {
  RECOVERED: 'bg-emerald-600 text-white',
  MASKED: 'bg-amber-500 text-black',
  MITIGATED: 'bg-amber-500 text-black',
  FAILED: 'bg-red-700 text-white',
  ABORTED: 'bg-red-700 text-white',
  UNDETECTED: 'bg-red-900 text-red-100',
  SKIPPED: 'bg-slate-600 text-white',
  SKIPPED_PREFLIGHT: 'bg-slate-600 text-white',
}

const sec = (v) => (v === null || v === undefined ? '—' : `${Math.round(v)}s`)

function Check({ ok }) {
  if (ok === undefined || ok === null) return null
  return <span className={ok ? 'text-emerald-400' : 'text-red-400'}>{ok ? ' ✓' : ' ✗'}</span>
}

/** One row per round, straight from the persisted round records. */
export default function DecisionTraceTable({ rounds }) {
  if (!rounds?.length) {
    return <div className="h-full flex items-center justify-center text-slate-500 text-xs">No campaign rounds yet.</div>
  }
  return (
    <div className="h-full overflow-auto scroll-thin">
      <table className="w-full text-[11px] border-collapse">
        <thead className="sticky top-0 bg-slate-800 text-slate-400">
          <tr>
            {['#', 'Fault', 'Target', 'Diagnosed as', 'RCA origin', 'Action', 'TTD', 'TTR', 'SLA', 'Users failed', 'Status'].map((h) => (
              <th key={h} className="px-2 py-1.5 text-left font-semibold whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rounds.map((r) => {
            const sla = r.sla || {}
            const rca = r.rca || {}
            const acts = (r.remediations || []).map((a) => `${a.remediator}${a.verified ? '✓' : '✗'}`).join(' → ')
            const live = !['RECOVERED', 'MASKED', 'MITIGATED', 'FAILED', 'ABORTED', 'UNDETECTED', 'SKIPPED', 'SKIPPED_PREFLIGHT'].includes(r.status)
            return (
              <tr key={`${r.campaign_id}-${r.round}`} className="border-b border-slate-800 hover:bg-slate-800/60">
                <td className="px-2 py-1.5 mono text-slate-300">{r.round}</td>
                <td className="px-2 py-1.5 text-fuchsia-300 whitespace-nowrap">{r.injector}</td>
                <td className="px-2 py-1.5 text-blue-300 whitespace-nowrap">{shortName(r.target) || '—'}</td>
                <td className="px-2 py-1.5 whitespace-nowrap">
                  {rca.anomaly_type || '—'}{rca.anomaly_type && <Check ok={r.classification_correct} />}
                </td>
                <td className="px-2 py-1.5 whitespace-nowrap">
                  {shortName(rca.origin) || '—'}{rca.origin && <Check ok={r.diagnosis_correct} />}
                </td>
                <td className="px-2 py-1.5 text-slate-300 whitespace-nowrap">{acts || '—'}</td>
                <td className={`px-2 py-1.5 mono ${sla.detection_met ? 'text-emerald-300' : 'text-amber-300'}`}>{sec(sla.ttd_seconds)}</td>
                <td className={`px-2 py-1.5 mono ${sla.recovery_met ? 'text-emerald-300' : 'text-amber-300'}`}>{sec(sla.ttr_seconds)}</td>
                <td className="px-2 py-1.5 mono">{r.sla ? (sla.recovery_met ? <span className="text-emerald-400">MET</span> : <span className="text-red-400">MISS</span>) : '—'}</td>
                <td className="px-2 py-1.5 mono text-slate-300">{pct(r.user_impact?.failure_ratio, 1)}</td>
                <td className="px-2 py-1.5">
                  <span className={`px-1.5 py-px rounded text-[9px] font-bold ${STATUS_PILL[r.status] || 'bg-amber-500 text-black'} ${live ? 'animate-pulse' : ''}`}>
                    {r.status}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
