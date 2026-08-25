/** Library — unified resource library page (replaces ModuleStore). */
import { useState, useMemo, useCallback, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { listResources, getTypes, getTags, importResource, importCVE, createResource } from '../api/library'
import { Library, Grid3x3, List, Upload, Bug, Plus, X, Search } from 'lucide-react'
import FilterBar from '../components/library/FilterBar'
import ResourceCard from '../components/library/ResourceCard'
import ResourceList from '../components/library/ResourceList'
import ResourceDetail from '../components/library/ResourceDetail'
import type { Resource, LibraryFilters, ResourceType } from '../types/library'

export default function LibraryPage() {
  const qc = useQueryClient()
  const [filters, setFilters] = useState<LibraryFilters & { q?: string }>({ sort: 'updated_at' })
  const [view, setView] = useState<'grid' | 'list'>('grid')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showImport, setShowImport] = useState(false)
  const [showCVE, setShowCVE] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [page, setPage] = useState(0)
  const pageSize = 60

  // Debounce search query
  const [debouncedQ, setDebouncedQ] = useState(filters.q)
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(filters.q), 300)
    return () => clearTimeout(t)
  }, [filters.q])

  const { data: types = {} } = useQuery({ queryKey: ['library-types'], queryFn: getTypes })
  const { data: tags = [] } = useQuery({ queryKey: ['library-tags'], queryFn: getTags })

  const queryParams = useMemo(() => ({
    ...filters,
    q: debouncedQ,
    limit: pageSize,
    offset: page * pageSize,
  }), [filters, debouncedQ, page])

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['library', queryParams],
    queryFn: () => listResources(queryParams),
  })

  const resources = data?.results ?? []
  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / pageSize)

  const handleFilterChange = useCallback((newFilters: typeof filters) => {
    setFilters(newFilters)
    setPage(0)
  }, [])

  const handleSelect = (r: Resource) => {
    if (r.id) setSelectedId(r.id)
  }

  // Import dialog state
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importType, setImportType] = useState('')
  const [importName, setImportName] = useState('')
  const [importTags, setImportTags] = useState('')

  // CVE dialog state
  const [cveId, setCveId] = useState('')

  // Create dialog state
  const [createType, setCreateType] = useState<ResourceType>('note')
  const [createName, setCreateName] = useState('')
  const [createContent, setCreateContent] = useState('')

  const importMut = useMutationImport(qc, () => { setShowImport(false); setImportFile(null) })
  const cveMut = useMutationCVE(rqc(), () => { setShowCVE(false); setCveId('') })
  const createMut = useMutationCreate(qc, () => { setShowCreate(false); setCreateName(''); setCreateContent('') })

  return (
    <div className="page-container space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Library size={22} className="text-success" /> Resource Library
        </h1>
        <div className="flex gap-2">
          <button className="btn btn-sm btn-ghost gap-1" onClick={() => setShowCVE(true)}>
            <Bug size={14} /> Import CVE
          </button>
          <button className="btn btn-sm btn-ghost gap-1" onClick={() => setShowImport(true)}>
            <Upload size={14} /> Import
          </button>
          <button className="btn btn-sm btn-success gap-1" onClick={() => setShowCreate(true)}>
            <Plus size={14} /> New
          </button>
        </div>
      </div>

      {/* Filters */}
      <FilterBar filters={filters} onChange={handleFilterChange} types={types} tags={tags} />

      {/* View toggle + count */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-base-content/50">
          {total} resource{total !== 1 ? 's' : ''}
          {isFetching && <span className="loading loading-spinner loading-xs ml-2" />}
        </span>
        <div className="join">
          <button
            className={`btn btn-xs join-item ${view === 'grid' ? 'btn-active' : ''}`}
            onClick={() => setView('grid')}
          >
            <Grid3x3 size={12} />
          </button>
          <button
            className={`btn btn-xs join-item ${view === 'list' ? 'btn-active' : ''}`}
            onClick={() => setView('list')}
          >
            <List size={12} />
          </button>
        </div>
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <span className="loading loading-spinner loading-lg text-success" />
        </div>
      ) : resources.length === 0 ? (
        <div className="text-center py-16">
          <Search size={32} className="inline text-base-content/20 mb-2" />
          <p className="text-base-content/40">No resources found</p>
        </div>
      ) : view === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {resources.map(r => (
            <ResourceCard key={r.id ?? r.name} resource={r} onClick={() => handleSelect(r)} />
          ))}
        </div>
      ) : (
        <ResourceList resources={resources} onSelect={handleSelect} />
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center">
          <div className="join">
            <button
              className="btn btn-sm join-item"
              disabled={page === 0}
              onClick={() => setPage(p => p - 1)}
            >«</button>
            <button className="btn btn-sm join-item">
              {page + 1} / {totalPages}
            </button>
            <button
              className="btn btn-sm join-item"
              disabled={page >= totalPages - 1}
              onClick={() => setPage(p => p + 1)}
            >»</button>
          </div>
        </div>
      )}

      {/* Detail drawer/modal */}
      {selectedId && (
        <div className="fixed inset-0 z-50 flex items-stretch justify-end">
          <div className="absolute inset-0 bg-black/40" onClick={() => setSelectedId(null)} />
          <div className="relative bg-base-100 w-full max-w-3xl h-full overflow-y-auto shadow-2xl p-6">
            <button className="btn btn-sm btn-circle btn-ghost absolute top-4 right-4" onClick={() => setSelectedId(null)}>
              <X size={16} />
            </button>
            <ResourceDetail resourceId={selectedId} onClose={() => setSelectedId(null)} />
          </div>
        </div>
      )}

      {/* Import dialog */}
      {showImport && (
        <div className="modal modal-open">
          <div className="modal-box">
            <h3 className="font-bold text-lg mb-4">Import Resource</h3>
            <div className="space-y-3">
              <input
                type="file"
                className="file-input file-input-bordered w-full"
                onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
              />
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-base-content/50">Type (auto-detected if empty)</label>
                  <input
                    className="input input-sm input-bordered w-full"
                    placeholder="auto"
                    value={importType}
                    onChange={(e) => setImportType(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-xs text-base-content/50">Name (uses filename if empty)</label>
                  <input
                    className="input input-sm input-bordered w-full"
                    value={importName}
                    onChange={(e) => setImportName(e.target.value)}
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-base-content/50">Tags (comma-separated)</label>
                <input
                  className="input input-sm input-bordered w-full"
                  placeholder="tag1, tag2"
                  value={importTags}
                  onChange={(e) => setImportTags(e.target.value)}
                />
              </div>
            </div>
            <div className="modal-action">
              <button className="btn btn-ghost" onClick={() => setShowImport(false)}>Cancel</button>
              <button
                className="btn btn-success"
                disabled={!importFile || importMut.isPending}
                onClick={() => importMut.mutate({
                  file: importFile!,
                  resource_type: importType || undefined,
                  name: importName || undefined,
                  tags: importTags || undefined,
                })}
              >
                {importMut.isPending ? <span className="loading loading-spinner loading-xs" /> : 'Import'}
              </button>
            </div>
          </div>
          <div className="modal-backdrop" onClick={() => setShowImport(false)} />
        </div>
      )}

      {/* CVE import dialog */}
      {showCVE && (
        <div className="modal modal-open">
          <div className="modal-box">
            <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
              <Bug size={18} className="text-error" /> Import CVE from NVD
            </h3>
            <input
              className="input input-bordered w-full"
              placeholder="CVE-2024-12345"
              value={cveId}
              onChange={(e) => setCveId(e.target.value.toUpperCase())}
            />
            <p className="text-xs text-base-content/50 mt-2">
              Fetches CVE data from NVD and caches it as a library resource.
            </p>
            <div className="modal-action">
              <button className="btn btn-ghost" onClick={() => setShowCVE(false)}>Cancel</button>
              <button
                className="btn btn-success"
                disabled={!cveId || cveMut.isPending}
                onClick={() => cveMut.mutate(cveId)}
              >
                {cveMut.isPending ? <span className="loading loading-spinner loading-xs" /> : 'Import'}
              </button>
            </div>
          </div>
          <div className="modal-backdrop" onClick={() => setShowCVE(false)} />
        </div>
      )}

      {/* Create dialog */}
      {showCreate && (
        <div className="modal modal-open">
          <div className="modal-box max-w-2xl">
            <h3 className="font-bold text-lg mb-4">New Resource</h3>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-base-content/50">Type</label>
                  <select
                    className="select select-sm select-bordered w-full"
                    value={createType}
                    onChange={(e) => setCreateType(e.target.value as ResourceType)}
                  >
                    {['note', 'snippet', 'script', 'documentation', 'configuration', 'template', 'research', 'command', 'idea', 'todo', 'test', 'report'].map(t => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-base-content/50">Name</label>
                  <input
                    className="input input-sm input-bordered w-full"
                    value={createName}
                    onChange={(e) => setCreateName(e.target.value)}
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-base-content/50">Content</label>
                <textarea
                  className="textarea textarea-bordered w-full font-mono text-xs"
                  rows={12}
                  value={createContent}
                  onChange={(e) => setCreateContent(e.target.value)}
                />
              </div>
            </div>
            <div className="modal-action">
              <button className="btn btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
              <button
                className="btn btn-success"
                disabled={!createName || createMut.isPending}
                onClick={() => createMut.mutate({
                  resource_type: createType,
                  name: createName,
                  content: createContent,
                })}
              >
                {createMut.isPending ? <span className="loading loading-spinner loading-xs" /> : 'Create'}
              </button>
            </div>
          </div>
          <div className="modal-backdrop" onClick={() => setShowCreate(false)} />
        </div>
      )}
    </div>
  )
}

// --- Mutation hooks (inline to keep file self-contained) ---
import { useMutation } from '@tanstack/react-query'
import { useQueryClient as rqc } from '@tanstack/react-query'

function useMutationImport(qc: ReturnType<typeof useQueryClient>, onSuccess: () => void) {
  return useMutation({
    mutationFn: (opts: { file: File; resource_type?: string; name?: string; tags?: string }) =>
      importResource(opts.file, opts),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['library'] })
      qc.invalidateQueries({ queryKey: ['library-types'] })
      qc.invalidateQueries({ queryKey: ['library-tags'] })
      onSuccess()
    },
  })
}

function useMutationCVE(qc: ReturnType<typeof useQueryClient>, onSuccess: () => void) {
  return useMutation({
    mutationFn: (cveId: string) => importCVE(cveId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['library'] })
      onSuccess()
    },
  })
}

function useMutationCreate(qc: ReturnType<typeof useQueryClient>, onSuccess: () => void) {
  return useMutation({
    mutationFn: (data: { resource_type: ResourceType; name: string; content?: string }) =>
      createResource(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['library'] })
      qc.invalidateQueries({ queryKey: ['library-types'] })
      onSuccess()
    },
  })
}
