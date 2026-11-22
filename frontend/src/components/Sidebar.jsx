import { NavLink } from 'react-router-dom'
import {
  Bell,
  FileText,
  LayoutDashboard,
  Receipt,
  SlidersHorizontal,
  TrendingUp,
  Users,
  X,
} from 'lucide-react'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/clients', label: 'Clients', icon: Users },
  { to: '/invoices', label: 'Invoices', icon: FileText },
  { to: '/expenses', label: 'Expenses', icon: Receipt },
  { to: '/cash-flow', label: 'Cash Flow Forecast', icon: TrendingUp },
  { to: '/what-if', label: 'What-If Simulator', icon: SlidersHorizontal },
  { to: '/action-centre', label: 'Action Centre', icon: Bell },
]

function SidebarContent({ onNavigate, onClose }) {
  return (
    <div className="flex h-full w-60 flex-col bg-white">
      <div className="flex items-center gap-3 px-6 py-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-lg font-bold text-white">
          B
        </div>
        <span className="text-lg font-semibold text-gray-900">SoloLedger</span>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="ml-auto rounded-md p-1 text-gray-500 hover:bg-gray-100 md:hidden"
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        )}
      </div>

      <p className="px-6 pb-2 text-xs font-medium uppercase tracking-wider text-gray-400">
        WORKSPACE
      </p>

      <nav className="flex-1 space-y-1 px-3">
        {navItems.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                isActive
                  ? 'bg-indigo-50 text-indigo-600'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              }`
            }
          >
            <Icon size={18} aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-gray-200 p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-600">
            F
          </div>
          <span className="text-sm text-gray-600">Freelancer workspace</span>
        </div>
      </div>
    </div>
  )
}

export default function Sidebar({ open = false, onClose }) {
  return (
    <>
      <aside className="hidden md:sticky md:top-0 md:flex md:h-screen md:w-60 md:shrink-0 md:flex-col md:border-r md:border-gray-200 md:bg-white">
        <SidebarContent />
      </aside>

      {open && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-gray-900/40"
            onClick={onClose}
            aria-hidden="true"
          />
          <aside className="relative h-full w-60 bg-white shadow-xl">
            <SidebarContent onNavigate={onClose} onClose={onClose} />
          </aside>
        </div>
      )}
    </>
  )
}
