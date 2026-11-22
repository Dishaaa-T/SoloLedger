
import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import { getClients } from '../services/api'

export default function Clients() {
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadClients() {
      try {
        const response = await getClients()
        setClients(response.data)
      } catch (err) {
        setError('Unable to load clients. Check backend connection.')
      } finally {
        setLoading(false)
      }
    }

    loadClients()
  }, [])

  return (
    <div>
      <PageHeader title="Clients" />

      <div style={{ padding: '24px' }}>
        <h2>Clients</h2>
        <p>Manage the people and businesses you bill.</p>

        {error && <p style={{ color: 'red' }}>{error}</p>}

        {loading ? (
          <p>Loading clients...</p>
        ) : clients.length === 0 ? (
          <EmptyState
            title="No clients yet"
            message="Add clients to get started."
          />
        ) : (
          <div style={{
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
                </tr>
              </thead>

              <tbody>
                {clients.map(client => (
                  <tr key={client.id}>
                    <td style={{ padding: '12px' }}>{client.name}</td>
                    <td style={{ padding: '12px' }}>{client.email}</td>
                    <td style={{ padding: '12px' }}>{client.phone || '-'}</td>
                    <td style={{ padding: '12px' }}>{client.company || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
