// pages/Links.jsx — Main links list with save, search, filter
import { useEffect, useState, useCallback, useRef } from 'react'
import {
  Plus, Search, Star, Archive, Filter,
  X, Loader2, ExternalLink, Trash2,
  Youtube, Github, FileText, Globe,
  CheckCheck, DownloadCloud, Link2
} from 'lucide-react'
import toast from 'react-hot-toast'
import { links as linksApi, tags as tagsApi, exports } from '../api/services'
import { formatDistanceToNow } from 'date-fns'

// ── Link type icon ────────────────────────────────────────────────────────────
const TypeIcon = ({ type }) => {
  const props = { className: 'w-4 h-4' }
  if (type === 'youtube') return <Youtube {...props} className="w-4 h-4 text-red-500" />
  if (type === 'github')  return <Github  {...props} className="w-4 h-4 text-gray-700" />
  if (type === 'pdf')     return <FileText {...props} className="w-4 h-4 text-orange-500" />
  return <Globe {...props} className="w-4 h-4 text-blue-500" />
}

// ── Single link card ──────────────────────────────────────────────────────────
const LinkCard = ({ link, onFavorite, onDelete, onMarkRead }) => (
  <div className={`card p-4 hover:shadow-md transition-shadow ${
    link.is_read ? 'opacity-75' : ''
  }`}>
    <div className="flex gap-3">
      {/* Favicon */}
      <div className="flex-shrink-0 mt-0.5">
        {link.favicon_url ? (
          <img
            src={link.favicon_url}
            alt=""
            className="w-6 h-6 rounded"
            onError={(e) => { e.target.style.display = 'none' }}
          />
        ) : (
          <TypeIcon type={link.link_type} />
        )}
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <a
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-gray-900 hover:text-primary-600
                       line-clamp-1 flex-1 transition-colors"
          >
            {link.title || link.url}
          </a>
          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              onClick={() => onFavorite(link.id)}
              className={`p-1 rounded hover:bg-gray-100 transition-colors ${
                link.is_favorite ? 'text-amber-500' : 'text-gray-300 hover:text-amber-400'
              }`}
            >
              <Star className="w-4 h-4" fill={link.is_favorite ? 'currentColor' : 'none'} />
            </button>
            <button
              onClick={() => onMarkRead(link.id, !link.is_read)}
              className={`p-1 rounded hover:bg-gray-100 transition-colors ${
                link.is_read ? 'text-emerald-500' : 'text-gray-300 hover:text-emerald-400'
              }`}
              title={link.is_read ? 'Mark unread' : 'Mark read'}
            >
              <CheckCheck className="w-4 h-4" />
            </button>
            <button
              onClick={() => onDelete(link.id)}
              className="p-1 rounded hover:bg-red-50 text-gray-300
                         hover:text-red-400 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {link.description && (
          <p className="text-sm text-gray-500 mt-1 line-clamp-2">{link.description}</p>
        )}

        <div className="flex items-center gap-2 mt-2 flex-wrap">
          <span className="text-xs text-gray-400">{link.domain}</span>
          <span className="text-xs text-gray-300">·</span>
          <span className="text-xs text-gray-400">
            {formatDistanceToNow(new Date(link.created_at), { addSuffix: true })}
          </span>

          {/* Scraping badge */}
          {link.scrape_status === 'pending' && (
            <span className="text-xs bg-amber-50 text-amber-600 px-2 py-0.5 rounded-full">
              loading...
            </span>
          )}

          {/* Tags */}
          {link.tags?.map((tag) => (
            <span
              key={tag.id}
              className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={{ backgroundColor: tag.color + '20', color: tag.color }}
            >
              {tag.name}
            </span>
          ))}

          {/* GitHub stars */}
          {link.gh_stars != null && (
            <span className="text-xs text-gray-400">★ {link.gh_stars}</span>
          )}
        </div>
      </div>
    </div>
  </div>
)

