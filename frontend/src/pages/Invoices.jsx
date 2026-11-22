
import { useCallback, useEffect, useRef, useState } from 'react'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import InvoiceFormModal from '../components/InvoiceFormModal'
import InvoiceDetailModal from '../components/InvoiceDetailModal'
import MarkPaidDialog from '../components/MarkPaidDialog'
import ConfirmDialog from '../components/ConfirmDialog'
import {
  getInvoices,
  getClients,
  markInvoicePaid,
  deleteInvoice,
} from '../services/api'

const LOAD_ERROR = 'Unable to load invoices. Check backend connection.'
const REFRESH_ERROR = 'Unable to refresh invoices. Check backend connection.'
const CLIENTS_ERROR = 'Unable to load clients. Creating invoices may not work.'
const CONNECTION_MESSAGE = 'Could not reach the API. Check that the backend is running.'
const GENERIC_MESSAGE = 'Something went wrong. Try again.'
const NOTICE_MS = 4000

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'paid', label: 'Paid' },
  { key: 'pending', label: 'Pending' },
  { key: 'overdue', label: 'Overdue' },
]

const STATUS_CLASSES = {
  paid: 'bg-green-100 text-green-800',
  pending: 'bg-amber-100 text-amber-800',
  overdue: 'bg-red-100 text-red-800',
}

const moneyFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
})

function money(value) {
  return moneyFormatter.format(value)
}

function statusOf(invoice) {
  return String(invoice.status ?? '').toLowerCase()
}

function statusLabel(status) {
  return status.charAt(0).toUpperCase() + status.slice(1)
}

// The API returns oldest first, so sort newest first here.
function sortNewestFirst(list) {
  return [...list].sort((a, b) => {
    const byDate = String(b.issue_date ?? '').localeCompare(String(a.issue_date ?? ''))
    return byDate !== 0 ? byDate : b.id - a.id
  })
}

// Totals and per-status counts, computed only from the fetched invoices.
function buildSummary(list) {
  const summary = {
    total: list.length,
    invoiced: 0,
    counts: { all: list.length, paid: 0, pending: 0, overdue: 0 },
    sums: { paid: 0, pending: 0, overdue: 0 },
  }
  for (const invoice of list) {
    const amount = Number(invoice.amount)
    const status = statusOf(invoice)
    summary.invoiced += amount
    if (status in summary.sums) {
      summary.sums[status] += amount
      summary.counts[status] += 1
    }
  }
  return summary
}

// Use the server's detail text when it is a plain string, otherwise a fallback.
function detailFromError(err, fallback) {
  const detail = err.response?.data?.detail
  return typeof detail === 'string' && detail ? detail : fallback
}

function SummaryCard({ label, value, tone = 'text-gray-900' }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`mt-1 text-xl font-semibold ${tone}`}>{value}</p>
    </div>
  )
}

