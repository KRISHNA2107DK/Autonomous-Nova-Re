import { Area, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { shortName } from '../lib/format'

const HISTORY = 24
const STEP_S = 5

/**
 * LSTM forecast: the last 2 minutes of the Isolation Forest score for one
 * service, followed by the score of the LSTM's 60-second forecast trajectory.
 */
export default function ForecastChart({ buffer, frame, threshold }) {
  const service = frame?.anomaly?.affected_service
    || Object.entries(frame?.services || {}).sort((a, b) => (a[1].score ?? 1) - (b[1].score ?? 1))[0]?.[0]
    || 'payment-service'
  const lstm = frame?.services?.[service]?.lstm
  const past = buffer.slice(-HISTORY).map((f, i, arr) => ({
    t: -(arr.length - 1 - i) * STEP_S,
    actual: f.services?.[service]?.score ?? null,
  }))
  const future = (lstm?.forecast_scores || []).map((v, i) => ({ t: (i + 1) * STEP_S, forecast: v }))
  if (past.length && future.length) future.unshift({ t: 0, forecast: past[past.length - 1].actual })
  const data = [...past, ...future]
  const warn = lstm?.predicted_anomaly

  return (
    <div className="h-full flex flex-col">
      <div className="text-[11px] text-slate-400 mb-1 shrink-0">
        <span className="text-blue-300 font-semibold">{shortName(service)}</span>
        {lstm?.ready ? (
          <span className="ml-1">· +60s: <span className="mono">{lstm.predicted_score_60s?.toFixed(3)}</span></span>
        ) : (
          <span className="ml-1 text-slate-500">· warming up (needs 60s of history)</span>
        )}
        {lstm?.residual_z != null && <span className="ml-1 text-slate-500">· surprise z {lstm.residual_z.toFixed(1)}</span>}
      </div>
      {warn && <div className="text-[11px] font-bold text-red-400 animate-pulse shrink-0">⚠ still anomalous in 60s</div>}
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
            <XAxis dataKey="t" type="number" domain={[-HISTORY * STEP_S, 60]} tick={{ fontSize: 8, fill: '#64748b' }}
              tickFormatter={(v) => (v === 0 ? 'now' : `${v}s`)} />
            <YAxis domain={[-0.3, 0.3]} allowDataOverflow tick={{ fontSize: 8, fill: '#64748b' }} />
            <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 10 }}
              formatter={(v) => v?.toFixed(3)} labelFormatter={(v) => `${v}s`} />
            {threshold != null && <ReferenceLine y={threshold} stroke="#ef4444" strokeDasharray="4 3" />}
            <ReferenceLine x={0} stroke="#475569" />
            <Area type="monotone" dataKey="actual" stroke="#60a5fa" fill="#60a5fa" fillOpacity={0.15}
              isAnimationActive={false} connectNulls />
            <Line type="monotone" dataKey="forecast" stroke={warn ? '#f87171' : '#a78bfa'} strokeDasharray="5 3"
              dot={false} isAnimationActive={false} connectNulls />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
