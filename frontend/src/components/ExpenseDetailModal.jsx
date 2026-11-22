import { useEffect } from 'react'

const currencyFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
})

const PAYMENT_METHOD_LABELS = {
  cash: 'Cash',
  upi: 'UPI',
  card: 'Card',
  bank_transfer: 'Bank transfer',
  other: 'Other',
}

const STATUS_STYLES = {
  paid: 'bg-green-100 text-green-800',
  upcoming: 'bg-amber-100 text-amber-800',
}

function capitalise(text) {
  if (!text) return '-'
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function DetailRow({ label, children }) {
  return (
    <div>
      <dt className="text-sm font-medium text-gray-500">{label}</dt>
      <dd className="mt-1 whitespace-pre-wrap text-sm text-gray-900">{children}</dd>
    </div>
  )
}

export default function ExpenseDetailModal({ open, expense, onClose, onEdit, onDelete }) {
  // Escape closes the modal.
  useEffect(() => {
    if (!open) return undefined
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        onClose?.()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  if (!open || !expense) return null

  function handleBackdropClick(event) {
    if (event.target === event.currentTarget) {
      onClose?.()
    }
  }

  const statusClass = STATUS_STYLES[expense.status] ?? 'bg-gray-100 text-gray-800'
  const paymentLabel = expense.payment_method
    ? PAYMENT_METHOD_LABELS[expense.payment_method] ?? capitalise(expense.payment_method)
    : '-'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={handleBackdropClick}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="expense-detail-title"
        className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-xl border border-gray-200 bg-white p-6 text-gray-900 shadow-lg"
      >
        <div className="flex items-start justify-between gap-3">
          <h2 id="expense-detail-title" className="text-lg font-semibold text-gray-900">
            {expense.title}
          </h2>
          <span
            className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${statusClass}`}
          >
            {capitalise(expense.status)}
          </span>
        </div>

        <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <DetailRow label="Description">{expense.description || '-'}</DetailRow>
          <DetailRow label="Amount">
            {currencyFormatter.format(Number(expense.amount))}
          </DetailRow>
          <DetailRow label="Category">{expense.category || '-'}</DetailRow>
          <DetailRow label="Expense date">{expense.expense_date || '-'}</DetailRow>
          <DetailRow label="Payment method">{paymentLabel}</DetailRow>
          <DetailRow label="Status">{capitalise(expense.status)}</DetailRow>
          <DetailRow label="Notes">{expense.notes || '-'}</DetailRow>
        </dl>

        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-end">
          <button
            type="button"
            onClick={() => onDelete?.(expense)}
            className="rounded-lg px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 sm:mr-auto"
          >
            Delete
          </button>
          <button
            type="button"
            onClick={() => onClose?.()}
            className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
          >
            Close
          </button>
          <button
            type="button"
            onClick={() => onEdit?.(expense)}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Edit
          </button>
        </div>
      </div>
    </div>
  )
}
