import { useCallback, useEffect, useMemo, useState } from 'react'
import { getExpenses } from '../services/api'
import {
  buildConicGradient,
  buildExpenseCategoryBreakdown,
  groupTopCategories,
} from '../utils/chartData'
import LoadingState from './LoadingState'
import ErrorState from './ErrorState'
import EmptyState from './EmptyState'

// Index-aligned with ranked categories; the 8th colour is reserved for 'Other'.
const PALETTE = ['#4f46e5', '#10b981', '#f59e0b', '#f43f5e', '#0ea5e9', '#a855f7', '#84cc16', '#64748b']

const MAX_CATEGORIES = 7

const currencyFormatter = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 2,
})

const formatINR = (value) => `₹${currencyFormatter.format(Number(value) || 0)}`

export default function ExpenseDonutChart() {
  const [status, setStatus] = useState('loading')
  const [expenses, setExpenses] = useState([])

  const load = useCallback(async () => {
    setStatus('loading')
    try {
      const response = await getExpenses()
      setExpenses(Array.isArray(response.data) ? response.data : [])
      setStatus('success')
    } catch {
      setExpenses([])
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const breakdown = useMemo(() => buildExpenseCategoryBreakdown(expenses), [expenses])
  const display = useMemo(
    () => groupTopCategories(breakdown.categories, MAX_CATEGORIES),
    [breakdown],
  )
  const gradient = useMemo(
    () => buildConicGradient(display, PALETTE),
    [display],
  )

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6">
      <h3 className="text-lg font-semibold text-slate-900">
        Expense Breakdown by Category
      </h3>

      <div className="mt-4">
        {status === 'loading' && <LoadingState />}

        {status === 'error' && <ErrorState onRetry={load} />}

        {status === 'success' && breakdown.total === 0 && (
          <EmptyState
            title="No expenses yet"
            message="No expenses recorded yet."
          />
        )}

        {status === 'success' && breakdown.total > 0 && (
          <div className="flex flex-col items-center gap-6 md:flex-row">
            <div
              className="relative h-48 w-48 shrink-0 rounded-full"
              style={{ background: gradient }}
            >
              <div className="absolute inset-6 flex flex-col items-center justify-center rounded-full bg-white text-center">
                <span className="text-sm font-semibold text-slate-900">
                  {formatINR(breakdown.total)}
                </span>
                <span className="text-xs text-slate-500">Total</span>
              </div>
            </div>

            <ul className="w-full space-y-2">
              {display.map((category, index) => (
                <li
                  key={`${category.name}-${index}`}
                  className="flex items-center justify-between gap-3 text-sm"
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <span
                      className="inline-block h-3 w-3 shrink-0 rounded-full"
                      style={{ backgroundColor: PALETTE[index % PALETTE.length] }}
                      aria-hidden="true"
                    />
                    <span className="min-w-0 truncate text-slate-700">{category.name}</span>
                  </span>
                  <span className="shrink-0 text-slate-600">
                    {formatINR(category.amount)}{' '}
                    <span className="text-slate-500">· {category.percent.toFixed(1)}%</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  )
}
