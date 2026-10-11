import { PHASE_STYLE, clock, shortName } from '../lib/format'

/** The narrated decision log — every line is generated from live data. */
export default function ReasoningFeed({ events }) {
  const items = [...events].reverse().slice(0, 60)
  if (!items.length) {
    return (
      <div className="h-full flex items-center justify-center text-slate-500 text-xs text-center px-6">
        No reasoning events yet. Start a campaign — or inject a fault with autopilot on — and AutoHeal will narrate
        every detection, diagnosis and decision here.
      </div>
    )
  }
  return (
    <ol className="h-full overflow-y-auto scroll-thin space-y-1.5 pr-1">
      {items.map((e) => (
        <li key={e.id} className="rounded-lg bg-slate-900/80 border border-slate-800 px-2.5 py-1.5">
          <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
            <span className="mono text-[10px] text-slate-500">{clock(e.at)}</span>
            {e.round && <span className="mono text-[10px] text-slate-400">R{e.round}</span>}
            <span className={`px-1.5 py-px rounded text-[9px] font-bold ${PHASE_STYLE[e.phase] || 'bg-slate-600'}`}>
              {e.phase}
            </span>
            {e.service && (
              <span className="px-1.5 py-px rounded text-[9px] font-semibold bg-blue-900 text-blue-200">
                {shortName(e.service)}
              </span>
            )}
          </div>
          <p className="text-[12px] leading-snug text-slate-200">{e.message}</p>
        </li>
      ))}
    </ol>
  )
}
