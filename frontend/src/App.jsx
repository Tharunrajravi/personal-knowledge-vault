// App.jsx — Router + auth guard
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useAuthStore } from './store/auth'
import Layout from './components/Layout'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'
import Links from './pages/Links'
import Tags from './pages/Tags'

// Favorites is just Links with is_favorite filter pre-applied
import { useEffect } from 'react'
const Favorites = () => {
  useEffect(() => {}, [])
  return <Links defaultFilter={{ is_favorite: true }} />
}

// Protected route wrapper
const Protected = ({ children }) => {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Layout>{children}</Layout>
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            borderRadius: '10px',
            fontSize: '14px',
          },
        }}
      />
      <Routes>
        <Route path="/login" element={<Auth />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        <Route path="/dashboard" element={
          <Protected><Dashboard /></Protected>
        } />
        <Route path="/links" element={
          <Protected><Links /></Protected>
        } />
        <Route path="/favorites" element={
          <Protected><Links defaultFilter={{ is_favorite: true }} /></Protected>
        } />
        <Route path="/tags" element={
          <Protected><Tags /></Protected>
        } />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
