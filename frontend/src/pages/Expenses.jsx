
import { useCallback, useEffect, useRef, useState } from 'react'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import ExpenseFormModal from '../components/ExpenseFormModal'
import ExpenseDetailModal from '../components/ExpenseDetailModal'
import ConfirmDialog from '../components/ConfirmDialog'
import { getExpenses, deleteExpense } from '../services/api'

const LOAD_ERROR = 'Unable to load expenses. Check backend connection.'
const REFRESH_ERROR = 'Unable to refresh expenses. Check backend connection.'
const CONNECTION_MESSAGE = 'Could not reach the API. Check that the backend is running.'
const GENERIC_MESSAGE = 'Something went wrong. Try again.'
const NOTICE_MS = 4000
const DATE_RANGE_MESSAGE = 'Start date cannot be after end date.'

const DEFAULT_CATEGORIES = [
  'Software & Subscriptions',
  'Internet & Utilities',
  'Equipment',
  'Travel',
  'Marketing',
  'Office Supplies',
  'Professional Services',
  'Other',
]

const STATUS_OPTIONS = [
  { value: 'paid', label: 'Paid' },
  { value: 'upcoming', label: 'Upcoming' },
]

const PAYMENT_METHOD_LABELS = {
  cash: 'Cash',
  upi: 'UPI',
  card: 'Card',
  bank_transfer: 'Bank transfer',
  other: 'Other',
}

const STATUS_CLASSES = {
  paid: 'bg-green-100 text-green-800',
  upcoming: 'bg-amber-100 text-amber-800',
}

const EMPTY_FILTERS = {
  search: '',
  status: '',
  category: '',
  dateFrom: '',
  dateTo: '',
}

const inputClass =
  'rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500'

const moneyFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
})

function money(value) {
  return moneyFormatter.format(value)
}

function statusOf(expense) {
  return String(expense.status ?? '').toLowerCase()
}

function capitalise(text) {
  if (!text) return '-'
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function paymentMethodLabel(method) {
  if (!method) return '-'
  return PAYMENT_METHOD_LABELS[method] ?? capitalise(method)
}

// The API returns oldest first, so sort newest first here (date, then id).
function sortNewestFirst(list) {
  return [...list].sort((a, b) => {
    const byDate = String(b.expense_date ?? '').localeCompare(String(a.expense_date ?? ''))
    return byDate !== 0 ? byDate : b.id - a.id
  })
}

// Default categories plus any category already used, sorted, with Other last.
function buildCategories(list) {
  const names = new Set(DEFAULT_CATEGORIES)
  for (const expense of list) {
    const name = String(expense.category ?? '').trim()
    if (name) names.add(name)
  }
  const sorted = [...names]
    .filter((name) => name !== 'Other')
    .sort((a, b) => a.localeCompare(b))
  return [...sorted, 'Other']
}

// Totals computed only from the fetched expenses, never from the filtered table.
function buildSummary(list) {
  const summary = { total: 0, paid: 0, upcoming: 0, count: list.length }
  for (const expense of list) {
    const amount = Number(expense.amount) || 0
    const status = statusOf(expense)
    summary.total += amount
    if (status === 'paid') summary.paid += amount
    else if (status === 'upcoming') summary.upcoming += amount
  }
  return summary
}

function isDateRangeInvalid(filters) {
  return Boolean(filters.dateFrom && filters.dateTo && filters.dateFrom > filters.dateTo)
}

function hasActiveFilters(filters) {
  return Boolean(
    filters.search.trim() || filters.status || filters.category || filters.dateFrom || filters.dateTo
  )
}

// Client-side filtering. The date range is skipped while it is invalid.
function applyFilters(list, filters) {
  const needle = filters.search.trim().toLowerCase()
  const useDateRange = !isDateRangeInvalid(filters)
  return list.filter((expense) => {
    if (needle) {
      const title = String(expense.title ?? '').toLowerCase()
      const description = String(expense.description ?? '').toLowerCase()
      if (!title.includes(needle) && !description.includes(needle)) return false
    }
    if (filters.status && statusOf(expense) !== filters.status) return false
    if (filters.category && expense.category !== filters.category) return false
    if (useDateRange) {
      const date = String(expense.expense_date ?? '')
      if (filters.dateFrom && date < filters.dateFrom) return false
      if (filters.dateTo && date > filters.dateTo) return false
    }
    return true
  })
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
      {capitalise(status)}
    </span>
  )
}

function FilterField({ id, label, children }) {
  return (
    <div className="flex w-full flex-col gap-1 sm:w-auto">
      <label htmlFor={id} className="text-sm font-medium text-gray-700">
        {label}
      </label>
      {children}
    </div>
  )
}

