export default function Panel({ title, right, children, className = '', accent = false }) {
  return (
    <section
      className={`rounded-xl border ${accent ? 'border-blue-800/70 bg-[#0d1628]' : 'border-slate-800 bg-[#111a2e]'} p-3 flex flex-col min-h-0 overflow-hidden ${className}`}
    >
      <header className="flex items-center justify-between mb-2 shrink-0">
        <h2 className={`text-[11px] font-bold uppercase tracking-widest ${accent ? 'text-blue-300' : 'text-slate-400'}`}>
          {title}
        </h2>
        {right}
      </header>
      <div className="flex-1 min-h-0">{children}</div>
    </section>
  )
}
