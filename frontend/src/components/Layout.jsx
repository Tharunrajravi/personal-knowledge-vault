// components/Layout.jsx — Sidebar + main content wrapper
import { NavLink, useNavigate } from 'react-router-dom'
import {
  BookMarked, LayoutDashboard, Link2,
  Tag, Star, LogOut, Menu, X
} from 'lucide-react'
import { useState } from 'react'
import { auth } from '../api/services'
import { useAuthStore } from '../store/auth'
import toast from 'react-hot-toast'

const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/links',     icon: Link2,           label: 'All Links'  },
  { to: '/favorites', icon: Star,            label: 'Favorites'  },
  { to: '/tags',      icon: Tag,             label: 'Tags'       },
]

const NavItem = ({ to, icon: Icon, label, onClick }) => (
  <NavLink
    to={to}
    onClick={onClick}
    className={({ isActive }) =>
      `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
       transition-colors ${
        isActive
          ? 'bg-primary-600 text-white'
          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
      }`
    }
  >
    <Icon className="w-4 h-4 flex-shrink-0" />
    {label}
  </NavLink>
)

export default function Layout({ children }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  const handleLogout = async () => {
    await auth.logout()
    logout()
    navigate('/login')
    toast.success('Logged out')
  }

  const Sidebar = ({ onNavClick }) => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-3 py-4 mb-2">
        <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
          <BookMarked className="w-4 h-4 text-white" />
        </div>
        <div>
          <p className="font-bold text-gray-900 text-sm leading-tight">Knowledge</p>
          <p className="text-xs text-gray-500 leading-tight">Vault</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 px-2">
        {NAV.map((item) => (
          <NavItem key={item.to} {...item} onClick={onNavClick} />
        ))}
      </nav>

      {/* User + logout */}
      <div className="px-2 pb-4 border-t border-gray-100 pt-4">
        <div className="flex items-center justify-between px-3 py-2">
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">
              {user?.username}
            </p>
            <p className="text-xs text-gray-400 truncate">{user?.email}</p>
          </div>
          <button
            onClick={handleLogout}
            className="ml-2 p-1.5 text-gray-400 hover:text-red-500
                       hover:bg-red-50 rounded-lg transition-colors flex-shrink-0"
            title="Logout"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen flex">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col w-56 bg-white border-r border-gray-100
                        fixed inset-y-0 left-0">
        <Sidebar />
      </aside>

      {/* Mobile sidebar */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40">
          <div
            className="absolute inset-0 bg-black/30 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute left-0 top-0 bottom-0 w-56 bg-white shadow-xl">
            <div className="absolute top-3 right-3">
              <button onClick={() => setMobileOpen(false)}>
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <Sidebar onNavClick={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 lg:ml-56">
        {/* Mobile topbar */}
        <div className="lg:hidden sticky top-0 z-30 bg-white border-b border-gray-100
                        flex items-center gap-3 px-4 py-3">
          <button onClick={() => setMobileOpen(true)}>
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-primary-600 rounded flex items-center justify-center">
              <BookMarked className="w-3 h-3 text-white" />
            </div>
            <span className="font-semibold text-gray-900 text-sm">Knowledge Vault</span>
          </div>
        </div>

        <div className="p-4 lg:p-8 max-w-5xl mx-auto">
          {children}
        </div>
      </main>
    </div>
  )
}
