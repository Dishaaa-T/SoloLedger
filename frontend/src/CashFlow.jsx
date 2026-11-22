
import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import { getCashflow } from '../services/api'

export default function CashFlow() {
  const [forecast, setForecast] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadForecast() {
      try {
        const response = await getCashflow(30)
        setForecast(response.data)
      } catch (err) {
        setError('Unable to load cash flow forecast.')
      } finally {
        setLoading(false)
      }
    }

    loadForecast()
  }, [])

  const money = (value) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(value || 0)

  const cardStyle = {
    background: 'white',
    padding: '20px',
    borderRadius: '12px',
    border: '1px solid #e5e7eb',
  }

  if (loading) {
    return <div><PageHeader title="Cash Flow Forecast" /><p>Loading forecast...</p></div>
  }

  if (error) {
    return <div><PageHeader title="Cash Flow Forecast" /><p style={{ color: 'red' }}>{error}</p></div>
  }

  if (!forecast) {
    return <div><PageHeader title="Cash Flow Forecast" /><EmptyState title="No forecast yet" message="Unable to find forecast data." /></div>
  }

  return (
    <div>
      <PageHeader title="Cash Flow Forecast" />

      <div style={{ padding: '24px' }}>
        <h2>Cash Flow Forecast</h2>
        <p>See where your cash is heading over the next 30 days.</p>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
          gap: '16px',
          marginTop: '24px'
        }}>
          <div style={cardStyle}>
            <p>Starting Balance</p>
            <h2>{money(forecast.starting_balance)}</h2>
          </div>

          <div style={cardStyle}>
            <p>Expected Income</p>
            <h2 style={{ color: '#059669' }}>
              {money(forecast.expected_income)}
            </h2>
          </div>

          <div style={cardStyle}>
            <p>Expected Expenses</p>
            <h2 style={{ color: '#dc2626' }}>
              {money(forecast.expected_expenses)}
            </h2>
          </div>

          <div style={cardStyle}>
            <p>Projected Closing Balance</p>
            <h2 style={{ color: '#059669' }}>
              {money(forecast.projected_closing_balance)}
            </h2>
          </div>
        </div>

        <div style={{
          ...cardStyle,
          marginTop: '20px'
        }}>
          <h3>Cash Flow Risk Analysis</h3>

          <p>
            Risk of negative balance:{' '}
            <strong style={{
              color: forecast.risk_of_negative_balance
                ? '#dc2626' : '#059669'
            }}>
              {forecast.risk_of_negative_balance ? 'Yes' : 'No'}
            </strong>
          </p>

          <p>
            Lowest projected balance:{' '}
            <strong>{money(forecast.lowest_projected_balance)}</strong>
          </p>

          <p>
            Lowest balance date:{' '}
            <strong>{forecast.lowest_balance_date}</strong>
          </p>
        </div>

        <div style={{
          ...cardStyle,
          marginTop: '20px',
          overflowX: 'auto'
        }}>
          <h3>Daily Cash Flow Forecast</h3>

          <table style={{
            width: '100%',
            borderCollapse: 'collapse',
            marginTop: '16px'
          }}>
            <thead>
              <tr>
                <th style={{ padding: '12px', textAlign: 'left' }}>Date</th>
                <th style={{ padding: '12px', textAlign: 'left' }}>Income</th>
                <th style={{ padding: '12px', textAlign: 'left' }}>Expenses</th>
                <th style={{ padding: '12px', textAlign: 'left' }}>Projected Balance</th>
              </tr>
            </thead>

            <tbody>
              {forecast.daily_forecast.map(day => (
                <tr key={day.date}>
                  <td style={{ padding: '12px' }}>{day.date}</td>
                  <td style={{ padding: '12px', color: '#059669' }}>
                    {money(day.expected_income)}
                  </td>
                  <td style={{ padding: '12px', color: '#dc2626' }}>
                    {money(day.expected_expenses)}
                  </td>
                  <td style={{ padding: '12px', fontWeight: '600' }}>
                    {money(day.projected_balance)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p style={{ color: '#64748b', marginTop: '16px' }}>
          Forecast period: {forecast.forecast_days} days | Currency: {forecast.currency}
        </p>
      </div>
    </div>
  )
}
