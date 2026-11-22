import { useEffect, useState } from 'react'
import { createClient, updateClient } from '../services/api'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const CONNECTION_MESSAGE = 'Could not reach the API. Check that the backend is running.'
const GENERIC_MESSAGE = 'Something went wrong. Try again.'

const EMPTY_FORM = { name: '', email: '', phone: '', company: '', notes: '' }

const inputClass =
  'mt-1 block w-full rounded-lg border px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-indigo-500'
const inputOk = 'border-gray-300 focus:border-indigo-500'
const inputBad = 'border-red-400 focus:border-red-500'

function validate(form) {
  const errors = {}
  const name = form.name.trim()
  if (!name) {
    errors.name = 'Name is required.'
  } else if (name.length > 120) {
    errors.name = 'Name must be 120 characters or fewer.'
  }

  const email = form.email.trim()
  if (email && !EMAIL_PATTERN.test(email)) {
    errors.email = 'Enter a valid email address.'
  } else if (email.length > 254) {
    errors.email = 'Email must be 254 characters or fewer.'
  }

  if (form.phone.trim().length > 30) {
    errors.phone = 'Phone must be 30 characters or fewer.'
  }
  if (form.company.trim().length > 120) {
    errors.company = 'Company must be 120 characters or fewer.'
  }
  if (form.notes.trim().length > 1000) {
    errors.notes = 'Notes must be 1000 characters or fewer.'
  }
  return errors
}

function buildPayload(form) {
  const optional = (value) => {
    const trimmed = value.trim()
    return trimmed === '' ? null : trimmed
  }
  return {
    name: form.name.trim(),
    email: optional(form.email),
    phone: optional(form.phone),
    company: optional(form.company),
    notes: optional(form.notes),
  }
}

function describeError(err) {
  if (!err.response) {
    return { form: CONNECTION_MESSAGE }
  }
  const { status, data } = err.response
  const detail = data?.detail

  if (status === 409) {
    const message = typeof detail === 'string' ? detail : 'This client already exists.'
    if (/email/i.test(message)) {
      return { errors: { email: message } }
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

  return { form: typeof detail === 'string' ? detail : GENERIC_MESSAGE }
}

export default function ClientFormModal({ open, client, onClose, onSaved }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  const isEdit = Boolean(client)

  // Reset the form each time the modal opens or the target client changes.
  useEffect(() => {
    if (open) {
      setForm(
        client
          ? {
              name: client.name ?? '',
              email: client.email ?? '',
              phone: client.phone ?? '',
              company: client.company ?? '',
              notes: client.notes ?? '',
            }
          : EMPTY_FORM
      )
      setErrors({})
      setSaving(false)
    }
  }, [open, client])

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
        ? await updateClient(client.id, payload)
        : await createClient(payload)
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

  const title = isEdit ? 'Edit Client' : 'Add Client'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={handleBackdropClick}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="client-form-title"
        className="max-h-[90vh] w-full max-w-[560px] overflow-y-auto rounded-xl border border-gray-200 bg-white p-6 text-gray-900 shadow-lg"
      >
        <h2 id="client-form-title" className="text-lg font-semibold text-gray-900">
          {title}
        </h2>

        <form onSubmit={handleSubmit} noValidate className="mt-4 space-y-4">
          {errors.form && (
            <p role="alert" className="text-sm text-red-600">
              {errors.form}
            </p>
          )}

          <div>
            <label htmlFor="client-name" className="block text-sm font-medium text-gray-700">
              Name <span className="text-red-600">*</span>
            </label>
            <input
              id="client-name"
              name="name"
              type="text"
              value={form.name}
              onChange={handleChange}
              className={`${inputClass} ${errors.name ? inputBad : inputOk}`}
              aria-invalid={Boolean(errors.name)}
            />
            {errors.name && <p className="mt-1 text-sm text-red-600">{errors.name}</p>}
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="client-email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                id="client-email"
                name="email"
                type="email"
                value={form.email}
                onChange={handleChange}
                className={`${inputClass} ${errors.email ? inputBad : inputOk}`}
                aria-invalid={Boolean(errors.email)}
              />
              {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email}</p>}
            </div>

            <div>
              <label htmlFor="client-phone" className="block text-sm font-medium text-gray-700">
                Phone
              </label>
              <input
                id="client-phone"
                name="phone"
                type="text"
                value={form.phone}
                onChange={handleChange}
                className={`${inputClass} ${errors.phone ? inputBad : inputOk}`}
                aria-invalid={Boolean(errors.phone)}
              />
              {errors.phone && <p className="mt-1 text-sm text-red-600">{errors.phone}</p>}
            </div>
          </div>

          <div>
            <label htmlFor="client-company" className="block text-sm font-medium text-gray-700">
              Company
            </label>
            <input
              id="client-company"
              name="company"
              type="text"
              value={form.company}
              onChange={handleChange}
              className={`${inputClass} ${errors.company ? inputBad : inputOk}`}
              aria-invalid={Boolean(errors.company)}
            />
            {errors.company && <p className="mt-1 text-sm text-red-600">{errors.company}</p>}
          </div>

          <div>
            <label htmlFor="client-notes" className="block text-sm font-medium text-gray-700">
              Notes
            </label>
            <textarea
              id="client-notes"
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
