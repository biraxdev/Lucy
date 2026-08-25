/** ResourcePreview — preview panel showing type-adapted preview. */
import { useQuery } from '@tanstack/react-query'
import { getPreview } from '../../api/library'
import { FileText, AlertCircle, Shield, Bug, BookOpen, Code } from 'lucide-react'
import type { Resource } from '../../types/library'

interface Props {
  resource: Resource
}

const PREVIEW_ICONS: Record<string, React.ElementType> = {
  cve: Bug,
  finding: AlertCircle,
  module: Code,
  poc: Bug,
  playbook: BookOpen,
  detection_rule: Shield,
  note: FileText,
}

export default function ResourcePreview({ resource }: Props) {
  const { data: preview, isLoading } = useQuery({
    queryKey: ['library-preview', resource.id],
    queryFn: () => getPreview(resource.id!),
    enabled: !!resource.id,
  })

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <span className="loading loading-spinner loading-sm text-success" />
      </div>
    )
  }

  if (!preview || !resource.id) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          {(() => {
            const Icon = PREVIEW_ICONS[resource.resource_type] ?? FileText
            return <Icon size={16} className="text-success" />
          })()}
          <h3 className="font-semibold text-sm">{resource.name}</h3>
        </div>
        {resource.description && <p className="text-sm text-base-content/70">{resource.description}</p>}
        {resource.tags?.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {resource.tags.map(t => <span key={t} className="badge badge-xs badge-ghost">{t}</span>)}
          </div>
        )}
      </div>
    )
  }

  const Icon = PREVIEW_ICONS[resource.resource_type] ?? FileText
  const fields = preview.preview_fields ?? []
  const data = preview.preview ?? {}

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Icon size={16} className="text-success" />
        <h3 className="font-semibold text-sm">{preview.name}</h3>
        <span className="badge badge-xs badge-ghost ml-auto">{preview.preview_type}</span>
      </div>

      {preview.description && (
        <p className="text-sm text-base-content/70">{preview.description}</p>
      )}

      <div className="space-y-2">
        {fields.map(field => {
          const value = data[field]
          if (value === null || value === undefined || value === '') return null
          return (
            <div key={field} className="flex flex-col gap-0.5">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-base-content/40">{field}</span>
              {Array.isArray(value) ? (
                <div className="flex flex-wrap gap-1">
                  {value.slice(0, 10).map((v, i) => (
                    <span key={i} className="badge badge-xs badge-ghost font-mono text-[10px]">
                      {typeof v === 'string' ? (v.length > 60 ? v.slice(0, 60) + '…' : v) : JSON.stringify(v)}
                    </span>
                  ))}
                  {value.length > 10 && <span className="text-xs text-base-content/40">+{value.length - 10}</span>}
                </div>
              ) : typeof value === 'object' ? (
                <pre className="text-xs bg-base-300/50 p-2 rounded font-mono overflow-x-auto">
                  {JSON.stringify(value, null, 2)}
                </pre>
              ) : (
                <span className="text-sm font-mono">{String(value)}</span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
