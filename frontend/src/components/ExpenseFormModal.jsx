import { useEffect, useState } from 'react'
import { addExpense, updateExpense } from '../services/api'

const CONNECTION_MESSAGE = 'Could not reach the API. Check that the backend is running.'
const GENERIC_MESSAGE = 'Something went wrong. Try again.'
const MAX_AMOUNT = 10000000

const PAYMENT_METHODS = [
  { value: 'cash', label: 'Cash' },
  { value: 'upi', label: 'UPI' },
  { value: 'card', label: 'Card' },
  { value: 'bank_transfer', label: 'Bank transfer' },
  { value: 'other', label: 'Other' },
]

const STATUS_OPTIONS = [
  { value: 'paid', label: 'Paid' },
  { value: 'upcoming', label: 'Upcoming' },
]

const inputClass =
  'mt-1 block w-full rounded-lg border px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-indigo-500'
const inputOk = 'border-gray-300 focus:border-indigo-500'
const inputBad = 'border-red-400 focus:border-red-500'

function todayLocal() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function buildEmptyForm() {
  return {
    title: '',
    description: '',
    amount: '',
    category: '',
    expense_date: todayLocal(),
    payment_method: '',
    status: '',
    notes: '',
  }
}

function formFromExpense(expense) {
  return {
    title: expense.title ?? '',
    description: expense.description ?? '',
    amount: Number(expense.amount),
    category: expense.category ?? '',
    expense_date: expense.expense_date ?? '',
    payment_method: expense.payment_method ?? '',
    status: expense.status ?? '',
    notes: expense.notes ?? '',
  }
}

function hasMoreThanTwoDecimals(value) {
  const text = String(value).trim()
  const dot = text.indexOf('.')
  return dot !== -1 && text.length - dot - 1 > 2
}

function validate(form) {
  const errors = {}

  const title = form.title.trim()
  if (!title) {
    errors.title = 'Title is required.'
  } else if (title.length > 120) {
    errors.title = 'Title must be 120 characters or fewer.'
  }

  if (form.description.trim().length > 2000) {
    errors.description = 'Description must be 2000 characters or fewer.'
  }

  const amountText = String(form.amount).trim()
  const amount = Number(amountText)
  if (amountText === '') {
    errors.amount = 'Amount is required.'
  } else if (!Number.isFinite(amount) || amount <= 0) {
    errors.amount = 'Amount must be a number greater than 0.'
  } else if (hasMoreThanTwoDecimals(amountText)) {
    errors.amount = 'Amount can have at most 2 decimal places.'
  } else if (amount > MAX_AMOUNT) {
    errors.amount = 'Amount must be 10000000 or less.'
  }

  const category = form.category.trim()
  if (!category) {
    errors.category = 'Category is required.'
  } else if (category.length > 60) {
    errors.category = 'Category must be 60 characters or fewer.'
  }

  if (!form.expense_date) {
    errors.expense_date = 'Expense date is required.'
  }

  if (form.notes.trim().length > 1000) {
    errors.notes = 'Notes must be 1000 characters or fewer.'
  }
  return errors
}

function buildPayload(form, isEdit) {
  const optional = (value) => {
    const trimmed = value.trim()
    return trimmed === '' ? null : trimmed
  }
  const payload = {
    title: form.title.trim(),
    description: optional(form.description),
    amount: Number(String(form.amount).trim()),
    category: form.category.trim(),
    expense_date: form.expense_date,
    payment_method: form.payment_method || null,
    notes: optional(form.notes),
  }
  if (form.status) {
    payload.status = form.status
  } else if (!isEdit) {
    payload.status = null
  }
  // In edit mode an empty status is omitted entirely: the update endpoint rejects null.
  return payload
}

function describeError(err) {
  if (!err.response) {
    return { form: CONNECTION_MESSAGE }
  }
  const { status, data } = err.response
  const detail = data?.detail

  if (status === 422) {
    if (Array.isArray(detail)) {
      const messages = detail.map((item) => item?.msg).filter(Boolean)
      return { form: messages.length ? messages.join(' ') : GENERIC_MESSAGE }
    }
    return { form: typeof detail === 'string' ? detail : GENERIC_MESSAGE }
  }

  if (status === 404) {
    return { form: typeof detail === 'string' ? detail : 'Expense not found.' }
  }

  return { form: typeof detail === 'string' ? detail : GENERIC_MESSAGE }
}

