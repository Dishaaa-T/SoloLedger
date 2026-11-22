
import { useCallback, useEffect, useRef, useState } from 'react'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import PaymentRiskCard from '../components/PaymentRiskCard'
import ClientFormModal from '../components/ClientFormModal'
import ConfirmDialog from '../components/ConfirmDialog'
import { getClients, deleteClient } from '../services/api'

const LOAD_ERROR = 'Unable to load clients. Check backend connection.'
const REFRESH_ERROR = 'Unable to refresh clients. Check backend connection.'
const CONNECTION_MESSAGE = 'Could not reach the API. Check that the backend is running.'
const GENERIC_MESSAGE = 'Something went wrong. Try again.'
const NOTICE_MS = 4000

function describeDeleteError(err) {
  if (!err.response) {
    return CONNECTION_MESSAGE
  }
  const { status, data } = err.response
  const detail = typeof data?.detail === 'string' ? data.detail : null

  if (status === 404) {
    return 'This client no longer exists.'
  }
  if (status === 409) {
    return detail || 'This client cannot be deleted right now.'
  }
  return detail || GENERIC_MESSAGE
}

export default function Clients() {
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedClient, setSelectedClient] = useState(null)

  const [formOpen, setFormOpen] = useState(false)
  const [editingClient, setEditingClient] = useState(null)

  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  const [notice, setNotice] = useState('')
  const noticeTimer = useRef(null)

  const loadClients = useCallback(async (failMessage = LOAD_ERROR) => {
    try {
      const response = await getClients()
      setClients(response.data)
      setError('')
    } catch (err) {
      setError(failMessage)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadClients()
  }, [loadClients])

  // Clear any pending notice timer when the page unmounts.
  useEffect(() => {
    return () => clearTimeout(noticeTimer.current)
  }, [])

  function showNotice(message) {
    clearTimeout(noticeTimer.current)
    setNotice(message)
    noticeTimer.current = setTimeout(() => setNotice(''), NOTICE_MS)
  }

  function openCreateForm() {
    setEditingClient(null)
    setFormOpen(true)
  }

  function openEditForm(event, client) {
    event.stopPropagation()
    setEditingClient(client)
    setFormOpen(true)
  }

  function closeForm() {
    setFormOpen(false)
  }

  function handleSaved(savedClient) {
    const wasEdit = Boolean(editingClient)
    if (wasEdit) {
      setSelectedClient(savedClient)
    }
    showNotice(wasEdit ? 'Client updated.' : 'Client added.')
    loadClients(REFRESH_ERROR)
  }

  function openDeleteDialog(event, client) {
    event.stopPropagation()
    setDeleteError('')
    setDeleteTarget(client)
  }

  function closeDeleteDialog() {
    if (deleteBusy) return
    setDeleteTarget(null)
    setDeleteError('')
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return
    const target = deleteTarget
    setDeleteBusy(true)
    setDeleteError('')
    try {
      await deleteClient(target.id)
      setDeleteTarget(null)
      setSelectedClient(prev => (prev?.id === target.id ? null : prev))
      showNotice('Client deleted.')
      await loadClients(REFRESH_ERROR)
    } catch (err) {
      setDeleteError(describeDeleteError(err))
      if (err.response?.status === 404) {
        setSelectedClient(prev => (prev?.id === target.id ? null : prev))
        await loadClients(REFRESH_ERROR)
      }
    } finally {
      setDeleteBusy(false)
    }
  }

  return (
    <div>
      <PageHeader title="Clients" />

      <div style={{ padding: '24px' }}>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2>Clients</h2>
            <p>Manage the people and businesses you bill.</p>
          </div>
          <button
            type="button"
            onClick={openCreateForm}
            className="inline-flex shrink-0 items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            + Add Client
          </button>
        </div>

        {error && <p style={{ color: 'red' }}>{error}</p>}

        {notice && (
          <p className="mt-4 rounded-lg border border-green-200 bg-green-50 px-4 py-2 text-sm text-green-700">
            {notice}
          </p>
        )}

        {loading ? (
          <p>Loading clients...</p>
        ) : clients.length === 0 ? (
          <EmptyState
            title="No clients yet"
            message="Add clients to get started."
          />
        ) : (
          <div className="overflow-x-auto" style={{
            background: 'white',
            padding: '20px',
            borderRadius: '12px',
            overflowX: 'auto'
          }}>
            <h3>Total Clients: {clients.length}</h3>

            <table style={{
              width: '100%',
              borderCollapse: 'collapse'
            }}>
              <thead>
                <tr>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Name</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Email</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Phone</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Company</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>

              <tbody>
                {clients.map(client => (
                  <tr
                    key={client.id}
                    onClick={() => setSelectedClient(client)}
                    style={{
                      cursor: 'pointer',
                      background: selectedClient?.id === client.id ? '#EEF2FF' : undefined
                    }}
                  >
                    <td style={{ padding: '12px' }}>{client.name}</td>
                    <td style={{ padding: '12px' }}>{client.email}</td>
                    <td style={{ padding: '12px' }}>{client.phone || '-'}</td>
                    <td style={{ padding: '12px' }}>{client.company || '-'}</td>
                    <td style={{ padding: '12px' }} className="whitespace-nowrap text-right">
                      <button
                        type="button"
                        onClick={(event) => openEditForm(event, client)}
                        className="rounded-md px-2 py-1 text-sm font-medium text-indigo-600 hover:bg-indigo-50"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={(event) => openDeleteDialog(event, client)}
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
        )}

        {!loading && clients.length > 0 && selectedClient && (
          <div style={{ marginTop: '24px' }}>
            <PaymentRiskCard clientId={selectedClient.id} clientName={selectedClient.name} />
          </div>
        )}
      </div>

      <ClientFormModal
        open={formOpen}
        client={editingClient}
        onClose={closeForm}
        onSaved={handleSaved}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete client?"
        message={deleteTarget ? `Delete ${deleteTarget.name}? This cannot be undone.` : ''}
        confirmLabel="Delete"
        onConfirm={handleConfirmDelete}
        onCancel={closeDeleteDialog}
        busy={deleteBusy}
        error={deleteError}
      />
    </div>
  )
}
