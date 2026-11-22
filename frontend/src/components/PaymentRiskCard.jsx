import { useEffect, useState } from 'react'
import { getClientPaymentRisk } from '../services/api'
import ErrorState from './ErrorState'
import LoadingState from './LoadingState'

const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
})

const riskPillClasses = {
  Low: 'bg-emerald-100 text-emerald-700',
  Medium: 'bg-amber-100 text-amber-700',
  High: 'bg-rose-100 text-rose-700',
  Unknown: 'bg-gray-100 text-gray-600',
}

const barClasses = {
  Low: 'bg-emerald-500',
  Medium: 'bg-amber-500',
  High: 'bg-rose-500',
  Unknown: 'bg-gray-400',
}

function errorMessageFor(error) {
  const status = error?.response?.status
  if (status === 404) return 'Client not found.'
  if (status === 503) {
    return 'The payment-risk model is not available yet. Ask the developer to run: python -m services.payment_training'
  }
  return 'Could not load payment risk for this client.'
}

function StatItem({ label, value }) {
  return (
    <div className="rounded-lg bg-gray-50 p-3">
      <p className="text-xs font-medium text-gray-500">{label}</p>
      <p className="mt-1 text-base font-semibold text-gray-900">{value}</p>
    </div>
  )
}

export default function PaymentRiskCard({ clientId, clientName }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setData(null)

    getClientPaymentRisk(clientId)
      .then((res) => {
        if (!cancelled) setData(res.data)
      })
      .catch((err) => {
        if (!cancelled) setError(err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [clientId, reloadKey])

  const retry = () => setReloadKey((k) => k + 1)

  const header = (
    <div>
      <h2 className="text-lg font-semibold text-gray-900">Payment Risk</h2>
      <p className="text-sm text-gray-600">{clientName}</p>
      <p className="mt-1 text-xs text-gray-500">
        Probability of a late payment, not the probability of on-time payment
      </p>
    </div>
  )

  let body
  if (loading) {
    body = <LoadingState />
  } else if (error) {
    if (!error.response) {
      body = <ErrorState onRetry={retry} />
    } else {
      body = (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm text-red-600">{errorMessageFor(error)}</p>
          <button
            type="button"
            onClick={retry}
            className="mt-4 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      )
    }
  } else if (data) {
    const {
      probability_delayed: probability,
      risk_category: riskCategory,
      sufficient_history: sufficientHistory,
      explanation,
      historical_stats: stats,
      training_data_source: trainingSource,
      synthetic_data_warning: syntheticWarning,
    } = data

    const category = riskPillClasses[riskCategory] ? riskCategory : 'Unknown'
    const hasProbability = typeof probability === 'number'
    const percent = hasProbability ? probability * 100 : null

    let probabilityText = null
    if (!hasProbability) {
      probabilityText = sufficientHistory === false
        ? 'Insufficient payment history'
        : 'No prediction available'
    }

    const notices = []
    if (trainingSource === 'synthetic') {
      notices.push(
        'Model trained on synthetic demonstration data. It has not been validated against real payment outcomes.',
      )
    } else if (trainingSource) {
      notices.push(`Training data: ${trainingSource}`)
    }
    if (typeof syntheticWarning === 'string' && syntheticWarning.trim() !== '') {
      notices.push(syntheticWarning)
    }

    body = (
      <div className="space-y-5">
        <div className="flex items-center justify-between gap-3">
          <span
            className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${riskPillClasses[category]}`}
          >
            {riskCategory}
          </span>
        </div>

        <div>
          {hasProbability ? (
            <>
              <div className="flex items-baseline justify-between">
                <p className="text-sm font-medium text-gray-500">
                  Probability of delayed payment
                </p>
                <p className="text-2xl font-bold text-gray-900">
                  {percent.toFixed(1)}%
                </p>
              </div>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-gray-200">
                <div
                  className={`h-2 rounded-full ${barClasses[category]}`}
                  style={{ width: `${Math.min(Math.max(percent, 0), 100)}%` }}
                />
              </div>
            </>
          ) : (
            <p className="text-sm font-medium text-gray-600">{probabilityText}</p>
          )}
        </div>

        {stats && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <StatItem label="Prior paid invoices" value={stats.prior_invoice_count} />
            <StatItem label="Previous late payments" value={stats.prior_late_count} />
            <StatItem label="Late payment rate" value={`${stats.prior_late_pct}%`} />
            <StatItem label="Average delay" value={`${stats.avg_delay_days} days`} />
            <StatItem label="Max delay" value={`${stats.max_delay_days} days`} />
            <StatItem
              label="Average invoice"
              value={
                typeof stats.avg_prior_amount === 'number'
                  ? inrFormatter.format(stats.avg_prior_amount)
                  : '—'
              }
            />
          </div>
        )}

        {explanation && (
          <p className="text-sm text-gray-700">{explanation}</p>
        )}

        {notices.map((text) => (
          <div
            key={text}
            className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
          >
            {text}
          </div>
        ))}
      </div>
    )
  } else {
    body = null
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      {header}
      <div className="mt-4">{body}</div>
    </div>
  )
}
