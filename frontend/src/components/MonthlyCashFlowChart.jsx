import { useCallback, useEffect, useMemo, useState } from 'react'
import { getExpenses, getInvoices } from '../services/api'
import { buildMonthlyPerformance } from '../utils/chartData'
import LoadingState from './LoadingState'
import ErrorState from './ErrorState'
import EmptyState from './EmptyState'

const VIEW_W = 800
const VIEW_H = 320
const PAD = { left: 72, right: 16, top: 16, bottom: 40 }
const PLOT_W = VIEW_W - PAD.left - PAD.right
const PLOT_H = VIEW_H - PAD.top - PAD.bottom
const GRID_LINES = 5

const SERIES = [
  { key: 'income', label: 'Income', color: '#10b981' },
  { key: 'expenses', label: 'Expenses', color: '#6366f1' },
  { key: 'net', label: 'Net Profit', color: '#7c3aed' },
]

const axisFormatter = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
const tooltipFormatter = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })

const formatAmount = (value, formatter) => {
  const amount = Number(value) || 0
  const sign = amount < 0 ? '-' : ''
  return `${sign}₹${formatter.format(Math.abs(amount))}`
}

/** Smooth cubic Bézier path through points, using midpoint control x-values. */
const buildPath = (points) => {
  if (points.length < 2) return ''
  let d = `M ${points[0].x},${points[0].y}`
  for (let i = 1; i < points.length; i += 1) {
    const prev = points[i - 1]
    const curr = points[i]
    const mid = (prev.x + curr.x) / 2
    d += ` C ${mid},${prev.y} ${mid},${curr.y} ${curr.x},${curr.y}`
  }
  return d
}

/** For more than 6 months, label every other month, always keeping first and last. */
const shouldShowLabel = (index, count) =>
  count <= 6 || index === count - 1 || (index % 2 === 0 && index < count - 2)

export default function MonthlyCashFlowChart() {
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
    () => buildMonthlyPerformance(invoices, expenses, 12),
    [invoices, expenses],
  )

  const chart = useMemo(() => {
    const count = data.months.length
    if (count === 0) return null

    const rows = data.months.map((month) => ({
      ...month,
      net: month.income - month.expenses,
    }))

    const allValues = rows.flatMap((row) => [row.income, row.expenses, row.net])
    const yMin = Math.min(0, ...allValues)
    let yMax = Math.max(0, ...allValues)
    if (yMax === yMin) yMax = yMin + 1

    const yScale = (value) =>
      PAD.top + PLOT_H - ((value - yMin) / (yMax - yMin)) * PLOT_H

    const xs = rows.map((_, i) =>
      PAD.left + (count === 1 ? PLOT_W / 2 : (i * PLOT_W) / (count - 1)),
    )

    const seriesPoints = SERIES.map((series) => ({
      ...series,
      points: rows.map((row, i) => ({
        x: xs[i],
        y: yScale(row[series.key]),
        value: row[series.key],
        label: row.label,
      })),
    }))

    const gridValues = Array.from(
      { length: GRID_LINES },
      (_, i) => yMin + ((yMax - yMin) * i) / (GRID_LINES - 1),
    )

    return { rows, count, yMin, yScale, xs, seriesPoints, gridValues }
  }, [data])

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6 w-full">
      <h3 className="text-lg font-semibold text-slate-900">Monthly Cash Flow Trend</h3>

      <div className="mt-4">
        {status === 'loading' && <LoadingState />}

        {status === 'error' && <ErrorState onRetry={load} />}

        {status === 'success' && chart === null && (
          <EmptyState
            title="No cash flow history yet"
            message="Paid invoices and expenses will appear here by month."
          />
        )}

        {status === 'success' && chart !== null && (
          <>
            <div className="mb-4 flex items-center gap-4 text-xs text-slate-600">
              {SERIES.map((series) => (
                <span key={series.key} className="inline-flex items-center gap-1.5">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: series.color }}
                    aria-hidden="true"
                  />
                  {series.label}
                </span>
              ))}
            </div>

            <div className="w-full overflow-x-auto">
              <svg
                viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
                width="100%"
                height="auto"
                style={{ display: 'block', minWidth: '560px' }}
                role="img"
                aria-label="Line chart of monthly income, expenses and net profit"
              >
                {/* Horizontal gridlines and Y-axis labels */}
                {chart.gridValues.map((value, i) => {
                  const y = chart.yScale(value)
                  return (
                    <g key={`grid-${i}`}>
                      <line
                        x1={PAD.left}
                        x2={PAD.left + PLOT_W}
                        y1={y}
                        y2={y}
                        stroke="#e2e8f0"
                        strokeWidth={1}
                      />
                      <text
                        x={PAD.left - 8}
                        y={y}
                        textAnchor="end"
                        dominantBaseline="middle"
                        fontSize={12}
                        fill="#64748b"
                      >
                        {formatAmount(value, axisFormatter)}
                      </text>
                    </g>
                  )
                })}

                {/* Emphasised zero line when the domain goes negative */}
                {chart.yMin < 0 && (
                  <line
                    x1={PAD.left}
                    x2={PAD.left + PLOT_W}
                    y1={chart.yScale(0)}
                    y2={chart.yScale(0)}
                    stroke="#94a3b8"
                    strokeWidth={1}
                  />
                )}

                {/* X-axis month labels */}
                {chart.rows.map((row, i) =>
                  shouldShowLabel(i, chart.count) ? (
                    <text
                      key={`x-${row.key}`}
                      x={chart.xs[i]}
                      y={VIEW_H - PAD.bottom + 20}
                      textAnchor="middle"
                      fontSize={12}
                      fill="#64748b"
                    >
                      {row.label}
                    </text>
                  ) : null,
                )}

                {/* Smooth lines (only when there are at least two months) */}
                {chart.count >= 2 &&
                  chart.seriesPoints.map((series) => (
                    <path
                      key={`line-${series.key}`}
                      d={buildPath(series.points)}
                      fill="none"
                      stroke={series.color}
                      strokeWidth={2.5}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  ))}

                {/* Point markers with transparent hit areas carrying native tooltips */}
                {chart.seriesPoints.map((series) => (
                  <g key={`points-${series.key}`}>
                    {series.points.map((point, i) => (
                      <g key={`point-${series.key}-${i}`}>
                        <circle
                          cx={point.x}
                          cy={point.y}
                          r={3.5}
                          fill="#ffffff"
                          stroke={series.color}
                          strokeWidth={2}
                        />
                        <circle cx={point.x} cy={point.y} r={10} fill="transparent">
                          <title>
                            {`${point.label} · ${series.label}: ${formatAmount(point.value, tooltipFormatter)}`}
                          </title>
                        </circle>
                      </g>
                    ))}
                  </g>
                ))}
              </svg>
            </div>

            {chart.count === 1 && (
              <p className="mt-3 text-xs text-slate-500">
                Add activity in another month to see a trend line.
              </p>
            )}
          </>
        )}
      </div>
    </section>
  )
}
