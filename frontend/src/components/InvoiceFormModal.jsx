import { useEffect, useState } from 'react'
import { createInvoice, updateInvoice } from '../services/api'

const CONNECTION_MESSAGE = 'Could not reach the API. Check that the backend is running.'
const GENERIC_MESSAGE = 'Something went wrong. Try again.'
const MAX_AMOUNT = 10000000

const inputClass =
  'mt-1 block w-full rounded-lg border px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-indigo-500'
const inputOk = 'border-gray-300 focus:border-indigo-500'
const inputBad = 'border-red-400 focus:border-red-500'

function todayLocal() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function emptyForm() {
  return {
    client_id: '',
    invoice_number: '',
    description: '',
    amount: '',
    issue_date: todayLocal(),
    due_date: '',
  }
}

function formFromInvoice(invoice) {
  return {
    client_id: String(invoice.client_id ?? ''),
    invoice_number: invoice.invoice_number ?? '',
    description: invoice.description ?? '',
    amount: String(Number(invoice.amount)),
    issue_date: invoice.issue_date ?? '',
    due_date: invoice.due_date ?? '',
  }
}

function validate(form) {
  const errors = {}

  if (!form.client_id) {
    errors.client_id = 'Client is required.'
  }

  const invoiceNumber = form.invoice_number.trim()
  if (!invoiceNumber) {
    errors.invoice_number = 'Invoice number is required.'
  } else if (invoiceNumber.length > 50) {
    errors.invoice_number = 'Invoice number must be 50 characters or fewer.'
  }

  if (form.description.trim().length > 500) {
    errors.description = 'Description must be 500 characters or fewer.'
  }

  const raw = form.amount.trim()
  if (!raw) {
    errors.amount = 'Amount is required.'
  } else {
    const match = /^\d+(?:\.(\d+))?$/.exec(raw)
    const value = Number(raw)
    if (!match || !Number.isFinite(value)) {
      errors.amount = 'Enter a valid amount.'
    } else if (value <= 0) {
      errors.amount = 'Amount must be greater than 0.'
    } else if (match[1] && match[1].length > 2) {
      errors.amount = 'Amount can have at most 2 decimal places.'
    } else if (value > MAX_AMOUNT) {
      errors.amount = 'Amount cannot exceed 10,000,000.'
    }
  }

  if (!form.issue_date) {
    errors.issue_date = 'Issue date is required.'
  }
  if (!form.due_date) {
    errors.due_date = 'Due date is required.'
  }
  if (form.issue_date && form.due_date && form.due_date < form.issue_date) {
    errors.due_date = 'Due date cannot be earlier than issue date.'
  }

  return errors
}

function buildPayload(form) {
  const description = form.description.trim()
  return {
    client_id: Number(form.client_id),
    invoice_number: form.invoice_number.trim(),
    description: description === '' ? null : description,
    amount: Number(form.amount.trim()),
    issue_date: form.issue_date,
    due_date: form.due_date,
  }
}

function describeError(err) {
  if (!err.response) {
    return { form: CONNECTION_MESSAGE }
  }
  const { status, data } = err.response
  const detail = data?.detail

  if (status === 409) {
    const message = typeof detail === 'string' ? detail : 'This invoice number already exists.'
    if (/already exists|invoice number/i.test(message)) {
      return { errors: { invoice_number: message } }
    }
    return { form: message }
  }

  if (status === 422) {
    if (Array.isArray(detail)) {
      const messages = detail.map((item) => item?.msg).filter(Boolean)
      return { form: messages.length ? messages.join(' ') : GENERIC_MESSAGE }
    }
    return { form: typeof detail === 'string' ? detail : GENERIC_MESSAGE }
  }

  if (status === 404) {
    return { form: typeof detail === 'string' ? detail : 'Not found.' }
  }

  return { form: typeof detail === 'string' ? detail : GENERIC_MESSAGE }
}

