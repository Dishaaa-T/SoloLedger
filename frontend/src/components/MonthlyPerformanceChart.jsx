import { useCallback, useEffect, useMemo, useState } from 'react'
import { getExpenses, getInvoices } from '../services/api'
import { buildMonthlyPerformance } from '../utils/chartData'
import LoadingState from './LoadingState'
import ErrorState from './ErrorState'
import EmptyState from './EmptyState'

const currencyFormatter = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 2,
})

const formatINR = (value) => `₹${currencyFormatter.format(Number(value) || 0)}`

const barHeight = (value, maxValue) =>
  maxValue > 0 ? (value / maxValue) * 100 : 0

export default function MonthlyPerformanceChart() {
  const [status, setStatus] = useState('loading')
  const [invoices, setInvoices] = useState([])
  const [expenses, setExpenses] = useState([])

  const load = useCallback(async () => {
    setStatus('loading')
    try {
      const [invoicesResponse, expensesResponse] = await Promise.all([
        getInvoices(),
        getExpenses(),
      ])
      setInvoices(Array.isArray(invoicesResponse.data) ? invoicesResponse.data : [])
      setExpenses(Array.isArray(expensesResponse.data) ? expensesResponse.data : [])
      setStatus('success')
    } catch {
      setInvoices([])
      setExpenses([])
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const data = useMemo(
    () => buildMonthlyPerformance(invoices, expenses),
    [invoices, expenses],
  )

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6">
      <h3 className="text-lg font-semibold text-slate-900">
        Monthly Financial Performance
      </h3>

      <div className="mt-4">
        {status === 'loading' && <LoadingState />}

        {status === 'error' && <ErrorState onRetry={load} />}

        {status === 'success' && data.months.length === 0 && (
          <EmptyState
            title="No activity yet"
            message="No paid invoices or expenses exist yet."
          />
        )}

        {status === 'success' && data.months.length > 0 && (
          <>
            <div className="mb-4 flex items-center gap-4 text-xs text-slate-600">
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-sm bg-emerald-500" aria-hidden="true" />
                Income
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-sm bg-indigo-500" aria-hidden="true" />
                Expenses
              </span>
            </div>

            <div className="space-y-4">
              {data.months.map((month) => (
                <div key={month.key} className="flex items-center gap-3">
                  <span className="w-20 shrink-0 text-xs font-medium text-slate-600 sm:w-24">
                    {month.label}
                  </span>
                  <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                    <div className="flex items-center gap-2">
                      <div className="relative h-3 flex-1 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-emerald-500 transition-[width] duration-500"
                          style={{ width: `${barHeight(month.income, data.maxValue)}%` }}
                          title={`Income: ${formatINR(month.income)}`}
                        />
                      </div>
                      <span className="w-24 shrink-0 text-right text-xs tabular-nums text-slate-600">
                        {formatINR(month.income)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="relative h-3 flex-1 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-indigo-500 transition-[width] duration-500"
                          style={{ width: `${barHeight(month.expenses, data.maxValue)}%` }}
                          title={`Expenses: ${formatINR(month.expenses)}`}
                        />
                      </div>
                      <span className="w-24 shrink-0 text-right text-xs tabular-nums text-slate-600">
                        {formatINR(month.expenses)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  )
}
