import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAgents } from '../hooks/useAgents'
import { killAgent } from '../api/agents'
import { useUIStore } from '../stores/uiStore'
import {
  Server, RefreshCw, Search, Zap, Users, Filter, CheckSquare,
  Square, X, Plus, Rocket,
} from 'lucide-react'
import {
  listGroups, addMembersBulk, removeMembersBulk, getAllGroupSummaries,
} from '../api/groups'

export default function Agents() {
  const { agents, isLoading, refetch } = useAgents()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [groupFilter, setGroupFilter] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [showBulkMenu, setShowBulkMenu] = useState(false)
  const openAgent = useUIStore((s) => s.openAgent)
  const navigate = useNavigate()
  const qc = useQueryClient()

  const killMut = useMutation({
    mutationFn: killAgent,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agents'] }),
  })

  const { data: groups = [] } = useQuery({
    queryKey: ['groups'],
    queryFn: listGroups,
  })

  const { data: groupSummaries = [] } = useQuery({
    queryKey: ['group-summaries'],
    queryFn: getAllGroupSummaries,
    refetchInterval: 30_000,
  })

  // Build a map: agent_id -> group_ids for filtering
  const agentGroupMap = useMemo(() => {
    const m: Record<string, string[]> = {}
    for (const g of groups) {
      for (const aid of g.members || []) {
        if (!m[aid]) m[aid] = []
        m[aid].push(g.id)
      }
    }
    return m
  }, [groups])

  const filtered = agents.filter((a) => {
    const matchesSearch = [a.hostname, a.ip_public, a.ip_private, a.os, a.username].some((v) =>
      v?.toLowerCase().includes(search.toLowerCase())
    )
    const matchesStatus = !statusFilter || a.status === statusFilter
    const matchesGroup = !groupFilter || (agentGroupMap[a.id] || []).includes(groupFilter)
    return matchesSearch && matchesStatus && matchesGroup
  })

  const allSelected = filtered.length > 0 && filtered.every((a) => selected.has(a.id))
  const someSelected = filtered.some((a) => selected.has(a.id))

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelected((prev) => {
        const next = new Set(prev)
        for (const a of filtered) next.delete(a.id)
        return next
      })
    } else {
      setSelected((prev) => {
        const next = new Set(prev)
        for (const a of filtered) next.add(a.id)
        return next
      })
    }
  }

  const clearSelection = () => {
    setSelected(new Set())
    setShowBulkMenu(false)
  }

  const assignToGroup = async (groupId: string) => {
    try {
      await addMembersBulk(groupId, Array.from(selected))
      qc.invalidateQueries({ queryKey: ['groups'] })
      qc.invalidateQueries({ queryKey: ['group-summaries'] })
      clearSelection()
    } catch (e) {
      console.error('Bulk assign failed', e)
    }
  }

  const removeFromGroup = async (groupId: string) => {
    try {
      await removeMembersBulk(groupId, Array.from(selected))
      qc.invalidateQueries({ queryKey: ['groups'] })
      qc.invalidateQueries({ queryKey: ['group-summaries'] })
      clearSelection()
    } catch (e) {
      console.error('Bulk remove failed', e)
    }
  }

  return (
    <div className="page-container space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Server size={22} /> Agents</h1>
        <div className="flex items-center gap-2">
          <span className="text-xs text-base-content/50">{agents.length} total</span>
          <button className="btn btn-sm btn-outline gap-1" onClick={() => refetch()}>
            <RefreshCw size={14} /> Refresh
          </button>
          <button className="btn btn-sm btn-success gap-1" onClick={() => navigate('/builder')}>
            <Rocket size={14} /> Build Agent
          </button>
        </div>
      </div>

      {/* Group summary cards (for 50+ agent fleets) */}
      {groupSummaries.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin">
          <button
            onClick={() => setGroupFilter('')}
            className={`card shrink-0 w-40 p-3 text-left transition-all ${
              groupFilter === '' ? 'border-2 border-primary bg-primary/5' : 'border border-base-300 hover:border-base-content/20'
            }`}
          >
            <p className="text-xs font-bold text-base-content/60 uppercase">All Agents</p>
            <p className="text-2xl font-bold mt-1">{agents.length}</p>
            <div className="flex gap-2 mt-1 text-[10px]">
              <span className="text-success">{agents.filter(a => a.status === 'online').length} on</span>
              <span className="text-warning">{agents.filter(a => a.status === 'idle').length} idle</span>
              <span className="text-error">{agents.filter(a => a.status === 'offline').length} off</span>
            </div>
          </button>
          {groupSummaries.map((gs) => (
            <button
              key={gs.group_id}
              onClick={() => setGroupFilter(groupFilter === gs.group_id ? '' : gs.group_id)}
              className={`card shrink-0 w-40 p-3 text-left transition-all ${
                groupFilter === gs.group_id ? 'border-2 bg-base-200' : 'border border-base-300 hover:border-base-content/20'
              }`}
              style={groupFilter === gs.group_id ? { borderColor: gs.color } : {}}
            >
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: gs.color }} />
                <p className="text-xs font-bold truncate" style={{ color: gs.color }}>{gs.name}</p>
                {gs.is_dynamic && <span className="badge badge-xs badge-info">dyn</span>}
              </div>
              <p className="text-2xl font-bold mt-1">{gs.total}</p>
              <div className="flex gap-2 mt-1 text-[10px]">
                <span className="text-success">{gs.online} on</span>
                <span className="text-warning">{gs.idle} idle</span>
                <span className="text-error">{gs.offline} off</span>
              </div>
              {gs.last_active && (
                <p className="text-[9px] text-base-content/40 mt-1">
                  active {new Date(gs.last_active).toLocaleTimeString()}
                </p>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-base-content/40" />
          <input
            className="input input-bordered w-full pl-8 input-sm"
            placeholder="Search agents…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-1">
          {['', 'online', 'idle', 'offline'].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`btn btn-xs ${
                statusFilter === s
                  ? s === 'online' ? 'btn-success' : s === 'idle' ? 'btn-warning' : s === 'offline' ? 'btn-error' : 'btn-primary'
                  : 'btn-ghost'
              }`}
            >
              {s || 'All'}
            </button>
          ))}
        </div>
        {groups.length > 0 && (
          <div className="relative">
            <Filter size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-base-content/40 pointer-events-none" />
            <select
              className="select select-bordered select-sm pl-7"
              value={groupFilter}
              onChange={(e) => setGroupFilter(e.target.value)}
            >
              <option value="">All groups</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 px-4 py-2 bg-info/10 border border-info/30 rounded-lg">
          <span className="text-sm font-semibold text-info flex items-center gap-1">
            <Users size={14} /> {selected.size} selected
          </span>
          <div className="flex-1" />
          <div className="relative">
            <button
              onClick={() => setShowBulkMenu((v) => !v)}
              className="btn btn-xs btn-info gap-1"
            >
              <Plus size={12} /> Assign to group
            </button>
            {showBulkMenu && (
              <div className="absolute right-0 top-full mt-1 z-50 bg-base-200 border border-base-300 rounded-lg shadow-xl min-w-[200px] py-1">
                {groups.map((g) => (
                  <div key={g.id} className="px-2">
                    <button
                      onClick={() => assignToGroup(g.id)}
                      className="w-full text-left px-2 py-1.5 text-xs hover:bg-base-300 rounded flex items-center gap-2"
                    >
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: g.color }} />
                      <span className="flex-1 truncate">{g.name}</span>
                      <Plus size={10} />
                    </button>
                  </div>
                ))}
                <div className="border-t border-base-300 my-1" />
                <p className="px-3 py-1 text-[10px] text-base-content/40 uppercase font-bold">Remove from</p>
                {groups.map((g) => (
                  <div key={g.id} className="px-2">
                    <button
                      onClick={() => removeFromGroup(g.id)}
                      className="w-full text-left px-2 py-1.5 text-xs hover:bg-base-300 rounded flex items-center gap-2"
                    >
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: g.color }} />
                      <span className="flex-1 truncate">{g.name}</span>
                      <X size={10} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button onClick={clearSelection} className="btn btn-xs btn-ghost gap-1">
            <X size={12} /> Clear
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center py-12"><span className="loading loading-spinner loading-lg text-success" /></div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-base-300">
          <table className="table table-sm w-full">
            <thead className="bg-base-300">
              <tr>
                <th className="w-8">
                  <button onClick={toggleSelectAll} className="btn btn-ghost btn-xs p-0">
                    {allSelected ? <CheckSquare size={14} className="text-success" /> : someSelected ? <CheckSquare size={14} className="text-warning" /> : <Square size={14} />}
                  </button>
                </th>
                <th>Hostname</th><th>OS</th><th>Username</th><th>IP</th>
                <th>Status</th><th>Groups</th><th>Last Seen</th><th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => {
                const aGroups = (agentGroupMap[a.id] || []).map((gid) => groups.find((g) => g.id === gid)).filter(Boolean)
                const isSel = selected.has(a.id)
                return (
                  <tr key={a.id} className={`hover cursor-pointer ${isSel ? 'bg-info/5' : ''}`} onClick={() => openAgent(a.id)}>
                    <td onClick={(e) => e.stopPropagation()}>
                      <button onClick={() => toggleSelect(a.id)} className="btn btn-ghost btn-xs p-0">
                        {isSel ? <CheckSquare size={14} className="text-info" /> : <Square size={14} className="text-base-content/30" />}
                      </button>
                    </td>
                    <td className="font-mono font-medium">{a.hostname}</td>
                    <td>{a.os}</td>
                    <td>{a.username}</td>
                    <td className="font-mono text-xs">{a.ip_public || a.ip_private}</td>
                    <td>
                      <span className={`badge badge-sm badge-${a.status === 'online' ? 'success' : a.status === 'idle' ? 'warning' : 'error'}`}>
                        {a.status}
                      </span>
                    </td>
                    <td>
                      <div className="flex gap-0.5 flex-wrap max-w-[120px]">
                        {aGroups.slice(0, 3).map((g: any) => (
                          <span
                            key={g.id}
                            className="badge badge-xs badge-ghost"
                            style={{ backgroundColor: `${g.color}20`, color: g.color }}
                            title={g.name}
                          >
                            {g.name.slice(0, 6)}
                          </span>
                        ))}
                        {aGroups.length > 3 && (
                          <span className="badge badge-xs badge-ghost" title={`${aGroups.length - 3} more`}>
                            +{aGroups.length - 3}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="text-xs text-base-content/50">
                      {a.last_seen ? new Date(a.last_seen).toLocaleString() : '—'}
                    </td>
                    <td className="text-right">
                      <div className="flex gap-1 justify-end">
                        <button
                          className="btn btn-xs btn-success gap-1"
                          onClick={() => openAgent(a.id)}
                        >
                          <Server size={10} /> Control
                        </button>
                        {a.status !== 'offline' && (
                          <button
                            className="btn btn-xs btn-error btn-outline gap-1"
                            onClick={(e) => { e.stopPropagation(); killMut.mutate(a.id) }}
                            disabled={killMut.isPending}
                          >
                            <Zap size={10} /> Kill
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
              {filtered.length === 0 && (
                <tr><td colSpan={9} className="text-center text-base-content/40 py-8">No agents found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
