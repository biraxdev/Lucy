import { useState, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, ArrowLeft, ArrowRight, RefreshCw, ExternalLink, Globe, Loader2, Bookmark, Check } from 'lucide-react'
import { webSearch, fetchUrl, type WebSearchResult } from '../../api/copilot'
import { createResource } from '../../api/library'
import { useCopilotStore } from '../../stores/copilotStore'

export function WebBrowser() {
  const [url, setUrl] = useState('')
  const [currentUrl, setCurrentUrl] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<WebSearchResult | null>(null)
  const [searching, setSearching] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const { openWithMessage } = useCopilotStore()
  const qc = useQueryClient()

  const saveMut = useMutation({
    mutationFn: async () => {
      if (!currentUrl) return
      setSaving(true)
      // Fetch the URL content through the existing fetch-url endpoint
      const fetched = await fetchUrl(currentUrl)
      // Determine resource type from content
      const isHTML = fetched.content_type?.includes('text/html')
      const resourceType = isHTML ? 'research' : 'documentation'
      // Extract a name from the URL
      const name = currentUrl.split('/').pop()?.split('?')[0] || currentUrl
      return createResource({
        resource_type: resourceType as any,
        name: name.slice(0, 200),
        description: `Saved from ${currentUrl}`,
        content: fetched.content,
        status: 'draft',
        tags: ['web', 'saved'],
        source: currentUrl,
      })
    },
    onSuccess: () => {
      setSaving(false)
      setSaved(true)
      qc.invalidateQueries({ queryKey: ['library'] })
      setTimeout(() => setSaved(false), 2000)
    },
    onError: () => {
      setSaving(false)
    },
  })

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const results = await webSearch(searchQuery, 8)
      setSearchResults(results)
    } finally {
      setSearching(false)
    }
  }

  const navigate = (target: string) => {
    let full = target.trim()
    if (!full) return
    if (!full.startsWith('http://') && !full.startsWith('https://')) {
      // Check if it's a URL or a search query
      if (full.includes('.') && !full.includes(' ')) {
        full = 'https://' + full
      } else {
        setSearchQuery(full)
        handleSearch()
        return
      }
    }
    setCurrentUrl(full)
    setUrl(full)
    setLoading(true)
  }

  const saveSearchResult = async (result: { title: string; url: string }) => {
    setSaving(true)
    try {
      const fetched = await fetchUrl(result.url)
      await createResource({
        resource_type: 'research' as any,
        name: result.title.slice(0, 200),
        description: `Saved from ${result.url}`,
        content: fetched.content,
        status: 'draft',
        tags: ['web', 'saved', 'search'],
        source: result.url,
      })
      qc.invalidateQueries({ queryKey: ['library'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      console.error('Save failed:', e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Address bar */}
      <div className="shrink-0 p-2 border-b border-base-300 space-y-2">
        <div className="flex gap-1.5">
          <button
            className="btn btn-xs btn-ghost btn-square"
            onClick={() => window.history.back()}
          >
            <ArrowLeft size={14} />
          </button>
          <button
            className="btn btn-xs btn-ghost btn-square"
            onClick={() => iframeRef.current?.contentWindow?.location.reload()}
          >
            <RefreshCw size={14} />
          </button>
          <div className="flex-1 flex items-center gap-1.5 input input-sm input-bordered bg-base-200">
            <Globe size={12} className="text-base-content/40 shrink-0" />
            <input
              type="text"
              className="flex-1 bg-transparent outline-none text-xs"
              placeholder="URL ou recherche..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') navigate(url)
              }}
            />
          </div>
          <button
            className="btn btn-xs btn-success btn-square"
            onClick={() => navigate(url)}
          >
            <ArrowRight size={14} />
          </button>
        </div>

        {/* Quick search */}
        <div className="flex gap-1.5">
          <input
            type="text"
            className="input input-xs input-bordered flex-1 bg-base-200 text-xs"
            placeholder="Recherche DuckDuckGo..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSearch()
            }}
          />
          <button
            className="btn btn-xs btn-outline gap-1"
            onClick={handleSearch}
            disabled={searching}
          >
            {searching ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
            Chercher
          </button>
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {/* Search results */}
        {searchResults && !currentUrl && (
          <div className="h-full overflow-y-auto p-2 space-y-2 scrollbar-thin">
            <div className="text-xs text-base-content/50 mb-2">
              {searchResults.count} résultats pour "{searchResults.query}"
              {searchResults.error && <span className="text-error"> — {searchResults.error}</span>}
            </div>
            {searchResults.results.map((r, i) => (
              <div
                key={i}
                className="p-2 rounded-lg bg-base-300/50 hover:bg-base-300 cursor-pointer transition-colors group"
                onClick={() => navigate(r.url)}
              >
                <div className="flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-success truncate">{r.title}</div>
                    <div className="text-[10px] text-base-content/40 truncate">{r.url}</div>
                  </div>
                  <button
                    className="btn btn-xs btn-ghost opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => {
                      e.stopPropagation()
                      saveSearchResult(r)
                    }}
                    title="Save to Library"
                  >
                    <Bookmark size={10} />
                  </button>
                </div>
              </div>
            ))}
            {searchResults.results.length === 0 && (
              <div className="text-center text-base-content/30 py-8 text-xs">
                Aucun résultat
              </div>
            )}
          </div>
        )}

        {/* iframe */}
        {currentUrl && (
          <div className="h-full relative">
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center bg-base-200/80 z-10">
                <Loader2 size={24} className="animate-spin text-success" />
              </div>
            )}
            <iframe
              ref={iframeRef}
              src={currentUrl}
              className="w-full h-full border-0"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
              onLoad={() => setLoading(false)}
              onError={() => setLoading(false)}
              title="web-browser"
            />
            {/* Fallback link for sites that block iframes */}
            <div className="absolute bottom-2 right-2 flex gap-1">
              <button
                className={`btn btn-xs gap-1 bg-base-100/80 ${saved ? 'btn-success' : 'btn-ghost'}`}
                onClick={() => saveMut.mutate()}
                disabled={saving || saved}
                title="Save to Library"
              >
                {saving ? <Loader2 size={12} className="animate-spin" /> : saved ? <Check size={12} /> : <Bookmark size={12} />}
                {saved ? 'Saved' : 'Save'}
              </button>
              <a
                href={currentUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-xs btn-ghost gap-1 bg-base-100/80"
              >
                <ExternalLink size={12} /> Ouvrir
              </a>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!searchResults && !currentUrl && (
          <div className="h-full flex items-center justify-center text-center text-base-content/30 p-4">
            <div className="space-y-2">
              <Globe size={32} className="mx-auto opacity-30" />
              <p className="text-xs">Recherche le web ou entre une URL</p>
              <div className="flex flex-wrap gap-1 justify-center mt-3">
                {['cve mitre', 'nmap documentation', 'latest windows exploits', 'MITRE ATT&CK'].map((q) => (
                  <button
                    key={q}
                    className="badge badge-xs badge-ghost cursor-pointer hover:badge-success text-[10px]"
                    onClick={() => {
                      setSearchQuery(q)
                      handleSearch()
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>
              <button
                className="btn btn-xs btn-outline mt-3 gap-1"
                onClick={() => openWithMessage('Recherche le web pour la dernière CVE Windows')}
              >
                Demander au Copilot de chercher
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