export default function ExpenseFormModal({
  open,
  expense,
  categories = [],
  onClose,
  onSaved,
}) {
  const [form, setForm] = useState(buildEmptyForm)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  const isEdit = Boolean(expense)

  const categoryOptions = [...categories]
  if (!categoryOptions.includes('Other')) {
    categoryOptions.push('Other')
  }

  // Reset the form each time the modal opens or the target expense changes.
  useEffect(() => {
    if (open) {
      const base = expense ? formFromExpense(expense) : buildEmptyForm()
      if (!expense) {
        base.category = categoryOptions.includes('Other') ? 'Other' : ''
      }
      setForm(base)
      setErrors({})
      setSaving(false)
    }
    // categoryOptions is derived from props; expense and open drive the reset.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, expense])

  // Escape closes the modal, unless a save is in progress.
  useEffect(() => {
    if (!open) return undefined
    function handleKeyDown(event) {
      if (event.key === 'Escape' && !saving) {
        onClose?.()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, saving, onClose])

  if (!open) return null

  function handleChange(event) {
    const { name, value } = event.target
    setForm((prev) => ({ ...prev, [name]: value }))
    if (errors[name] || errors.form) {
      setErrors((prev) => ({ ...prev, [name]: undefined, form: undefined }))
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (saving) return

    const fieldErrors = validate(form)
    if (Object.keys(fieldErrors).length > 0) {
      setErrors(fieldErrors)
      return
    }

    const payload = buildPayload(form, isEdit)
    setSaving(true)
    setErrors({})
    try {
      const response = isEdit
        ? await updateExpense(expense.id, payload)
        : await addExpense(payload)
      onSaved?.(response.data)
      onClose?.()
    } catch (err) {
      setErrors(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  function handleBackdropClick(event) {
    if (event.target === event.currentTarget && !saving) {
      onClose?.()
    }
  }

  const title = isEdit ? 'Edit Expense' : 'Add Expense'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={handleBackdropClick}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="expense-form-title"
        className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-xl border border-gray-200 bg-white p-6 text-gray-900 shadow-lg"
      >
        <h2 id="expense-form-title" className="text-lg font-semibold text-gray-900">
          {title}
        </h2>

        <form onSubmit={handleSubmit} noValidate className="mt-4 space-y-4">
          {errors.form && (
            <p role="alert" className="text-sm text-red-600">
              {errors.form}
            </p>
          )}

          <div>
            <label htmlFor="expense-title" className="block text-sm font-medium text-gray-700">
              Title <span className="text-red-600">*</span>
            </label>
            <input
              id="expense-title"
              name="title"
              type="text"
              value={form.title}
              onChange={handleChange}
              className={`${inputClass} ${errors.title ? inputBad : inputOk}`}
              aria-invalid={Boolean(errors.title)}
            />
            {errors.title && <p className="mt-1 text-sm text-red-600">{errors.title}</p>}
          </div>

          <div>
            <label htmlFor="expense-description" className="block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              id="expense-description"
              name="description"
              rows={2}
              value={form.description}
              onChange={handleChange}
              className={`${inputClass} ${errors.description ? inputBad : inputOk}`}
              aria-invalid={Boolean(errors.description)}
            />
            {errors.description && (
              <p className="mt-1 text-sm text-red-600">{errors.description}</p>
            )}
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="expense-amount" className="block text-sm font-medium text-gray-700">
                Amount (INR) <span className="text-red-600">*</span>
              </label>
              <input
                id="expense-amount"
                name="amount"
                type="number"
                step="0.01"
                min="0.01"
                value={form.amount}
                onChange={handleChange}
                className={`${inputClass} ${errors.amount ? inputBad : inputOk}`}
                aria-invalid={Boolean(errors.amount)}
              />
              {errors.amount && <p className="mt-1 text-sm text-red-600">{errors.amount}</p>}
            </div>

            <div>
              <label htmlFor="expense-category" className="block text-sm font-medium text-gray-700">
                Category <span className="text-red-600">*</span>
              </label>
              <select
                id="expense-category"
                name="category"
                value={form.category}
                onChange={handleChange}
                className={`${inputClass} ${errors.category ? inputBad : inputOk}`}
                aria-invalid={Boolean(errors.category)}
              >
                {!categoryOptions.includes(form.category) && form.category && (
                  <option value={form.category}>{form.category}</option>
                )}
                {categoryOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
              {errors.category && <p className="mt-1 text-sm text-red-600">{errors.category}</p>}
            </div>

            <div>
              <label htmlFor="expense-date" className="block text-sm font-medium text-gray-700">
                Expense date <span className="text-red-600">*</span>
              </label>
              <input
                id="expense-date"
                name="expense_date"
                type="date"
                value={form.expense_date}
                onChange={handleChange}
                className={`${inputClass} ${errors.expense_date ? inputBad : inputOk}`}
                aria-invalid={Boolean(errors.expense_date)}
              />
              {errors.expense_date && (
                <p className="mt-1 text-sm text-red-600">{errors.expense_date}</p>
              )}
            </div>

            <div>
              <label htmlFor="expense-payment-method" className="block text-sm font-medium text-gray-700">
                Payment method
              </label>
              <select
                id="expense-payment-method"
                name="payment_method"
                value={form.payment_method}
                onChange={handleChange}
                className={`${inputClass} ${inputOk}`}
              >
                <option value="">No payment method</option>
                {PAYMENT_METHODS.map((method) => (
                  <option key={method.value} value={method.value}>
                    {method.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="expense-status" className="block text-sm font-medium text-gray-700">
                Status
              </label>
              <select
                id="expense-status"
                name="status"
                value={form.status}
                onChange={handleChange}
                className={`${inputClass} ${inputOk}`}
              >
                <option value="">Automatic (based on date)</option>
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="expense-notes" className="block text-sm font-medium text-gray-700">
              Notes
            </label>
            <textarea
              id="expense-notes"
              name="notes"
              rows={3}
              value={form.notes}
              onChange={handleChange}
              className={`${inputClass} ${errors.notes ? inputBad : inputOk}`}
              aria-invalid={Boolean(errors.notes)}
            />
            {errors.notes && <p className="mt-1 text-sm text-red-600">{errors.notes}</p>}
          </div>

          <div className="flex flex-col-reverse gap-3 pt-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={() => onClose?.()}
              disabled={saving}
              className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