export default function InvoiceFormModal({ open, invoice, clients = [], onClose, onSaved }) {
  const [form, setForm] = useState(emptyForm)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  const isEdit = Boolean(invoice)

  // Reset the form each time the modal opens or the target invoice changes.
  useEffect(() => {
    if (open) {
      setForm(invoice ? formFromInvoice(invoice) : emptyForm())
      setErrors({})
      setSaving(false)
    }
  }, [open, invoice])

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

    const payload = buildPayload(form)
    setSaving(true)
    setErrors({})
    try {
      const response = isEdit
        ? await updateInvoice(invoice.id, payload)
        : await createInvoice(payload)
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

  const title = isEdit ? 'Edit Invoice' : 'Create Invoice'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={handleBackdropClick}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="invoice-form-title"
        className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-xl border border-gray-200 bg-white p-6 text-gray-900 shadow-lg"
      >
        <h2 id="invoice-form-title" className="text-lg font-semibold text-gray-900">
          {title}
        </h2>

        <form onSubmit={handleSubmit} noValidate className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {errors.form && (
            <p role="alert" className="text-sm text-red-600 sm:col-span-2">
              {errors.form}
            </p>
          )}

          <div className="sm:col-span-2">
            <label htmlFor="invoice-client" className="block text-sm font-medium text-gray-700">
              Client <span className="text-red-600">*</span>
            </label>
            <select
              id="invoice-client"
              name="client_id"
              value={form.client_id}
              onChange={handleChange}
              className={`${inputClass} ${errors.client_id ? inputBad : inputOk}`}
              aria-invalid={Boolean(errors.client_id)}
            >
              <option value="">Select a client</option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.company ? `${client.name} (${client.company})` : client.name}
                </option>
              ))}
            </select>
            {errors.client_id && <p className="mt-1 text-sm text-red-600">{errors.client_id}</p>}
          </div>

          <div>
            <label htmlFor="invoice-number" className="block text-sm font-medium text-gray-700">
              Invoice number <span className="text-red-600">*</span>
            </label>
            <input
              id="invoice-number"
              name="invoice_number"
              type="text"
              value={form.invoice_number}
              onChange={handleChange}
              className={`${inputClass} ${errors.invoice_number ? inputBad : inputOk}`}
              aria-invalid={Boolean(errors.invoice_number)}
            />
            {errors.invoice_number && (
              <p className="mt-1 text-sm text-red-600">{errors.invoice_number}</p>
            )}
          </div>

          <div>
            <label htmlFor="invoice-amount" className="block text-sm font-medium text-gray-700">
              Amount (INR) <span className="text-red-600">*</span>
            </label>
            <input
              id="invoice-amount"
              name="amount"
              type="number"
              step="0.01"
              min="0"
              value={form.amount}
              onChange={handleChange}
              className={`${inputClass} ${errors.amount ? inputBad : inputOk}`}
              aria-invalid={Boolean(errors.amount)}
            />
            {errors.amount && <p className="mt-1 text-sm text-red-600">{errors.amount}</p>}
          </div>

          <div className="sm:col-span-2">
            <label htmlFor="invoice-description" className="block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              id="invoice-description"
              name="description"
              rows={3}
              value={form.description}
              onChange={handleChange}
              className={`${inputClass} ${errors.description ? inputBad : inputOk}`}
              aria-invalid={Boolean(errors.description)}
            />
            {errors.description && (
              <p className="mt-1 text-sm text-red-600">{errors.description}</p>
            )}
          </div>

          <div>
            <label htmlFor="invoice-issue-date" className="block text-sm font-medium text-gray-700">
              Issue date <span className="text-red-600">*</span>
            </label>
            <input
              id="invoice-issue-date"
              name="issue_date"
              type="date"
              value={form.issue_date}
              onChange={handleChange}
              className={`${inputClass} ${errors.issue_date ? inputBad : inputOk}`}
              aria-invalid={Boolean(errors.issue_date)}
            />
            {errors.issue_date && <p className="mt-1 text-sm text-red-600">{errors.issue_date}</p>}
          </div>

          <div>
            <label htmlFor="invoice-due-date" className="block text-sm font-medium text-gray-700">
              Due date <span className="text-red-600">*</span>
            </label>
            <input
              id="invoice-due-date"
              name="due_date"
              type="date"
              value={form.due_date}
              onChange={handleChange}
              className={`${inputClass} ${errors.due_date ? inputBad : inputOk}`}
              aria-invalid={Boolean(errors.due_date)}
            />
            {errors.due_date && <p className="mt-1 text-sm text-red-600">{errors.due_date}</p>}
          </div>

          <div className="flex flex-col-reverse gap-3 pt-2 sm:col-span-2 sm:flex-row sm:justify-end">
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
