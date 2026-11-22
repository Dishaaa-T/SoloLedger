import { useLocation } from 'react-router-dom'
import { Menu } from 'lucide-react'

const pageMeta = {
  '/': {
    title: 'Dashboard',
    subtitle: "Welcome back! Here's your business overview.",
  },
  '/clients': {
    title: 'Clients',
    subtitle: 'Manage the people and businesses you bill.',
  },
  '/invoices': {
    title: 'Invoices',
    subtitle: 'Track what you have billed and what is still owed.',
  },
  '/expenses': {
    title: 'Expenses',
    subtitle: 'Record and review your business spending.',
  },
  '/cash-flow': {
    title: 'Cash Flow Forecast',
    subtitle: 'See where your cash is heading.',
  },
  '/what-if': {
    title: 'What-If Simulator',
    subtitle: 'Test scenarios before you commit.',
  },
  '/action-centre': {
    title: 'Action Centre',
    subtitle: 'Items that need your attention.',
  },
}

export default function Header({ onMenuClick }) {
  const { pathname } = useLocation()
  const meta = pageMeta[pathname] || { title: 'SoloLedger', subtitle: '' }

  return (
    <header className="flex items-center gap-4 border-b border-gray-200 bg-white px-4 py-4 md:px-8">
      <button
        type="button"
        onClick={onMenuClick}
        className="rounded-lg p-2 text-gray-600 hover:bg-gray-100 md:hidden"
        aria-label="Open menu"
      >
        <Menu size={22} />
      </button>

      <div className="min-w-0 flex-1">
        <div className="truncate text-xl font-bold text-gray-900">
          {meta.title}
        </div>
        {meta.subtitle && (
          <p className="truncate text-sm text-gray-500">{meta.subtitle}</p>
        )}
      </div>

      <div className="hidden items-center gap-2 text-sm text-gray-600 sm:flex">
        <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
        Business Overview
      </div>

      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-600 text-sm font-semibold text-white">
        F
      </div>
    </header>
  )
}
