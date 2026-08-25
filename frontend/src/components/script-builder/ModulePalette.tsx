import { useState } from 'react'
import { Search, Puzzle } from 'lucide-react'
import type { Module } from '../../types/module'

const CAT_ORDER = ['recon', 'credentials', 'persistence', 'lateral', 'exfil', 'surveillance', 'simulation', 'full', 'other']

function getCategory(mod: Module): string {
  return mod.category || 'other'
}

export default function ModulePalette({ modules }: { modules: Module[] }) {
  const [search, setSearch] = useState('')

  const filtered = modules.filter((m) =>
    m.name.toLowerCase().includes(search.toLowerCase()) ||
    (m.description || '').toLowerCase().includes(search.toLowerCase()) ||
    (m.category || '').toLowerCase().includes(search.toLowerCase())
  )

  const grouped = filtered.reduce<Record<string, Module[]>>((acc, m) => {
    const cat = getCategory(m)
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(m)
    return acc
  }, {})

  const onDragStart = (e: React.DragEvent, mod: Module) => {
    e.dataTransfer.setData('application/reactflow', JSON.stringify(mod))
    e.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div className="flex flex-col h-full w-64 bg-base-200 border-r border-base-300">
      <div className="p-3 border-b border-base-300">
        <h2 className="text-sm font-bold flex items-center gap-2 mb-2"><Puzzle size={14} /> Modules</h2>
        <div className="relative">
          <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-base-content/40" />
          <input
            className="input input-xs input-bordered w-full pl-7"
            placeholder="Search modules…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-3">
        {CAT_ORDER.map((cat) => {
          const items = grouped[cat]
          if (!items || items.length === 0) return null
          return (
            <div key={cat}>
              <div className="text-[10px] font-bold uppercase tracking-wider text-base-content/40 mb-1 px-1">{cat}</div>
              <div className="space-y-1">
                {items.map((mod) => (
                  <div
                    key={mod.id}
                    draggable
                    onDragStart={(e) => onDragStart(e, mod)}
                    className="bg-base-100 border border-base-300 rounded-lg p-2 cursor-grab hover:border-success/50 hover:shadow-sm transition-all"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-medium">{mod.name}</span>
                      <span className="text-[9px] text-base-content/40">{mod.os_compat?.join(', ')}</span>
                    </div>
                    <p className="text-[10px] text-base-content/50 line-clamp-2 mt-0.5">{mod.description || 'No description'}</p>
                    {mod.actions && mod.actions.length > 0 && (
                      <div className="flex flex-wrap gap-0.5 mt-1">
                        {mod.actions.slice(0, 3).map((a) => (
                          <span key={a} className="badge badge-xs badge-ghost">{a}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
        {filtered.length === 0 && <p className="text-xs text-base-content/40 text-center py-4">No modules found</p>}
      </div>
    </div>
  )
}