function StatusPill({ status }) {
  const classes = STATUS_CLASSES[status] ?? 'bg-gray-100 text-gray-800'
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${classes}`}>
      {statusLabel(status)}
    </span>
  )
}

function FilterTabs({ value, counts, onChange }) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Filter invoices by status">
      {FILTERS.map((filter) => {
        const active = value === filter.key
        return (
          <button
            key={filter.key}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(filter.key)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
              active
                ? 'bg-indigo-600 text-white'
                : 'border border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            {filter.label} ({counts[filter.key]})
          </button>
        )
      })}
    </div>
  )
}

function InvoiceTable({ invoices, onRowClick, onEdit, onMarkPaid, onDelete }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-500">Invoice number</th>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-500">Client</th>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-500">Description</th>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-500">Amount</th>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-500">Issue date</th>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-500">Due date</th>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-500">Status</th>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-right font-medium text-gray-500">Actions</th>
          </tr>
        </thead>

        <tbody className="divide-y divide-gray-100">
          {invoices.map((invoice) => {
            const status = statusOf(invoice)
            return (
              <tr
                key={invoice.id}
                onClick={() => onRowClick(invoice)}
                className="cursor-pointer hover:bg-indigo-50"
              >
                <td className="whitespace-nowrap px-4 py-3 font-medium text-gray-900">
                  {invoice.invoice_number}
                </td>
                <td className="px-4 py-3 text-gray-700">{invoice.client?.name || '-'}</td>
                <td className="max-w-xs truncate px-4 py-3 text-gray-700">
                  {invoice.description || '-'}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-gray-900">
                  {money(Number(invoice.amount))}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-gray-700">{invoice.issue_date}</td>
                <td className="whitespace-nowrap px-4 py-3 text-gray-700">{invoice.due_date}</td>
                <td className="whitespace-nowrap px-4 py-3">
                  <StatusPill status={status} />
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation()
                      onEdit(invoice)
                    }}
                    className="rounded-md px-2 py-1 text-sm font-medium text-indigo-600 hover:bg-indigo-50"
                  >
                    Edit
                  </button>
                  {status !== 'paid' && (
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation()
                        onMarkPaid(invoice)
                      }}
                      className="ml-2 rounded-md px-2 py-1 text-sm font-medium text-green-700 hover:bg-green-50"
                    >
                      Mark as paid
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation()
                      onDelete(invoice)
                    }}
                    className="ml-2 rounded-md px-2 py-1 text-sm font-medium text-red-600 hover:bg-red-50"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function Invoices() {
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [clients, setClients] = useState([])
  const [clientsError, setClientsError] = useState('')
  const [filter, setFilter] = useState('all')

  const [notice, setNotice] = useState('')
  const [actionError, setActionError] = useState('')
  const noticeTimer = useRef(null)

  const [detailId, setDetailId] = useState(null)

  const [formOpen, setFormOpen] = useState(false)
  const [editingInvoice, setEditingInvoice] = useState(null)

  const [markPaidTarget, setMarkPaidTarget] = useState(null)
  const [markPaidBusy, setMarkPaidBusy] = useState(false)
  const [markPaidError, setMarkPaidError] = useState('')

  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  const loadInvoices = useCallback(async (failMessage = LOAD_ERROR) => {
    try {
      const response = await getInvoices()
      setInvoices(response.data)
      setLoadError('')
    } catch (err) {
      setLoadError(failMessage)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadInvoices()
  }, [loadInvoices])

  // Clients are only needed for the client dropdown in the invoice form.
  useEffect(() => {
    async function loadClients() {
      try {
        const response = await getClients()
        setClients(response.data)
        setClientsError('')
      } catch (err) {
        setClientsError(CLIENTS_ERROR)
      }
    }
    loadClients()
  }, [])

  // Clear any pending notice timer when the page unmounts.
  useEffect(() => {
    return () => clearTimeout(noticeTimer.current)
  }, [])

  function showNotice(message) {
    clearTimeout(noticeTimer.current)
    setActionError('')
    setNotice(message)
    noticeTimer.current = setTimeout(() => setNotice(''), NOTICE_MS)
  }

  function retryLoad() {
    setLoading(true)
    loadInvoices()
  }

  // The detail modal reads the invoice from the list, so it always shows fresh data.
  const detailInvoice = invoices.find((invoice) => invoice.id === detailId) || null

  // Escape and backdrop clicks should not close the detail modal behind an open dialog.
  function closeDetail() {
    if (markPaidTarget || deleteTarget) return
    setDetailId(null)
  }

  function openRowDetail(invoice) {
    setDetailId(invoice.id)
  }

  // Create and edit flow
  function openCreateForm() {
    setEditingInvoice(null)
    setFormOpen(true)
  }

  function openEditForm(invoice) {
    setEditingInvoice(invoice)
    setFormOpen(true)
  }

  function closeForm() {
    setFormOpen(false)
  }

  function handleDetailEdit(invoice) {
    setDetailId(null)
    openEditForm(invoice)
  }

  function handleSaved() {
    const wasEdit = Boolean(editingInvoice)
    setFormOpen(false)
    showNotice(wasEdit ? 'Invoice updated.' : 'Invoice created.')
    loadInvoices(REFRESH_ERROR)
  }

  // Mark as paid flow
  function openMarkPaid(invoice) {
    setMarkPaidError('')
    setMarkPaidTarget(invoice)
  }

  function closeMarkPaid() {
    if (markPaidBusy) return
    setMarkPaidTarget(null)
    setMarkPaidError('')
  }

  async function handleConfirmMarkPaid(paidDate) {
    const target = markPaidTarget
    if (!target) return
    setMarkPaidBusy(true)
    setMarkPaidError('')
    try {
      await markInvoicePaid(target.id, paidDate)
      setMarkPaidTarget(null)
      setDetailId((prev) => (prev === target.id ? null : prev))
      showNotice('Invoice marked as paid.')
      await loadInvoices(REFRESH_ERROR)
    } catch (err) {
      if (!err.response) {
        setMarkPaidError(CONNECTION_MESSAGE)
      } else if (err.response.status === 409) {
        setMarkPaidTarget(null)
        setActionError('This invoice is already paid.')
        await loadInvoices(REFRESH_ERROR)
      } else {
        setMarkPaidError(detailFromError(err, GENERIC_MESSAGE))
      }
    } finally {
      setMarkPaidBusy(false)
    }
  }

  // Delete flow
  function openDelete(invoice) {
    setDeleteError('')
    setDeleteTarget(invoice)
  }

  function closeDelete() {
    if (deleteBusy) return
    setDeleteTarget(null)
    setDeleteError('')
  }

  async function handleConfirmDelete() {
    const target = deleteTarget
    if (!target) return
    setDeleteBusy(true)
    setDeleteError('')
    try {
      await deleteInvoice(target.id)
      setDeleteTarget(null)
      setDetailId((prev) => (prev === target.id ? null : prev))
      showNotice('Invoice deleted.')
      await loadInvoices(REFRESH_ERROR)
    } catch (err) {
      if (!err.response) {
        setDeleteError(CONNECTION_MESSAGE)
      } else if (err.response.status === 404) {
        setDeleteTarget(null)
        setDetailId((prev) => (prev === target.id ? null : prev))
        setActionError('This invoice no longer exists.')
        await loadInvoices(REFRESH_ERROR)
      } else {
        setDeleteError(detailFromError(err, GENERIC_MESSAGE))
      }
    } finally {
      setDeleteBusy(false)
    }
  }

  // Derived data for the page body
  const summary = buildSummary(invoices)
  const sorted = sortNewestFirst(invoices)
  const visible = filter === 'all' ? sorted : sorted.filter((invoice) => statusOf(invoice) === filter)

  let body
  if (loading) {
    body = <LoadingState />
  } else if (loadError && invoices.length === 0) {
    body = <ErrorState onRetry={retryLoad} />
  } else if (invoices.length === 0) {
    body = (
      <EmptyState
        title="No invoices yet"
        message="Create your first invoice to start tracking payments."
      />
    )
  } else {
    body = (
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <SummaryCard label="Total invoices" value={String(summary.total)} />
          <SummaryCard label="Total invoiced" value={money(summary.invoiced)} />
          <SummaryCard label="Paid" value={money(summary.sums.paid)} tone="text-green-600" />
          <SummaryCard label="Pending" value={money(summary.sums.pending)} tone="text-amber-600" />
          <SummaryCard label="Overdue" value={money(summary.sums.overdue)} tone="text-red-600" />
        </div>

        <FilterTabs value={filter} counts={summary.counts} onChange={setFilter} />

        {visible.length === 0 ? (
          <p className="rounded-xl border border-gray-200 bg-white px-4 py-8 text-center text-sm text-gray-500">
            No {filter} invoices.
          </p>
        ) : (
          <InvoiceTable
            invoices={visible}
            onRowClick={openRowDetail}
            onEdit={openEditForm}
            onMarkPaid={openMarkPaid}
            onDelete={openDelete}
          />
        )}
      </div>
    )
  }

  return (
    <div>
      <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-start sm:justify-between">

        <button
          type="button"
          onClick={openCreateForm}
          className="inline-flex shrink-0 items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          + Create Invoice
        </button>
      </div>

      <div className="px-6 pb-6">
        {notice && (
          <p className="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-2 text-sm text-green-700">
            {notice}
          </p>
        )}

        {loadError && invoices.length > 0 && (
          <p role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">
            {loadError}
          </p>
        )}

        {actionError && (
          <p role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">
            {actionError}
          </p>
        )}

        {clientsError && (
          <p className="mb-4 text-sm text-red-600">{clientsError}</p>
        )}

        {body}
      </div>

      <InvoiceFormModal
        open={formOpen}
        invoice={editingInvoice}
        clients={clients}
        onClose={closeForm}
        onSaved={handleSaved}
      />

      <InvoiceDetailModal
        open={Boolean(detailInvoice)}
        invoice={detailInvoice}
        onClose={closeDetail}
        onEdit={handleDetailEdit}
        onMarkPaid={openMarkPaid}
        onDelete={openDelete}
      />

      <MarkPaidDialog
        open={Boolean(markPaidTarget)}
        invoice={markPaidTarget}
        onConfirm={handleConfirmMarkPaid}
        onCancel={closeMarkPaid}
        busy={markPaidBusy}
        error={markPaidError}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete invoice?"
        message={deleteTarget ? `Delete invoice ${deleteTarget.invoice_number}? This cannot be undone.` : ''}
        confirmLabel="Delete"
        onConfirm={handleConfirmDelete}
        onCancel={closeDelete}
        busy={deleteBusy}
        error={deleteError}
      />
    </div>
  )
}
