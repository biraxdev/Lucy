import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getModules, uploadModule, deleteModule } from '../api/modules'
import { Puzzle, Upload, Trash2, Download, Search } from 'lucide-react'
import api from '../api/client'

export default function ModuleStore() {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [search, setSearch] = useState('')

  const { data: modules = [], isLoading } = useQuery({ queryKey: ['modules'], queryFn: getModules })

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadModule(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['modules'] }),
  })

  const deleteMut = useMutation({
    mutationFn: deleteModule,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['modules'] }),
  })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) uploadMut.mutate(file)
  }

  const handleDownload = async (id: string, name: string) => {
    const res = await api.get(`/modules/${name}/download`)
    const code = res.data?.code ?? JSON.stringify(res.data, null, 2)
    const blob = new Blob([code], { type: 'text/x-python' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `${name}.py`; a.click()
    URL.revokeObjectURL(url)
  }

  const filtered = modules.filter((m: any) =>
    m.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="page-container space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Puzzle size={22} /> Module Store</h1>
        <button className="btn btn-sm btn-success gap-1" onClick={() => fileRef.current?.click()}>
          {uploadMut.isPending ? <span className="loading loading-spinner loading-xs" /> : <Upload size={14} />} Upload
        </button>
        <input ref={fileRef} type="file" accept=".py,.zip" className="hidden" onChange={handleFileChange} />
      </div>

      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-base-content/40" />
        <input className="input input-bordered w-full pl-8 input-sm" placeholder="Search modules…"
          value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12"><span className="loading loading-spinner loading-lg text-success" /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((m: any) => (
            <div key={m.id} className="card bg-base-200 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <p className="font-semibold">{m.name}</p>
                <span className="badge badge-sm badge-ghost">{m.version}</span>
              </div>
              <p className="text-xs text-base-content/50 line-clamp-2">{m.description || 'No description'}</p>
              <div className="flex gap-1 mt-2">
                <span className={`badge badge-xs ${m.type === 'builtin' ? 'badge-info' : 'badge-success'}`}>{m.type}</span>
                <span className="badge badge-xs badge-ghost">{m.os || 'any'}</span>
              </div>
              <div className="flex gap-1 justify-end">
                <button className="btn btn-xs btn-ghost gap-1" onClick={() => handleDownload(m.id, m.name)}>
                  <Download size={12} />
                </button>
                {m.type !== 'builtin' && (
                  <button className="btn btn-xs btn-ghost text-error" onClick={() => deleteMut.mutate(m.id)}>
                    <Trash2 size={12} />
                  </button>
                )}
              </div>
            </div>
          ))}
          {filtered.length === 0 && <p className="text-base-content/40 col-span-3 text-center py-8">No modules found</p>}
        </div>
      )}
    </div>
  )
}
