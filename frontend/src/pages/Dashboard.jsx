import { useCallback, useEffect, useState } from 'react'
import { IndianRupee } from 'lucide-react'
import { getDashboardSummary } from '../services/api'
import StatCard from '../components/StatCard'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import EmptyState from '../components/EmptyState'
import MonthlyPerformanceChart from '../components/MonthlyPerformanceChart'
import ExpenseDonutChart from '../components/ExpenseDonutChart'
import MonthlyCashFlowChart from '../components/MonthlyCashFlowChart'

const currencyFormatter = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 2,
})

const formatINR = (value) => {
  const amount = Number(value)
  if (value == null || value === '' || Number.isNaN(amount)) return '—'
  return `₹${currencyFormatter.format(amount)}`
}

const STAT_CARDS = [
  { key: 'total_income', label: 'Total Income', tone: 'positive' },
  { key: 'total_expenses', label: 'Total Expenses', tone: 'negative' },
  { key: 'net_profit', label: 'Net Profit', tone: 'signed' },
  { key: 'pending_payments', label: 'Pending Payments', tone: 'neutral' },
  { key: 'overdue_payments', label: 'Overdue Payments', tone: 'negative' },
  { key: 'available_cash', label: 'Available Cash', tone: 'neutral' },
]

export default function Dashboard() {
  const [status, setStatus] = useState('loading')
  const [summary, setSummary] = useState(null)

  const load = useCallback(async () => {
    setStatus('loading')
    try {
      const response = await getDashboardSummary('this_month')
      const data = response.data
      const hasData =
        data && typeof data === 'object' && Object.keys(data).length > 0
      setSummary(hasData ? data : null)
      setStatus('success')
    } catch {
      setSummary(null)
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="space-y-6">
      <section className="flex items-center justify-between gap-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-violet-500 p-6 text-white shadow-sm md:p-8">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-indigo-100">
            YOUR BUSINESS AT A GLANCE
          </p>
          <h2 className="mt-2 text-2xl font-bold md:text-3xl">
            Manage smarter. Grow faster.
          </h2>
          <p className="mt-2 text-sm text-indigo-100">
            Keep track of your clients, invoices, expenses and cash flow.
          </p>
        </div>
        <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-white/20 md:h-20 md:w-20">
          <IndianRupee className="h-8 w-8 md:h-10 md:w-10" aria-hidden="true" />
        </div>
      </section>

      <MonthlyCashFlowChart />

      {status === 'loading' && <LoadingState />}

      {status === 'error' && <ErrorState onRetry={load} />}

      {status === 'success' && !summary && (
        <EmptyState
          title="No summary yet"
          message="No data yet. Connect the backend to load your dashboard figures."
        />
      )}

      {status === 'success' && summary && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {STAT_CARDS.map((card) => {
            const value = summary[card.key]
            let tone = card.tone
            if (tone === 'signed') {
              tone = Number(value) < 0 ? 'negative' : 'positive'
            }
            return (
              <StatCard
                key={card.key}
                label={card.label}
                value={formatINR(value)}
                tone={tone}
              />
            )
          })}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        <div className="xl:col-span-3">
          <MonthlyPerformanceChart />
        </div>
        <div className="xl:col-span-2">
          <ExpenseDonutChart />
        </div>
      </div>
    </div>
  )
}
