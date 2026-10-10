export const SERVICES = [
  'api-gateway',
  'product-service',
  'order-service',
  'payment-service',
  'notification-service',
]

export const SERVICE_COLORS = {
  'api-gateway': '#60a5fa',
  'product-service': '#a78bfa',
  'order-service': '#fbbf24',
  'payment-service': '#34d399',
  'notification-service': '#94a3b8',
}

export const STATUS_STYLE = {
  healthy: { pill: 'bg-emerald-600/90 text-white', ring: 'border-slate-700', dot: '#10b981', label: 'HEALTHY' },
  degraded: { pill: 'bg-amber-500 text-black', ring: 'border-amber-500/70', dot: '#f59e0b', label: 'DEGRADED' },
  anomaly: { pill: 'bg-red-600 text-white', ring: 'border-red-500', dot: '#ef4444', label: 'ANOMALY' },
  unknown: { pill: 'bg-slate-600 text-white', ring: 'border-slate-700', dot: '#64748b', label: 'NO DATA' },
}

export const PHASE_STYLE = {
  CAMPAIGN: 'bg-indigo-600 text-white',
  STRATEGY: 'bg-slate-600 text-white',
  PREFLIGHT: 'bg-sky-700 text-white',
  INJECT: 'bg-fuchsia-600 text-white',
  DETECT: 'bg-red-600 text-white',
  RCA: 'bg-orange-500 text-black',
  DECIDE: 'bg-blue-600 text-white',
  GUARDRAIL: 'bg-amber-500 text-black',
  REMEDIATE: 'bg-cyan-600 text-white',
  VERIFY: 'bg-teal-600 text-white',
  RECOVERED: 'bg-emerald-600 text-white',
  FAILED: 'bg-red-800 text-white',
  TEARDOWN: 'bg-slate-500 text-white',
  SUMMARY: 'bg-violet-600 text-white',
  AUTOPILOT: 'bg-pink-600 text-white',
}

export const shortName = (svc) =>
  (svc || '').replace('-service', '').replace('api-gateway', 'gateway')

export function clock(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('en-GB', { hour12: false })
}

export function num(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return Number(v).toFixed(digits)
}

export function pct(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(digits)}%`
}

export function ms(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return v >= 1000 ? `${(v / 1000).toFixed(2)}s` : `${Math.round(v)}ms`
}
