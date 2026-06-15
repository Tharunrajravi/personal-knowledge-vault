// pages/Dashboard.jsx — Analytics dashboard
import { useEffect, useState } from 'react'
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer
} from 'recharts'
import {
  Link2, Star, Archive, BookOpen,
  TrendingUp, Globe, Tag, ExternalLink
} from 'lucide-react'
import { dashboard } from '../api/services'
import { format, parseISO } from 'date-fns'

const COLORS = ['#6366f1', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

const StatCard = ({ icon: Icon, label, value, color }) => (
  <div className="card p-5 flex items-center gap-4">
    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color}`}>
      <Icon className="w-6 h-6 text-white" />
    </div>
    <div>
      <p className="text-2xl font-bold text-gray-900">{value ?? '—'}</p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  </div>
)

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    dashboard.get()
      .then((r) => setData(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600
                        rounded-full animate-spin" />
      </div>
    )
  }

  if (!data) return <p className="text-gray-500">Failed to load dashboard.</p>

  const { summary, links_by_type, links_per_day, top_domains, top_tags, recent_links } = data

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-1">Your knowledge vault at a glance</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Link2}   label="Total Links"    value={summary.total_links}     color="bg-primary-600" />
        <StatCard icon={Star}    label="Favorites"      value={summary.total_favorites} color="bg-amber-500" />
        <StatCard icon={BookOpen} label="Unread"        value={summary.total_unread}    color="bg-emerald-500" />
        <StatCard icon={Archive} label="Archived"       value={summary.total_archived}  color="bg-gray-400" />
      </div>

      {/* Activity chart */}
      {links_per_day?.length > 0 && (
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-primary-600" />
            <h2 className="font-semibold text-gray-900">Links saved (last 30 days)</h2>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={links_per_day}>
              <defs>
                <linearGradient id="colorLinks" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="date"
                tickFormatter={(d) => format(parseISO(d), 'MMM d')}
                tick={{ fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis hide />
              <Tooltip
                labelFormatter={(d) => format(parseISO(d), 'MMM d, yyyy')}
                formatter={(v) => [v, 'Links']}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#6366f1"
                strokeWidth={2}
                fill="url(#colorLinks)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Links by type */}
        {links_by_type?.length > 0 && (
          <div className="card p-5">
            <h2 className="font-semibold text-gray-900 mb-4">By Type</h2>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={links_by_type}
                  dataKey="count"
                  nameKey="type"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  label={({ type, percent }) =>
                    `${type} ${(percent * 100).toFixed(0)}%`
                  }
                  labelLine={false}
                >
                  {links_by_type.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v, n) => [v, n]} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Top domains */}
        {top_domains?.length > 0 && (
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-4">
              <Globe className="w-4 h-4 text-gray-400" />
              <h2 className="font-semibold text-gray-900">Top Sources</h2>
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={top_domains.slice(0, 6)} layout="vertical">
                <XAxis type="number" hide />
                <YAxis
                  dataKey="domain"
                  type="category"
                  width={90}
                  tick={{ fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip />
                <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Top tags */}
        {top_tags?.length > 0 && (
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-4">
              <Tag className="w-4 h-4 text-gray-400" />
              <h2 className="font-semibold text-gray-900">Top Tags</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              {top_tags.map((t) => (
                <span
                  key={t.name}
                  className="inline-flex items-center gap-1 px-3 py-1 rounded-full
                             text-sm font-medium"
                  style={{ backgroundColor: t.color + '20', color: t.color }}
                >
                  {t.name}
                  <span className="text-xs opacity-70">({t.count})</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Recent links */}
      {recent_links?.length > 0 && (
        <div className="card p-5">
          <h2 className="font-semibold text-gray-900 mb-4">Recently Saved</h2>
          <div className="space-y-3">
            {recent_links.map((link) => (
              <div key={link.id}
                   className="flex items-center justify-between py-2
                              border-b border-gray-50 last:border-0">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {link.title || link.url}
                  </p>
                  <p className="text-xs text-gray-400">
                    {link.domain} · {format(new Date(link.created_at), 'MMM d')}
                  </p>
                </div>
                <a
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-3 text-gray-400 hover:text-primary-600 flex-shrink-0"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