function ExpenseTable({ expenses, onRowClick, onEdit, onDelete }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-500">Title</th>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-500">Category</th>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-500">Amount (INR)</th>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-500">Expense date</th>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-500">Payment method</th>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-left font-medium text-gray-500">Status</th>
            <th scope="col" className="whitespace-nowrap px-4 py-3 text-right font-medium text-gray-500">Actions</th>
          </tr>
        </thead>

        <tbody className="divide-y divide-gray-100">
          {expenses.map((expense) => (
            <tr
              key={expense.id}
              onClick={() => onRowClick(expense)}
              className="cursor-pointer hover:bg-indigo-50"
            >
              <td className="px-4 py-3 text-gray-900">
                <p className="font-medium">{expense.title}</p>
                {expense.description && (
                  <p className="mt-0.5 max-w-xs truncate text-gray-500">{expense.description}</p>
                )}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-gray-700">{expense.category || '-'}</td>
              <td className="whitespace-nowrap px-4 py-3 text-gray-900">
                {money(Number(expense.amount) || 0)}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-gray-700">{expense.expense_date}</td>
              <td className="whitespace-nowrap px-4 py-3 text-gray-700">
                {paymentMethodLabel(expense.payment_method)}
              </td>
              <td className="whitespace-nowrap px-4 py-3">
                <StatusPill status={statusOf(expense)} />
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-right">
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation()
                    onEdit(expense)
                  }}
                  className="rounded-md px-2 py-1 text-sm font-medium text-indigo-600 hover:bg-indigo-50"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation()
                    onDelete(expense)
                  }}
                  className="ml-2 rounded-md px-2 py-1 text-sm font-medium text-red-600 hover:bg-red-50"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Expenses() {
  const [expenses, setExpenses] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [filters, setFilters] = useState(EMPTY_FILTERS)

  const [notice, setNotice] = useState('')
  const [actionError, setActionError] = useState('')
  const noticeTimer = useRef(null)

  const [detailExpense, setDetailExpense] = useState(null)

  const [formOpen, setFormOpen] = useState(false)
  const [editingExpense, setEditingExpense] = useState(null)

  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  const loadExpenses = useCallback(async (failMessage = LOAD_ERROR) => {
    try {
      const response = await getExpenses()
      const list = response.data
      setExpenses(list)
      setLoadError('')
      // Keep the detail modal in sync with the fresh list; close it if the expense is gone.
      setDetailExpense((prev) => (prev ? list.find((item) => item.id === prev.id) ?? null : null))
    } catch (err) {
      setLoadError(failMessage)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadExpenses()
  }, [loadExpenses])

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
    loadExpenses()
  }

  function updateFilter(key, value) {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  function clearFilters() {
    setFilters(EMPTY_FILTERS)
  }

  // Escape and backdrop clicks should not close the detail modal behind an open dialog.
  function closeDetail() {
    if (deleteTarget) return
    setDetailExpense(null)
  }

  function openRowDetail(expense) {
    setDetailExpense(expense)
  }

  // Create and edit flow
  function openCreateForm() {
    setEditingExpense(null)
    setFormOpen(true)
  }

  function openEditForm(expense) {
    setEditingExpense(expense)
    setFormOpen(true)
  }

  function closeForm() {
    setFormOpen(false)
  }

  function handleDetailEdit(expense) {
    setDetailExpense(null)
    openEditForm(expense)
  }

  function handleSaved(saved) {
    const wasEdit = Boolean(editingExpense)
    setFormOpen(false)
    // If the detail modal shows this expense, pass the saved version back into it.
    setDetailExpense((prev) => (prev && saved && prev.id === saved.id ? saved : prev))
    showNotice(wasEdit ? 'Expense updated.' : 'Expense added.')
    loadExpenses(REFRESH_ERROR)
  }

  // Delete flow
  function openDelete(expense) {
    setDeleteError('')
    setDeleteTarget(expense)
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
      await deleteExpense(target.id)
      setDeleteTarget(null)
      setDetailExpense((prev) => (prev?.id === target.id ? null : prev))
      showNotice('Expense deleted.')
      await loadExpenses(REFRESH_ERROR)
    } catch (err) {
      if (!err.response) {
        setDeleteError(CONNECTION_MESSAGE)
      } else if (err.response.status === 404) {
        setDeleteTarget(null)
        setDetailExpense((prev) => (prev?.id === target.id ? null : prev))
        setActionError('This expense no longer exists.')
        await loadExpenses(REFRESH_ERROR)
      } else {
        setDeleteError(detailFromError(err, GENERIC_MESSAGE))
      }
    } finally {
      setDeleteBusy(false)
    }
  }

  // Derived data for the page body
  const summary = buildSummary(expenses)
  const categories = buildCategories(expenses)
  const sorted = sortNewestFirst(expenses)
  const visible = applyFilters(sorted, filters)
  const dateRangeInvalid = isDateRangeInvalid(filters)
  const filtersActive = hasActiveFilters(filters)

  let body
  if (loading) {
    body = <LoadingState />
  } else if (loadError && expenses.length === 0) {
    body = <ErrorState onRetry={retryLoad} />
  } else if (expenses.length === 0) {
    body = (
      <EmptyState
        title="No expenses yet"
        message="Add your first expense to track your spending."
      />
    )
  } else {
    body = (
      <div className="space-y-6">
        <div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <SummaryCard label="Total expenses" value={money(summary.total)} />
            <SummaryCard label="Paid expenses" value={money(summary.paid)} tone="text-green-600" />
            <SummaryCard label="Upcoming expenses" value={money(summary.upcoming)} tone="text-amber-600" />
            <SummaryCard label="Number of records" value={String(summary.count)} />
          </div>
          <p className="mt-2 text-xs text-gray-500">
            Summary cards include all expenses. Filters only affect the table below.
          </p>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="flex flex-wrap items-end gap-3">
            <FilterField id="expense-filter-search" label="Search">
              <input
                id="expense-filter-search"
                type="search"
                placeholder="Search title or description"
                value={filters.search}
                onChange={(event) => updateFilter('search', event.target.value)}
                className={`${inputClass} w-full sm:w-64`}
              />
            </FilterField>

            <FilterField id="expense-filter-status" label="Status">
              <select
                id="expense-filter-status"
                value={filters.status}
                onChange={(event) => updateFilter('status', event.target.value)}
                className={`${inputClass} w-full sm:w-40`}
              >
                <option value="">All statuses</option>
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </FilterField>

            <FilterField id="expense-filter-category" label="Category">
              <select
                id="expense-filter-category"
                value={filters.category}
                onChange={(event) => updateFilter('category', event.target.value)}
                className={`${inputClass} w-full sm:w-56`}
              >
                <option value="">All categories</option>
                {categories.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </FilterField>

            <FilterField id="expense-filter-from" label="Date from">
              <input
                id="expense-filter-from"
                type="date"
                value={filters.dateFrom}
                onChange={(event) => updateFilter('dateFrom', event.target.value)}
                className={`${inputClass} w-full sm:w-auto`}
              />
            </FilterField>

            <FilterField id="expense-filter-to" label="Date to">
              <input
                id="expense-filter-to"
                type="date"
                value={filters.dateTo}
                onChange={(event) => updateFilter('dateTo', event.target.value)}
                className={`${inputClass} w-full sm:w-auto`}
              />
            </FilterField>

            <button
              type="button"
              onClick={clearFilters}
              disabled={!filtersActive}
              className="rounded-lg px-3 py-2 text-sm font-medium text-indigo-600 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:text-gray-400 disabled:hover:bg-transparent"
            >
              Clear filters
            </button>
          </div>

          {dateRangeInvalid && (
            <p role="alert" className="mt-3 text-sm text-red-600">
              {DATE_RANGE_MESSAGE}
            </p>
          )}
        </div>

        {visible.length === 0 ? (
          <div className="rounded-xl border border-gray-200 bg-white px-4 py-8 text-center">
            <p className="text-sm text-gray-500">No expenses match these filters.</p>
            <button
              type="button"
              onClick={clearFilters}
              className="mt-3 rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
            >
              Clear filters
            </button>
          </div>
        ) : (
          <ExpenseTable
            expenses={visible}
            onRowClick={openRowDetail}
            onEdit={openEditForm}
            onDelete={openDelete}
          />
        )}
      </div>
    )
  }

  return (
    <div>
      <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader title="Expenses" subtitle="Track and manage your business spending." />
        <button
          type="button"
          onClick={openCreateForm}
          className="inline-flex shrink-0 items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          + Add Expense
        </button>
      </div>

      <div className="px-6 pb-6">
        {notice && (
          <p className="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-2 text-sm text-green-700">
            {notice}
          </p>
        )}

        {loadError && expenses.length > 0 && (
          <p role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">
            {loadError}
          </p>
        )}

        {actionError && (
          <p role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">
            {actionError}
          </p>
        )}

        {body}
      </div>

      <ExpenseFormModal
        open={formOpen}
        expense={editingExpense}
        categories={categories}
        onClose={closeForm}
        onSaved={handleSaved}
      />

      <ExpenseDetailModal
        open={Boolean(detailExpense)}
        expense={detailExpense}
        onClose={closeDetail}
        onEdit={handleDetailEdit}
        onDelete={openDelete}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete expense?"
        message={deleteTarget ? `Delete ${deleteTarget.title}? This cannot be undone.` : ''}
        confirmLabel="Delete"
        onConfirm={handleConfirmDelete}
        onCancel={closeDelete}
        busy={deleteBusy}
        error={deleteError}
      />
    </div>
  )
}
