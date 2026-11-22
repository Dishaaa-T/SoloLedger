import { useEffect, useState } from 'react'

function todayLocal() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export default function MarkPaidDialog({
  open,
  invoice,
  onConfirm,
  onCancel,
  busy = false,
  error = '',
}) {
  const [paidDate, setPaidDate] = useState(todayLocal)
  const [dateError, setDateError] = useState('')

  // Reset the date each time the dialog opens.
  useEffect(() => {
    if (open) {
      setPaidDate(todayLocal())
      setDateError('')
    }
  }, [open, invoice])

  // Escape cancels, unless an action is already running.
  useEffect(() => {
    if (!open) return undefined
    function handleKeyDown(event) {
      if (event.key === 'Escape' && !busy) {
        onCancel?.()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, busy, onCancel])

  if (!open) return null

  function handleBackdropClick(event) {
    if (event.target === event.currentTarget && !busy) {
      onCancel?.()
    }
  }

  function handleConfirm() {
    if (busy) return
    const today = todayLocal()
    if (!paidDate) {
      setDateError('Payment date is required.')
      return
    }
    if (invoice?.issue_date && paidDate < invoice.issue_date) {
      setDateError('Payment date cannot be earlier than issue date.')
      return
    }
    if (paidDate > today) {
      setDateError('Payment date cannot be in the future.')
      return
    }
    setDateError('')
    onConfirm?.(paidDate)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={handleBackdropClick}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="mark-paid-title"
        aria-describedby="mark-paid-message"
        className="w-full max-w-md rounded-xl border border-gray-200 bg-white p-6 text-gray-900 shadow-lg"
      >
        <h2 id="mark-paid-title" className="text-lg font-semibold text-gray-900">
          Mark as paid
        </h2>
        <p id="mark-paid-message" className="mt-2 text-sm text-gray-700">
          Enter the date the client actually paid invoice {invoice?.invoice_number}.
        </p>

        <div className="mt-4">
          <label htmlFor="mark-paid-date" className="block text-sm font-medium text-gray-700">
            Payment date <span className="text-red-600">*</span>
          </label>
          <input
            id="mark-paid-date"
            type="date"
            value={paidDate}
            onChange={(event) => {
              setPaidDate(event.target.value)
              if (dateError) setDateError('')
            }}
            disabled={busy}
            aria-invalid={Boolean(dateError)}
            className={`mt-1 block w-full rounded-lg border px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-indigo-500 ${
              dateError ? 'border-red-400 focus:border-red-500' : 'border-gray-300 focus:border-indigo-500'
            }`}
          />
          {dateError && <p className="mt-1 text-sm text-red-600">{dateError}</p>}
        </div>

        {error && (
          <p role="alert" className="mt-3 text-sm text-red-600">
            {error}
          </p>
        )}

        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={() => onCancel?.()}
            disabled={busy}
            className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={busy}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy ? 'Saving…' : 'Confirm payment'}
          </button>
        </div>
      </div>
    </div>
  )
}
