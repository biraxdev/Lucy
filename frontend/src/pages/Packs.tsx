import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Package, Search, Plus, Copy, Trash2, Download, Upload, Hammer, Play, Eye, Edit, X, Check } from 'lucide-react'
import type { BuildPack } from '../types/build'
import {
  listPacks,
  getPack,
  createPack,
  updatePack,
  deletePack,
  duplicatePack,
  combinePack,
  applyPack,
  buildFromPack,
  exportPack,
  importPack,
} from '../api/packs'

const emptyPack: PackForm = {
  id: '',
  name: '',
  description: '',
  icon: '📦',
  tags: [],
  modules: [],
  build_options: {},
}

type PackForm = {
  id: string
  name: string
  description: string
  icon: string
  tags: string[]
  modules: string[]
  build_options: Record<string, any>
}

export default function PacksPage() {
  const navigate = useNavigate()
  const [packs, setPacks] = useState<BuildPack[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState<'none' | 'edit' | 'view' | 'combine' | 'import' | 'build'>('none')
  const [selected, setSelected] = useState<BuildPack | null>(null)
  const [form, setForm] = useState<PackForm>(emptyPack)
  const [formError, setFormError] = useState('')
  const [combineB, setCombineB] = useState('')
  const [combineName, setCombineName] = useState('')
  const [buildResult, setBuildResult] = useState('')
  const [importText, setImportText] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const data = await listPacks(search)
      setPacks(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const t = setTimeout(load, 200)
    return () => clearTimeout(t)
  }, [search])

  const filtered = useMemo(() => packs, [packs])

  const openCreate = () => {
    setForm(emptyPack)
    setFormError('')
    setModal('edit')
    setSelected(null)
  }

  const openEdit = (p: BuildPack) => {
    setSelected(p)
    setForm({
      id: p.bpid,
      name: p.name,
      description: p.description,
      icon: p.icon || '📦',
      tags: p.tags || [],
      modules: p.modules || [],
      build_options: p.build_options || {},
    })
    setFormError('')
    setModal('edit')
  }

  const openView = async (bpid: string) => {
    const p = await getPack(bpid)
    setSelected(p as any)
    setModal('view')
  }

  const handleSave = async () => {
    setFormError('')
    if (!form.id || !form.name) {
      setFormError('ID et nom sont requis')
      return
    }
    try {
      if (selected) {
        await updatePack(selected.bpid, { ...form, id: undefined } as any)
      } else {
        await createPack(form)
      }
      setModal('none')
      load()
    } catch (err: any) {
      setFormError(err.response?.data?.detail || err.message || 'Erreur')
    }
  }

  const handleDelete = async (bpid: string) => {
    if (!confirm('Supprimer ce pack ?')) return
    try {
      await deletePack(bpid)
      load()
    } catch {}
  }

  const handleDuplicate = async (bpid: string) => {
    try {
      await duplicatePack(bpid)
      load()
    } catch {}
  }

  const handleCombine = async (bpid: string) => {
    if (!combineB || !combineName) return
    try {
      await combinePack(bpid, { bpid_b: combineB, new_id: `${bpid}_${combineB}`, name: combineName })
      setModal('none')
      load()
    } catch {}
  }

  const handleApply = async (bpid: string) => {
    const p = await applyPack(bpid)
    navigate('/builder', { state: { pack: p } })
  }

  const handleBuild = async (bpid: string) => {
    try {
      const r = await buildFromPack(bpid)
      setBuildResult(`Build lancé : ${r.build_id}`)
      setModal('build')
    } catch {}
  }

  const handleExport = async (bpid: string) => {
    const data = await exportPack(bpid)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${bpid}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleImport = async () => {
    try {
      const data = JSON.parse(importText)
      await importPack(data)
      setModal('none')
      load()
    } catch {}
  }

  const updateFormField = (key: keyof PackForm, value: any) => {
    setForm((f) => ({ ...f, [key]: value }))
  }

  const updateTags = (text: string) => {
    updateFormField('tags', text.split(',').map((s) => s.trim()).filter(Boolean))
  }

  const updateModules = (text: string) => {
    updateFormField('modules', text.split('\n').map((s) => s.trim()).filter(Boolean))
  }

  const updateBuildOptions = (text: string) => {
    try {
      const parsed = JSON.parse(text || '{}')
      updateFormField('build_options', parsed)
      setFormError('')
    } catch {
      setFormError('JSON build_options invalide')
    }
  }

  return (
    <div className="page-container space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Package className="text-success" />
          Pack Manager
        </h1>
        <div className="flex gap-2">
          <button className="btn btn-sm btn-primary" onClick={openCreate}>
            <Plus size={16} /> Créer
          </button>
          <button className="btn btn-sm btn-ghost" onClick={() => setModal('import')}>
            <Upload size={16} /> Importer
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="join flex-1">
          <span className="join-item btn btn-sm btn-ghost no-animation"><Search size={16} /></span>
          <input
            className="join-item input input-sm input-bordered w-full max-w-md"
            placeholder="Rechercher un pack..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center p-10"><span className="loading loading-spinner text-success" /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((p) => (
            <div key={p.bpid} className="card bg-base-100 shadow-md border border-base-300">
              <div className="card-body p-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">{p.icon}</span>
                    <div>
                      <h2 className="card-title text-base">{p.name}</h2>
                      <p className="text-xs text-base-content/50">{p.bpid}</p>
                    </div>
                  </div>
                </div>
                <p className="text-sm text-base-content/70 line-clamp-2">{p.description}</p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {p.tags?.map((t) => <span key={t} className="badge badge-sm badge-ghost">{t}</span>)}
                </div>
                <div className="text-xs text-base-content/50 mt-1">
                  {p.modules?.length || 0} module(s)
                </div>
                <div className="card-actions justify-end flex-wrap mt-3">
                  <button className="btn btn-xs btn-ghost" onClick={() => openView(p.bpid)}><Eye size={14} /></button>
                  <button className="btn btn-xs btn-ghost" onClick={() => openEdit(p)}><Edit size={14} /></button>
                  <button className="btn btn-xs btn-ghost" onClick={() => handleDuplicate(p.bpid)}><Copy size={14} /></button>
                  <button className="btn btn-xs btn-ghost" onClick={() => { setSelected(p); setCombineB(''); setCombineName(''); setModal('combine') }}>Combiner</button>
                  <button className="btn btn-xs btn-ghost" onClick={() => handleApply(p.bpid)}><Play size={14} /></button>
                  <button className="btn btn-xs btn-accent" onClick={() => handleBuild(p.bpid)}><Hammer size={14} /> Build</button>
                  <button className="btn btn-xs btn-ghost" onClick={() => handleExport(p.bpid)}><Download size={14} /></button>
                  <button className="btn btn-xs btn-ghost text-error" onClick={() => handleDelete(p.bpid)}><Trash2 size={14} /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit/Create modal */}
      {modal === 'edit' && (
        <div className="modal modal-open">
          <div className="modal-box max-w-2xl">
            <h3 className="font-bold text-lg mb-2">{selected ? 'Éditer' : 'Créer'} un pack</h3>
            {formError && <div className="alert alert-error alert-sm py-1 mb-2">{formError}</div>}
            <div className="grid grid-cols-2 gap-2">
              <label className="form-control w-full">
                <span className="label-text">ID unique</span>
                <input className="input input-bordered input-sm" value={form.id} disabled={!!selected} onChange={(e) => updateFormField('id', e.target.value)} />
              </label>
              <label className="form-control w-full">
                <span className="label-text">Nom</span>
                <input className="input input-bordered input-sm" value={form.name} onChange={(e) => updateFormField('name', e.target.value)} />
              </label>
              <label className="form-control w-full col-span-2">
                <span className="label-text">Description</span>
                <input className="input input-bordered input-sm" value={form.description} onChange={(e) => updateFormField('description', e.target.value)} />
              </label>
              <label className="form-control w-full">
                <span className="label-text">Icône</span>
                <input className="input input-bordered input-sm" value={form.icon} onChange={(e) => updateFormField('icon', e.target.value)} />
              </label>
              <label className="form-control w-full">
                <span className="label-text">Tags (séparés par ,)</span>
                <input className="input input-bordered input-sm" value={form.tags.join(', ')} onChange={(e) => updateTags(e.target.value)} />
              </label>
              <label className="form-control w-full col-span-2">
                <span className="label-text">Modules (un par ligne)</span>
                <textarea className="textarea textarea-bordered text-sm" rows={4} value={form.modules.join('\n')} onChange={(e) => updateModules(e.target.value)} />
              </label>
              <label className="form-control w-full col-span-2">
                <span className="label-text">Build options (JSON)</span>
                <textarea className="textarea textarea-bordered text-sm" rows={4} value={JSON.stringify(form.build_options, null, 2)} onChange={(e) => updateBuildOptions(e.target.value)} />
              </label>
            </div>
            <div className="modal-action">
              <button className="btn" onClick={() => setModal('none')}>Annuler</button>
              <button className="btn btn-primary" onClick={handleSave}><Check size={16} /> Enregistrer</button>
            </div>
          </div>
        </div>
      )}

      {/* View modal */}
      {modal === 'view' && selected && (
        <div className="modal modal-open">
          <div className="modal-box max-w-2xl">
            <h3 className="font-bold text-lg flex items-center gap-2"><span className="text-2xl">{selected.icon}</span> {selected.name}</h3>
            <p className="text-sm text-base-content/70 mb-2">{selected.bpid}</p>
            <p className="mb-2">{selected.description}</p>
            <div className="flex flex-wrap gap-1 mb-2">
              {selected.tags?.map((t) => <span key={t} className="badge badge-ghost">{t}</span>)}
            </div>
            <h4 className="font-semibold mt-3">Modules ({selected.modules?.length || 0})</h4>
            <ul className="text-sm list-disc list-inside max-h-32 overflow-auto">
              {selected.modules?.map((m) => <li key={m}>{m}</li>)}
            </ul>
            <h4 className="font-semibold mt-3">Build options</h4>
            <pre className="bg-base-300 p-2 rounded text-xs overflow-auto max-h-40">{JSON.stringify(selected.build_options, null, 2)}</pre>
            <div className="modal-action">
              <button className="btn" onClick={() => setModal('none')}><X size={16} /> Fermer</button>
            </div>
          </div>
        </div>
      )}

      {/* Combine modal */}
      {modal === 'combine' && selected && (
        <div className="modal modal-open">
          <div className="modal-box">
            <h3 className="font-bold text-lg mb-2">Combiner <span className="text-success">{selected.name}</span></h3>
            <label className="form-control w-full">
              <span className="label-text">Pack B</span>
              <select className="select select-bordered select-sm" value={combineB} onChange={(e) => setCombineB(e.target.value)}>
                <option value="">Choisir un pack</option>
                {packs.filter((p) => p.bpid !== selected.bpid).map((p) => (
                  <option key={p.bpid} value={p.bpid}>{p.name}</option>
                ))}
              </select>
            </label>
            <label className="form-control w-full mt-2">
              <span className="label-text">Nom du nouveau pack</span>
              <input className="input input-bordered input-sm" value={combineName} onChange={(e) => setCombineName(e.target.value)} />
            </label>
            <div className="modal-action">
              <button className="btn" onClick={() => setModal('none')}>Annuler</button>
              <button className="btn btn-primary" onClick={() => handleCombine(selected.bpid)}>Combiner</button>
            </div>
          </div>
        </div>
      )}

      {/* Import modal */}
      {modal === 'import' && (
        <div className="modal modal-open">
          <div className="modal-box max-w-2xl">
            <h3 className="font-bold text-lg mb-2">Importer un pack (JSON)</h3>
            <textarea className="textarea textarea-bordered w-full h-64 text-sm" value={importText} onChange={(e) => setImportText(e.target.value)} />
            <div className="modal-action">
              <button className="btn" onClick={() => setModal('none')}>Annuler</button>
              <button className="btn btn-primary" onClick={handleImport}>Importer</button>
            </div>
          </div>
        </div>
      )}

      {/* Build result modal */}
      {modal === 'build' && (
        <div className="modal modal-open">
          <div className="modal-box">
            <h3 className="font-bold text-lg mb-2">Build lancé</h3>
            <p className="font-mono text-sm">{buildResult}</p>
            <p className="text-sm text-base-content/70 mt-2">Téléchargement disponible dans la section Builder.</p>
            <div className="modal-action">
              <button className="btn" onClick={() => setModal('none')}>OK</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
