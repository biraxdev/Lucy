/** Library API client — unified resource library endpoints. */
import api from './client'
import type {
  Resource,
  ResourcePreview,
  LibrarySearchResponse,
  TypeCounts,
  ResourceVersion,
  RelationsResponse,
  DuplicateGroup,
  Suggestion,
  ResourceCreate,
  ResourceUpdate,
  RelationCreate,
  GraphData,
  LibraryFilters,
} from '../types/library'

// --- List + Search ---

export const listResources = (params?: LibraryFilters & { q?: string; limit?: number; offset?: number }) => {
  const query: Record<string, unknown> = {}
  if (params?.q) query.q = params.q
  if (params?.type?.length) query.type = params.type
  if (params?.tag?.length) query.tag = params.tag
  if (params?.status?.length) query.status = params.status
  if (params?.language) query.language = params.language
  if (params?.project) query.project = params.project
  if (params?.visibility) query.visibility = params.visibility
  if (params?.favorite) query.favorite = true
  if (params?.pinned) query.pinned = true
  if (params?.sort) query.sort = params.sort
  if (params?.limit) query.limit = params.limit
  if (params?.offset) query.offset = params.offset
  return api.get<LibrarySearchResponse>('/library', { params: query }).then(r => r.data)
}

export const searchResources = (q: string, params?: { type?: string[]; tag?: string[]; status?: string[]; limit?: number; offset?: number }) =>
  api.get<LibrarySearchResponse>('/library/search', { params: { q, ...params } }).then(r => r.data)

export const getTypes = () =>
  api.get<{ types: TypeCounts }>('/library/types').then(r => r.data.types)

export const getTags = () =>
  api.get<{ tags: string[] }>('/library/tags').then(r => r.data.tags)

// --- CRUD ---

export const createResource = (data: ResourceCreate) =>
  api.post<Resource>('/library', data).then(r => r.data)

export const getResource = (id: string) =>
  api.get<Resource>(`/library/${id}`).then(r => r.data)

export const updateResource = (id: string, data: ResourceUpdate) =>
  api.patch<Resource>(`/library/${id}`, data).then(r => r.data)

export const deleteResource = (id: string) =>
  api.delete(`/library/${id}`)

// --- Preview + Metadata ---

export const getPreview = (id: string) =>
  api.get<ResourcePreview>(`/library/${id}/preview`).then(r => r.data)

// --- Relations ---

export const getRelations = (id: string) =>
  api.get<RelationsResponse>(`/library/${id}/relations`).then(r => r.data)

export const createRelation = (id: string, data: RelationCreate) =>
  api.post(`/library/${id}/relations`, data).then(r => r.data)

export const deleteRelation = (id: string, relationId: string) =>
  api.delete(`/library/${id}/relations/${relationId}`)

export const getGraph = (id: string, depth?: number) =>
  api.get<GraphData>(`/library/${id}/graph`, { params: { depth: depth ?? 2 } }).then(r => r.data)

// --- Versions ---

export const getVersions = (id: string) =>
  api.get<{ versions: ResourceVersion[] }>(`/library/${id}/versions`).then(r => r.data.versions)

export const createVersion = (id: string, changeNote?: string) =>
  api.post<ResourceVersion>(`/library/${id}/versions`, { change_note: changeNote }).then(r => r.data)

export const restoreVersion = (id: string, versionId: string) =>
  api.post<Resource>(`/library/${id}/versions/${versionId}/restore`).then(r => r.data)

// --- Favorite + Pin ---

export const toggleFavorite = (id: string) =>
  api.post<{ id: string; favorite: boolean }>(`/library/${id}/favorite`).then(r => r.data)

export const togglePin = (id: string) =>
  api.post<{ id: string; pinned: boolean }>(`/library/${id}/pin`).then(r => r.data)

// --- Duplicate ---

export const duplicateResource = (id: string) =>
  api.post<Resource>(`/library/${id}/duplicate`).then(r => r.data)

export const getDuplicates = () =>
  api.get<{ duplicates: DuplicateGroup[]; count: number }>('/library/duplicates').then(r => r.data)

// --- Suggestions ---

export const getSuggestions = (id: string) =>
  api.get<{ suggestions: Suggestion[] }>(`/library/suggestions/${id}`).then(r => r.data.suggestions)

// --- Import / Export ---

export const importResource = (file: File, opts?: { resource_type?: string; name?: string; language?: string; tags?: string }) => {
  const formData = new FormData()
  formData.append('file', file)
  if (opts?.resource_type) formData.append('resource_type', opts.resource_type)
  if (opts?.name) formData.append('name', opts.name)
  if (opts?.language) formData.append('language', opts.language)
  if (opts?.tags) formData.append('tags', opts.tags)
  return api.post<Resource>('/library/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

export const exportResource = (id: string, format?: 'json' | 'yaml' | 'md' | 'raw') =>
  api.get<{ content: string; name: string; content_type: string }>(`/library/${id}/export`, {
    params: { format: format ?? 'json' },
  }).then(r => r.data)

// --- CVE ---

export const importCVE = (cveId: string) =>
  api.post<Resource>('/library/cve/import', { cve_id: cveId }).then(r => r.data)
