// api/services.js — All API calls in one place
import client from './client'

// ── Auth ──────────────────────────────────────────────────────────────────────
export const auth = {
  register: (data) => client.post('/api/auth/register', data),

  login: async (username, password) => {
    const form = new URLSearchParams({ username, password })
    const res = await client.post('/api/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    // Store tokens
    localStorage.setItem('access_token', res.data.access_token)
    localStorage.setItem('refresh_token', res.data.refresh_token)
    localStorage.setItem('user', JSON.stringify(res.data.user))
    return res.data
  },

  logout: async () => {
    const refresh_token = localStorage.getItem('refresh_token')
    if (refresh_token) {
      await client.post('/api/auth/logout', { refresh_token }).catch(() => {})
    }
    localStorage.clear()
  },

  me: () => client.get('/api/auth/me'),
}

// ── Links ─────────────────────────────────────────────────────────────────────
export const links = {
  list: (params = {}) => client.get('/api/links', { params }),
  get: (id) => client.get(`/api/links/${id}`),
  save: (data) => client.post('/api/links', data),
  update: (id, data) => client.patch(`/api/links/${id}`, data),
  delete: (id) => client.delete(`/api/links/${id}`),
  toggleFavorite: (id) => client.post(`/api/links/${id}/favorite`),
  search: (q, params = {}) => client.get('/api/links/search', { params: { q, ...params } }),
  preview: (url) => client.post('/api/scraper/preview', { url }),
}

// ── Tags ──────────────────────────────────────────────────────────────────────
export const tags = {
  list: () => client.get('/api/tags'),
  create: (data) => client.post('/api/tags', data),
  delete: (id) => client.delete(`/api/tags/${id}`),
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export const dashboard = {
  get: () => client.get('/api/dashboard'),
}

// ── Export ────────────────────────────────────────────────────────────────────
export const exports = {
  triggerPDF: (params = {}) => client.post('/api/export/pdf', null, { params }),
  getStatus: (jobId) => client.get(`/api/export/status/${jobId}`),
}
