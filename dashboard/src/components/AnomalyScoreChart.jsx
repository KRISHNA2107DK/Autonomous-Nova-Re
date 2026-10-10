import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { SERVICES, SERVICE_COLORS, clock, shortName } from '../lib/format'

/** Isolation Forest decision score per service; below the line = anomalous. */
export default function AnomalyScoreChart({ buffer, threshold }) {
  const data = buffer.map((f) => {
    const row = { t: clock(f.timestamp) }
    for (const s of SERVICES) row[s] = f.services?.[s]?.score ?? null
    return row
  })
  const last = buffer[buffer.length - 1]
  const alerted = new Set(SERVICES.filter((s) => last?.services?.[s]?.status === 'anomaly'))

  if (!data.length) {
    return <div className="h-full flex items-center justify-center text-slate-500 text-xs">Waiting for telemetry…</div>
  }
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid stroke="#1e293b" vertical={false} />
        <XAxis dataKey="t" tick={{ fontSize: 9, fill: '#64748b' }} interval="preserveStartEnd" minTickGap={40} />
        <YAxis domain={[-0.3, 0.3]} allowDataOverflow tick={{ fontSize: 9, fill: '#64748b' }} />
        <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 11 }}
          formatter={(v, name) => [v?.toFixed(3), shortName(name)]} />
        <Legend wrapperStyle={{ fontSize: 10 }} formatter={(v) => (
          <span style={{ color: alerted.has(v) ? '#f87171' : '#94a3b8', fontWeight: alerted.has(v) ? 700 : 400 }}>
            {shortName(v)}
          </span>
        )} />
        {threshold != null && (
          <ReferenceLine y={threshold} stroke="#ef4444" strokeDasharray="4 3"
            label={{ value: `threshold ${threshold.toFixed(3)}`, position: 'insideBottomRight', fill: '#f87171', fontSize: 9 }} />
        )}
        {SERVICES.map((s) => (
          <Line key={s} type="monotone" dataKey={s} stroke={SERVICE_COLORS[s]} dot={false}
            strokeWidth={alerted.has(s) ? 2.6 : 1.4} isAnimationActive={false} connectNulls />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