// ── Save link modal ───────────────────────────────────────────────────────────
const SaveModal = ({ onClose, onSaved, allTags }) => {
  const [url, setUrl] = useState('')
  const [notes, setNotes] = useState('')
  const [selectedTags, setSelectedTags] = useState([])
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const previewTimer = useRef(null)

  const fetchPreview = useCallback((u) => {
    clearTimeout(previewTimer.current)
    if (!u.startsWith('http')) return
    previewTimer.current = setTimeout(async () => {
      setPreviewing(true)
      try {
        const res = await linksApi.preview(u)
        setPreview(res.data)
      } catch { /* silent */ } finally {
        setPreviewing(false)
      }
    }, 800)
  }, [])

  const handleSave = async () => {
    if (!url) return
    setLoading(true)
    try {
      await linksApi.save({ url, notes, tag_ids: selectedTags })
      toast.success('Link saved!')
      onSaved()
      onClose()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save')
    } finally {
      setLoading(false)
    }
  }

  const toggleTag = (id) =>
    setSelectedTags((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    )

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center
                    z-50 p-4 backdrop-blur-sm">
      <div className="card w-full max-w-lg p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">Save Link</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">URL</label>
            <input
              className="input"
              placeholder="https://..."
              value={url}
              onChange={(e) => { setUrl(e.target.value); fetchPreview(e.target.value) }}
              autoFocus
            />
          </div>

          {/* Preview card */}
          {(previewing || preview) && (
            <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
              {previewing ? (
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <Loader2 className="w-4 h-4 animate-spin" /> Fetching preview...
                </div>
              ) : (
                <div>
                  <p className="font-medium text-sm text-gray-900 line-clamp-1">
                    {preview?.title || 'No title found'}
                  </p>
                  {preview?.description && (
                    <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                      {preview.description}
                    </p>
                  )}
                  <span className="text-xs text-primary-600 mt-1 inline-block capitalize">
                    {preview?.link_type}
                  </span>
                </div>
              )}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Notes (optional)
            </label>
            <textarea
              className="input resize-none"
              rows={2}
              placeholder="Why are you saving this?"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          {/* Tag picker */}
          {allTags.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Tags</label>
              <div className="flex flex-wrap gap-2">
                {allTags.map((tag) => (
                  <button
                    key={tag.id}
                    onClick={() => toggleTag(tag.id)}
                    className={`px-3 py-1 rounded-full text-sm font-medium
                                transition-all border ${
                      selectedTags.includes(tag.id)
                        ? 'border-transparent shadow-sm'
                        : 'border-transparent opacity-60 hover:opacity-100'
                    }`}
                    style={{
                      backgroundColor: tag.color + (selectedTags.includes(tag.id) ? '30' : '15'),
                      color: tag.color,
                    }}
                  >
                    {tag.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button onClick={onClose} className="btn-secondary flex-1">Cancel</button>
            <button
              onClick={handleSave}
              disabled={!url || loading}
              className="btn-primary flex-1"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'Save Link'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main Links page ───────────────────────────────────────────────────────────
export default function Links({ defaultFilter = {} }) {
  const [linksList, setLinksList]   = useState([])
  const [allTags, setAllTags]       = useState([])
  const [loading, setLoading]       = useState(true)
  const [showSave, setShowSave]     = useState(false)
  const [query, setQuery]           = useState('')
  const [filters, setFilters]       = useState({ is_favorite: null, link_type: null })
  const [page, setPage]             = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [exporting, setExporting]   = useState(false)
  const searchTimer = useRef(null)

  const fetchLinks = useCallback(async (q = query, f = filters, p = page) => {
    setLoading(true)
    try {
      let res
      if (q.trim()) {
        res = await linksApi.search(q.trim(), { page: p, per_page: 20 })
        setLinksList(res.data.items)
        setTotalPages(Math.ceil(res.data.total / 20))
      } else {
        const params = { page: p, per_page: 20, is_archived: false }
        if (f.is_favorite !== null) params.is_favorite = f.is_favorite
        if (f.link_type)            params.link_type   = f.link_type
        res = await linksApi.list(params)
        setLinksList(res.data.items)
        setTotalPages(res.data.pages)
      }
    } catch (err) {
      toast.error('Failed to load links')
    } finally {
      setLoading(false)
    }
  }, [query, filters, page])

  useEffect(() => {
    tagsApi.list().then((r) => setAllTags(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => fetchLinks(query, filters, 1), 300)
    setPage(1)
  }, [query, filters])

  useEffect(() => { fetchLinks() }, [page])

  const handleFavorite = async (id) => {
    const res = await linksApi.toggleFavorite(id)
    setLinksList((prev) =>
      prev.map((l) => l.id === id ? { ...l, is_favorite: res.data.is_favorite } : l)
    )
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this link?')) return
    await linksApi.delete(id)
    setLinksList((prev) => prev.filter((l) => l.id !== id))
    toast.success('Deleted')
  }

  const handleMarkRead = async (id, isRead) => {
    await linksApi.update(id, { is_read: isRead })
    setLinksList((prev) =>
      prev.map((l) => l.id === id ? { ...l, is_read: isRead } : l)
    )
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await exports.triggerPDF()
      const jobId = res.data.job_id
      toast.success('Export started — we\'ll notify you when ready')

      // Poll for completion
      const poll = setInterval(async () => {
        const status = await exports.getStatus(jobId)
        if (status.data.status === 'done') {
          clearInterval(poll)
          window.open(status.data.download_url, '_blank')
          setExporting(false)
        } else if (status.data.status === 'failed') {
          clearInterval(poll)
          toast.error('Export failed')
          setExporting(false)
        }
      }, 2000)
    } catch {
      toast.error('Export failed')
      setExporting(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Links</h1>
        <div className="flex gap-2">
          <button
            onClick={handleExport}
            disabled={exporting}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <DownloadCloud className="w-4 h-4" />
            {exporting ? 'Exporting...' : 'Export PDF'}
          </button>
          <button
            onClick={() => setShowSave(true)}
            className="btn-primary flex items-center gap-2 text-sm"
          >
            <Plus className="w-4 h-4" /> Save Link
          </button>
        </div>
      </div>

      {/* Search + Filters */}
      <div className="flex gap-2 flex-wrap">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            className="input pl-9"
            placeholder="Search your links..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400
                         hover:text-gray-600"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Filter buttons */}
        <button
          onClick={() => setFilters((f) => ({
            ...f, is_favorite: f.is_favorite === true ? null : true
          }))}
          className={`btn-secondary flex items-center gap-1.5 text-sm ${
            filters.is_favorite ? 'bg-amber-50 border-amber-200 text-amber-700' : ''
          }`}
        >
          <Star className="w-4 h-4" fill={filters.is_favorite ? 'currentColor' : 'none'} />
          Favorites
        </button>

        {['youtube', 'github', 'article'].map((type) => (
          <button
            key={type}
            onClick={() => setFilters((f) => ({
              ...f, link_type: f.link_type === type ? null : type
            }))}
            className={`btn-secondary text-sm capitalize ${
              filters.link_type === type
                ? 'bg-primary-50 border-primary-200 text-primary-700'
                : ''
            }`}
          >
            {type}
          </button>
        ))}
      </div>

      {/* Links list */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600
                          rounded-full animate-spin" />
        </div>
      ) : linksList.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Link2 className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="font-medium">
            {query ? 'No results found' : 'No links yet'}
          </p>
          {!query && (
            <p className="text-sm mt-1">
              Click <strong>Save Link</strong> to add your first URL
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {linksList.map((link) => (
            <LinkCard
              key={link.id}
              link={link}
              onFavorite={handleFavorite}
              onDelete={handleDelete}
              onMarkRead={handleMarkRead}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <button
            onClick={() => setPage((p) => p - 1)}
            disabled={page === 1}
            className="btn-secondary text-sm px-3 py-1.5 disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-sm text-gray-500">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page === totalPages}
            className="btn-secondary text-sm px-3 py-1.5 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}

      {/* Save modal */}
      {showSave && (
        <SaveModal
          onClose={() => setShowSave(false)}
          onSaved={() => fetchLinks(query, filters, 1)}
          allTags={allTags}
        />
      )}
    </div>
  )
}
