
import { useEffect, useState } from 'react'
import EmptyState from '../components/EmptyState'
import { getActionCentre } from '../services/api'

export default function ActionCentre() {
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadActions = async () => {
    try {
      setLoading(true)
      setError('')

      const response = await getActionCentre()
      const data = response.data

      const items = Array.isArray(data)
        ? data
        : data?.actions || data?.items || data?.alerts || []

      setActions(items)
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to load action centre. Please check the backend.'
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadActions()
  }, [])

  const getPriorityColor = (priority) => {
    const value = String(priority || '').toLowerCase()

    if (value === 'high' || value === 'critical') return '#dc2626'
    if (value === 'medium') return '#d97706'
    return '#16a34a'
  }

  const money = (value) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(Number(value) || 0)

  return (
    <div>
      <div style={{ padding: '24px' }}>

        {loading && (
          <p style={{ color: '#64748b', marginTop: '24px' }}>
            Loading action items...
          </p>
        )}

        {error && (
          <div
            style={{
              background: '#fef2f2',
              color: '#dc2626',
              padding: '16px',
              borderRadius: '10px',
              marginTop: '20px',
            }}
          >
            <p>{error}</p>
            <button onClick={loadActions}>Try Again</button>
          </div>
        )}

        {!loading && !error && actions.length === 0 && (
          <EmptyState
            title="No actions yet"
            message="You're all caught up! No action items need your attention."
          />
        )}

        {!loading && !error && actions.length > 0 && (
          <div
            style={{
              display: 'grid',
              gap: '16px',
              marginTop: '24px',
            }}
          >
            {actions.map((item, index) => {
              const title =
                item.title ||
                item.action ||
                item.type ||
                'Action Required'

              const message =
                item.message ||
                item.description ||
                item.recommendation ||
                'Please review this item.'

              const priority =
                item.priority || item.severity || 'Normal'

              return (
                <div
                  key={item.id || index}
                  style={{
                    background: 'white',
                    padding: '20px',
                    borderRadius: '12px',
                    border: '1px solid #e5e7eb',
                    boxShadow: '0 2px 6px rgba(0,0,0,0.03)',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '12px',
                      flexWrap: 'wrap',
                    }}
                  >
                    <h3 style={{ margin: 0, color: '#1e293b' }}>
                      {title}
                    </h3>

                    <span
                      style={{
                        color: getPriorityColor(priority),
                        background: '#f8fafc',
                        padding: '5px 10px',
                        borderRadius: '20px',
                        fontWeight: '600',
                        fontSize: '12px',
                      }}
                    >
                      {String(priority).toUpperCase()}
                    </span>
                  </div>

                  <p style={{ color: '#64748b', marginBottom: '8px' }}>
                    {message}
                  </p>

                  {item.amount != null && (
                    <p style={{ fontWeight: '600', margin: '8px 0' }}>
                      Amount: {money(item.amount)}
                    </p>
                  )}

                  {(item.due_date || item.date) && (
                    <p style={{ color: '#64748b', fontSize: '13px' }}>
                      Date: {item.due_date || item.date}
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
