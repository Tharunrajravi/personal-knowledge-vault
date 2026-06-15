// pages/Tags.jsx — Create and manage tags
import { useEffect, useState } from 'react'
import { Plus, Trash2, Tag } from 'lucide-react'
import toast from 'react-hot-toast'
import { tags as tagsApi } from '../api/services'

const PRESET_COLORS = [
  '#6366f1', '#8b5cf6', '#ec4899', '#ef4444',
  '#f59e0b', '#10b981', '#06b6d4', '#3b82f6',
  '#64748b', '#84cc16',
]

export default function Tags() {
  const [tagsList, setTagsList] = useState([])
  const [name, setName]         = useState('')
  const [color, setColor]       = useState('#6366f1')
  const [loading, setLoading]   = useState(false)

  const load = () =>
    tagsApi.list().then((r) => setTagsList(r.data)).catch(() => {})

  useEffect(() => { load() }, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setLoading(true)
    try {
      await tagsApi.create({ name: name.trim(), color })
      toast.success(`Tag "${name}" created`)
      setName('')
      load()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create tag')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id, tagName) => {
    if (!confirm(`Delete tag "${tagName}"?`)) return
    await tagsApi.delete(id)
    toast.success('Tag deleted')
    load()
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Tags</h1>
        <p className="text-gray-500 text-sm mt-1">Organise your links with tags</p>
      </div>

      {/* Create tag */}
      <div className="card p-5">
        <h2 className="font-semibold text-gray-900 mb-4">Create Tag</h2>
        <form onSubmit={handleCreate} className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              className="input"
              placeholder="e.g. machine-learning"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Color</label>
            <div className="flex gap-1.5 flex-wrap w-44">
              {PRESET_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setColor(c)}
                  className={`w-7 h-7 rounded-full transition-transform ${
                    color === c ? 'scale-125 ring-2 ring-offset-1 ring-gray-400' : 'hover:scale-110'
                  }`}
                  style={{ backgroundColor: c }}
                />
              ))}
            </div>
          </div>
          <button type="submit" disabled={loading || !name.trim()} className="btn-primary">
            <Plus className="w-4 h-4" />
          </button>
        </form>

        {/* Preview */}
        {name && (
          <div className="mt-3">
            <span
              className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium"
              style={{ backgroundColor: color + '20', color }}
            >
              <Tag className="w-3 h-3" />
              {name}
            </span>
          </div>
        )}
      </div>

      {/* Tags list */}
      <div className="card divide-y divide-gray-50">
        {tagsList.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            <Tag className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p>No tags yet</p>
          </div>
        ) : (
          tagsList.map((tag) => (
            <div key={tag.id} className="flex items-center justify-between p-4">
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 rounded-full" style={{ backgroundColor: tag.color }} />
                <span className="font-medium text-gray-900">{tag.name}</span>
                <span className="text-sm text-gray-400">{tag.link_count} links</span>
              </div>
              <button
                onClick={() => handleDelete(tag.id, tag.name)}
                className="text-gray-300 hover:text-red-400 transition-colors p-1"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
