/** Library resource types — unified knowledge & asset library. */

export type ResourceType =
  | 'module' | 'poc' | 'cve' | 'finding' | 'evidence' | 'playbook'
  | 'detection_rule' | 'c2_profile' | 'build_pack' | 'campaign'
  | 'note' | 'tactic' | 'technique'
  | 'agent' | 'task' | 'credential_reference' | 'log' | 'timeline'
  | 'group' | 'redirector'
  | 'snippet' | 'script' | 'template' | 'configuration' | 'documentation'
  | 'research' | 'command' | 'workflow' | 'test' | 'dataset' | 'asset'
  | 'api_reference' | 'integration' | 'architecture_doc' | 'decision'
  | 'idea' | 'todo' | 'experiment' | 'report' | 'tool' | 'payload'
  | 'exploit_research' | 'proof'

export type ResourceStatus =
  | 'draft' | 'experimental' | 'active' | 'stable'
  | 'verified' | 'deprecated' | 'archived' | 'live'

export type ResourceVisibility = 'public' | 'internal' | 'restricted' | 'private'

export type RelationType =
  | 'references' | 'depends_on' | 'related_to' | 'implements'
  | 'tests' | 'describes' | 'affects' | 'derived_from'
  | 'part_of' | 'replaces'

export interface Resource {
  id: string
  tenant_id: string | null
  resource_type: ResourceType
  name: string
  description: string | null
  status: ResourceStatus
  version: string
  tags: string[]
  project: string | null
  owner: string | null
  source: string | null
  license: string | null
  references: string[]
  dependencies: string[]
  metadata: Record<string, unknown>
  content: string | null
  language: string | null
  visibility: ResourceVisibility
  storage_path: string | null
  content_hash: string | null
  favorite: boolean
  pinned: boolean
  use_count: number
  source_type: string | null
  source_id: string | null
  created_by: string | null
  created_at: string
  updated_at: string
  _live?: boolean
}

export interface ResourcePreview {
  id: string
  resource_type: ResourceType
  name: string
  description: string | null
  preview_type: string
  preview: Record<string, unknown>
  preview_fields: string[]
}

export interface ResourceRelation {
  relation_id: string
  relation_type: RelationType
  direction: 'outgoing' | 'incoming'
  target?: Resource
  source?: Resource
  created_by: string | null
  created_at: string
}

export interface AutoRelationSuggestion {
  field: string
  value: string
  target_resource_id: string
  target_name: string
  target_type: ResourceType
  suggested_relation_type: RelationType
}

export interface RelationsResponse {
  outgoing: ResourceRelation[]
  incoming: ResourceRelation[]
  auto: AutoRelationSuggestion[]
}

export interface ResourceVersion {
  id: string
  resource_id: string
  version: string
  snapshot: Record<string, unknown>
  content: string | null
  change_note: string | null
  created_by: string | null
  created_at: string
}

export interface LibrarySearchResponse {
  results: Resource[]
  total: number
  limit: number
  offset: number
}

export interface TypeCounts {
  [key: string]: number
}

export interface DuplicateGroup {
  content_hash: string
  resources: Resource[]
}

export interface Suggestion {
  type: 'relation' | 'metadata' | 'duplicate'
  description: string
  relation_type?: RelationType
  target_id?: string
}

export interface LibraryFilters {
  type?: ResourceType[]
  tag?: string[]
  status?: ResourceStatus[]
  language?: string
  project?: string
  visibility?: ResourceVisibility
  favorite?: boolean
  pinned?: boolean
  sort?: 'updated_at' | 'name' | 'use_count' | 'created_at'
}

export interface ResourceCreate {
  resource_type: ResourceType
  name: string
  description?: string
  content?: string
  status?: ResourceStatus
  version?: string
  tags?: string[]
  project?: string
  owner?: string
  source?: string
  license?: string
  language?: string
  visibility?: ResourceVisibility
  references?: string[]
  dependencies?: string[]
  metadata?: Record<string, unknown>
}

export interface ResourceUpdate {
  name?: string
  description?: string
  content?: string
  status?: ResourceStatus
  version?: string
  tags?: string[]
  project?: string
  owner?: string
  source?: string
  license?: string
  language?: string
  visibility?: ResourceVisibility
  references?: string[]
  dependencies?: string[]
  metadata?: Record<string, unknown>
  favorite?: boolean
  pinned?: boolean
  change_note?: string
}

export interface RelationCreate {
  target_id: string
  relation_type: RelationType
  metadata?: Record<string, unknown>
}

export interface GraphData {
  nodes: Array<{ id: string; name: string; resource_type: ResourceType; status: string }>
  edges: Array<{ source: string; target: string; relation_type: RelationType }>
}
