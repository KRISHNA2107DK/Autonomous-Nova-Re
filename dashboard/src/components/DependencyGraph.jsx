import { useEffect, useMemo, useRef, useState } from 'react'
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, forceX } from 'd3'
import { STATUS_STYLE, shortName } from '../lib/format'

const RANK = { 'api-gateway': 0, 'order-service': 1, 'product-service': 2, 'payment-service': 2, 'notification-service': 2 }

/**
 * Live service dependency graph. Layout is computed once with d3-force
 * (ranked left-to-right by call depth); colours, edge widths (live call
 * rates) and the blast-radius highlight update every tick.
 */
export default function DependencyGraph({ meta, frame }) {
  const ref = useRef(null)
  const [size, setSize] = useState({ w: 360, h: 240 })

  useEffect(() => {
    if (!ref.current) return undefined
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      if (width > 50 && height > 50) setSize({ w: width, h: height })
    })
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])

  const services = meta?.services
  const edges = meta?.edges
  const layout = useMemo(() => {
    if (!services || !edges) return null
    const nodes = services.map((id) => ({ id }))
    const links = edges.map((e) => ({ ...e }))
    const pad = 46
    const sim = forceSimulation(nodes)
      .force('link', forceLink(links).id((d) => d.id).distance(Math.min(size.w, size.h) / 2.6).strength(0.4))
      .force('charge', forceManyBody().strength(-420))
      .force('x', forceX((d) => pad + (RANK[d.id] ?? 1) * ((size.w - 2 * pad) / 2)).strength(0.9))
      .force('center', forceCenter(size.w / 2, size.h / 2).strength(0.05))
      .force('collide', forceCollide(42))
      .stop()
    for (let i = 0; i < 300; i += 1) sim.tick()
    for (const n of nodes) {
      n.x = Math.max(pad, Math.min(size.w - pad, n.x))
      n.y = Math.max(pad - 14, Math.min(size.h - pad, n.y))
    }
    return { nodes, links }
  }, [services, edges, size])

  if (!layout) {
    return <div ref={ref} className="h-full flex items-center justify-center text-slate-500 text-xs">Waiting for topology…</div>
  }

  const rates = frame?.call_rates || {}
  const status = (id) => frame?.services?.[id]?.status || 'unknown'
  const anomalous = new Set(layout.nodes.filter((n) => status(n.id) === 'anomaly').map((n) => n.id))
  const width = (r) => (r ? Math.min(1 + Math.log2(1 + r) * 1.4, 8) : 1)

  return (
    <div ref={ref} className="h-full w-full relative">
      <svg width={size.w} height={size.h}>
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#475569" />
          </marker>
        </defs>
        {layout.links.map((l) => {
          const key = `${l.source.id}->${l.target.id}`
          const hot = anomalous.has(l.target.id)
          const dx = l.target.x - l.source.x
          const dy = l.target.y - l.source.y
          const d = Math.hypot(dx, dy) || 1
          const r = 24
          return (
            <g key={key}>
              <line x1={l.source.x + (dx / d) * r} y1={l.source.y + (dy / d) * r}
                x2={l.target.x - (dx / d) * (r + 4)} y2={l.target.y - (dy / d) * (r + 4)}
                stroke={hot ? '#f59e0b' : '#475569'} strokeWidth={width(rates[key])}
                strokeDasharray={l.kind === 'async' ? '5 4' : hot ? '7 3' : 'none'} strokeOpacity={0.85}
                markerEnd="url(#arrow)">
                {hot && <animate attributeName="stroke-dashoffset" from="20" to="0" dur="0.8s" repeatCount="indefinite" />}
              </line>
              {rates[key] > 0 && (
                <text x={(l.source.x + l.target.x) / 2} y={(l.source.y + l.target.y) / 2 - 4}
                  fontSize="9" fill="#64748b" textAnchor="middle" className="mono">{rates[key].toFixed(1)}/s</text>
              )}
            </g>
          )
        })}
        {layout.nodes.map((n) => {
          const st = STATUS_STYLE[status(n.id)] || STATUS_STYLE.unknown
          return (
            <g key={n.id} transform={`translate(${n.x},${n.y})`}>
              {anomalous.has(n.id) && <circle r="22" fill="none" stroke="#ef4444" strokeWidth="2" className="pulse-ring" />}
              <circle r="22" fill={st.dot} fillOpacity={0.9} stroke="#0b1220" strokeWidth="2" />
              <text y="4" textAnchor="middle" fontSize="9" fontWeight="700" fill="#0b1220">
                {(frame?.services?.[n.id]?.replicas?.ready ?? '·')}/{frame?.services?.[n.id]?.replicas?.desired ?? '·'}
              </text>
              <text y="36" textAnchor="middle" fontSize="10" fill="#cbd5e1">{shortName(n.id)}</text>
            </g>
          )
        })}
      </svg>
      <div className="absolute bottom-0 right-1 text-[9px] text-slate-500">edge width = live req/s · dashed = async events · node label = ready/desired pods</div>
    </div>
  )
}
