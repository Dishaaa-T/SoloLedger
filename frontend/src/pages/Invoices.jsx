
import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import { getInvoices } from '../services/api'

export default function Invoices() {
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadInvoices() {
      try {
        const response = await getInvoices()
        setInvoices(response.data)
      } catch (err) {
        setError('Unable to load invoices. Check backend connection.')
      } finally {
        setLoading(false)
      }
    }

    loadInvoices()
  }, [])

  const money = (value) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(value)

  const statusStyle = (status) => ({
    display: 'inline-block',
    padding: '5px 10px',
    borderRadius: '20px',
    fontSize: '13px',
    fontWeight: '600',
    background:
      status === 'paid' ? '#dcfce7' :
      status === 'overdue' ? '#fee2e2' : '#fef3c7',
    color:
      status === 'paid' ? '#166534' :
      status === 'overdue' ? '#991b1b' : '#92400e',
  })

  return (
    <div>
      <PageHeader title="Invoices" />

      <div style={{ padding: '24px' }}>
        <h2>Invoices</h2>
        <p>Track what you have billed and what is still owed.</p>

        {error && <p style={{ color: 'red' }}>{error}</p>}

        {loading ? (
          <p>Loading invoices...</p>
        ) : invoices.length === 0 ? (
          <EmptyState
            title="No invoices yet"
            message="Your invoices will appear here."
          />
        ) : (
          <div style={{
            background: 'white',
            padding: '20px',
            borderRadius: '12px',
            overflowX: 'auto'
          }}>
            <h3>Total Invoices: {invoices.length}</h3>

            <table style={{
              width: '100%',
              borderCollapse: 'collapse'
            }}>
              <thead>
                <tr>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Invoice No.</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Client</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Description</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Amount</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Issue Date</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Due Date</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Status</th>
                </tr>
              </thead>

              <tbody>
                {invoices.map(invoice => (
                  <tr key={invoice.id}>
                    <td style={{ padding: '12px' }}>
                      {invoice.invoice_number}
                    </td>
                    <td style={{ padding: '12px' }}>
                      {invoice.client?.name || '-'}
                    </td>
                    <td style={{ padding: '12px' }}>
                      {invoice.description}
                    </td>
                    <td style={{ padding: '12px' }}>
                      {money(Number(invoice.amount))}
                    </td>
                    <td style={{ padding: '12px' }}>
                      {invoice.issue_date}
                    </td>
                    <td style={{ padding: '12px' }}>
                      {invoice.due_date}
                    </td>
                    <td style={{ padding: '12px' }}>
                      <span style={statusStyle(invoice.status)}>
                        {invoice.status.toUpperCase()}
                      </span>
                    </td>
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
