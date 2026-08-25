import { useEffect, useState } from 'react'
import { Target, BookOpen, Flag, StickyNote } from 'lucide-react'
import { getCampaigns, getPlaybooks, getTechniques, getAgentNotes } from '../api/strategy'
import type { Campaign, Playbook, Technique, AgentNote } from '../types/strategy'

export default function Strategy() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [techniques, setTechniques] = useState<Technique[]>([])
  const [notes, setNotes] = useState<AgentNote[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      getCampaigns(),
      getPlaybooks(),
      getTechniques(),
      getAgentNotes(),
    ])
      .then(([c, p, t, n]) => {
        setCampaigns(c)
        setPlaybooks(p)
        setTechniques(t)
        setNotes(n)
      })
      .finally(() => setLoading(false))
  }, [])

  const StatCard = ({ icon: Icon, label, value, color }: { icon: any; label: string; value: number; color: string }) => (
    <div className="stat bg-base-200 rounded-xl">
      <div className={`stat-figure text-${color}`}>
        <Icon size={24} />
      </div>
      <div className="stat-title">{label}</div>
      <div className="stat-value text-2xl">{value}</div>
    </div>
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="loading loading-spinner loading-lg" />
      </div>
    )
  }

  return (
    <div className="p-4 space-y-6">
      <h1 className="text-2xl font-bold">Strategy & Operations</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Flag} label="Campaigns" value={campaigns.length} color="primary" />
        <StatCard icon={BookOpen} label="Playbooks" value={playbooks.length} color="secondary" />
        <StatCard icon={Target} label="Techniques" value={techniques.length} color="accent" />
        <StatCard icon={StickyNote} label="Agent Notes" value={notes.length} color="success" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="card bg-base-100 shadow-sm">
          <div className="card-body">
            <h2 className="card-title">Campaigns</h2>
            {campaigns.length === 0 ? (
              <p className="text-base-content/60">No campaigns yet. Create one from the Chat.</p>
            ) : (
              <ul className="divide-y divide-base-300">
                {campaigns.map((c) => (
                  <li key={c.id} className="py-2">
                    <div className="font-medium">{c.name}</div>
                    <div className="text-sm text-base-content/70">{c.objective || c.description || 'No objective'}</div>
                    <div className="badge badge-sm mt-1">{c.status}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="card bg-base-100 shadow-sm">
          <div className="card-body">
            <h2 className="card-title">Playbooks</h2>
            {playbooks.length === 0 ? (
              <p className="text-base-content/60">No playbooks yet.</p>
            ) : (
              <ul className="divide-y divide-base-300">
                {playbooks.map((p) => (
                  <li key={p.id} className="py-2">
                    <div className="font-medium">{p.name}</div>
                    <div className="text-sm text-base-content/70">
                      {p.steps?.length || 0} step(s)
                      {p.tags?.length ? ` · ${p.tags.join(', ')}` : ''}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>

      <section className="card bg-base-100 shadow-sm">
        <div className="card-body">
          <h2 className="card-title">Recent Agent Notes</h2>
          {notes.length === 0 ? (
            <p className="text-base-content/60">No notes yet. Tell Lucy "note that Agent 01 is ..."</p>
          ) : (
            <ul className="divide-y divide-base-300">
              {notes.slice(0, 10).map((n) => (
                <li key={n.id} className="py-2">
                  <div className="text-sm">{n.content}</div>
                  <div className="text-xs text-base-content/60 mt-1">
                    {n.category} · {new Date(n.created_at).toLocaleString()}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}
