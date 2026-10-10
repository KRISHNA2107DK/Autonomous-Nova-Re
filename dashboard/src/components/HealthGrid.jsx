import { SERVICES, STATUS_STYLE, ms, num, pct, shortName } from '../lib/format'

function Card({ name, svc }) {
  const st = STATUS_STYLE[svc?.status] || STATUS_STYLE.unknown
  const m = svc?.metrics || {}
  const r = svc?.replicas || {}
  const top = svc?.top_deviations?.[0]
  const isNotif = name === 'notification-service'
  return (
    <div className={`rounded-lg border ${st.ring} bg-slate-900/80 p-2 ${svc?.status === 'anomaly' ? 'animate-pulse' : ''}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-slate-100">{shortName(name)}</span>
        <span className={`px-1.5 py-px rounded text-[9px] font-bold ${st.pill}`}>{st.label}</span>
      </div>
      <div className="mt-1 grid grid-cols-3 gap-1 mono text-[10px] text-slate-300">
        <div><div className="text-slate-500">{isNotif ? 'evt/s' : 'req/s'}</div>{num(m.request_rate, 1)}</div>
        <div><div className="text-slate-500">p99</div>{ms(m.p99_latency_ms)}</div>
        <div><div className="text-slate-500">5xx</div>{pct(m.error_rate, 1)}</div>
      </div>
      <div className="mt-1 flex items-center justify-between mono text-[10px]">
        <span className={r.ready < r.desired || r.desired < r.baseline_min ? 'text-red-400' : 'text-slate-400'}>
          pods {r.ready ?? '—'}/{r.desired ?? '—'}
        </span>
        <span className="text-slate-500">score {svc?.score != null ? svc.score.toFixed(3) : '—'}</span>
      </div>
      {svc?.anomaly_type && (
        <div className="mt-1 text-[10px] text-red-300 truncate" title={(svc.flags || []).join(', ')}>
          {svc.anomaly_type.replace('_', ' ')}{top ? ` · ${top[0]} z=${top[1] > 0 ? '+' : ''}${top[1]}` : ''}
        </div>
      )}
    </div>
  )
}

export default function HealthGrid({ frame }) {
  return (
    <div className="h-full grid grid-cols-2 gap-2 content-start overflow-y-auto scroll-thin">
      {SERVICES.map((s, i) => (
        <div key={s} className={i === 4 ? 'col-span-2' : ''}>
          <Card name={s} svc={frame?.services?.[s]} />
        </div>
      ))}
    </div>
  )
}
