import { useEffect } from 'react'

const STATUS_CLASSES = {
  paid: 'bg-green-100 text-green-800',
  pending: 'bg-amber-100 text-amber-800',
  overdue: 'bg-red-100 text-red-800',
}

const currencyFormatter = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' })

function DetailRow({ label, children }) {
  return (
    <div>
      <dt className="text-sm font-medium text-gray-500">{label}</dt>
      <dd className="mt-1 text-sm text-gray-900">{children}</dd>
    </div>
  )
}

export default function InvoiceDetailModal({
  open,
  invoice,
  onClose,
  onEdit,
  onMarkPaid,
  onDelete,
}) {
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

  if (!open || !invoice) return null

  function handleBackdropClick(event) {
    if (event.target === event.currentTarget) {
      onClose?.()
    }
  }

  const status = String(invoice.status ?? '').toLowerCase()
  const statusClass = STATUS_CLASSES[status] ?? 'bg-gray-100 text-gray-800'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={handleBackdropClick}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="invoice-detail-title"
        className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-xl border border-gray-200 bg-white p-6 text-gray-900 shadow-lg"
      >
        <div className="flex items-start justify-between gap-4">
          <h2 id="invoice-detail-title" className="text-lg font-semibold text-gray-900">
            {invoice.invoice_number}
          </h2>
          <span
            className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${statusClass}`}
          >
            {invoice.status}
          </span>
        </div>

        <dl className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <DetailRow label="Client">{invoice.client?.name || '-'}</DetailRow>
          <DetailRow label="Company">{invoice.client?.company || '-'}</DetailRow>
          <DetailRow label="Client email">{invoice.client?.email || '-'}</DetailRow>
          <DetailRow label="Amount">
            {currencyFormatter.format(Number(invoice.amount))}
          </DetailRow>
          <div className="sm:col-span-2">
            <DetailRow label="Description">{invoice.description || '-'}</DetailRow>
          </div>
          <DetailRow label="Issue date">{invoice.issue_date}</DetailRow>
          <DetailRow label="Due date">{invoice.due_date}</DetailRow>
          <DetailRow label="Payment date">{invoice.paid_date || '—'}</DetailRow>
        </dl>

        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:flex-wrap sm:justify-end">
          <button
            type="button"
            onClick={() => onClose?.()}
            className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
          >
            Close
          </button>
          <button
            type="button"
            onClick={() => onDelete?.(invoice)}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Delete
          </button>
          <button
            type="button"
            onClick={() => onEdit?.(invoice)}
            className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
          >
            Edit
          </button>
          {status !== 'paid' && (
            <button
              type="button"
              onClick={() => onMarkPaid?.(invoice)}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Mark as paid
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
