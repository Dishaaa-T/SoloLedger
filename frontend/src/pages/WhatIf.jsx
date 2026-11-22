
import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import { runWhatIf, getInvoices } from '../services/api'

export default function WhatIf() {
  const today = new Date().toLocaleDateString('en-CA')

  const [invoices, setInvoices] = useState([])
  const [form, setForm] = useState({
    delay_invoice_id: '',
    delay_days: 7,
    unexpected_expense: {
      amount: 1,
      date: today,
    },
    additional_income: {
      amount: 1,
      date: today,
    },
    forecast_days: 30,
  })

  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadingInvoices, setLoadingInvoices] = useState(true)
  const [error, setError] = useState('')

  const money = value =>
    `₹${Number(value ?? 0).toLocaleString('en-IN', {
      maximumFractionDigits: 2,
    })}`

  useEffect(() => {
    async function loadInvoices() {
      try {
        const response = await getInvoices()
        const data = Array.isArray(response.data) ? response.data : []

        const unpaid = data.filter(
          invoice => invoice.status?.toLowerCase() !== 'paid'
        )

        setInvoices(unpaid)

        if (unpaid.length > 0) {
          setForm(prev => ({
            ...prev,
            delay_invoice_id: unpaid[0].id,
          }))
        }
      } catch (err) {
        setError(
          err.response?.data?.detail || 'Unable to load invoices.'
        )
      } finally {
        setLoadingInvoices(false)
      }
    }

    loadInvoices()
  }, [])

  const update = (field, value) => {
    setForm(prev => ({
      ...prev,
      [field]: value,
    }))
  }

  const handleSubmit = async e => {
    e.preventDefault()

    if (!form.delay_invoice_id) {
      setError('Please select an unpaid invoice.')
      return
    }

    setLoading(true)
    setError('')
    setResult(null)

    try {
      const response = await runWhatIf({
        delay_invoice_id: Number(form.delay_invoice_id),
        delay_days: Number(form.delay_days),
        unexpected_expense: {
          amount: Number(form.unexpected_expense.amount),
          date: form.unexpected_expense.date,
        },
        additional_income: {
          amount: Number(form.additional_income.amount),
          date: form.additional_income.date,
        },
        forecast_days: Number(form.forecast_days),
      })

      setResult(response.data)
    } catch (err) {
      const detail = err.response?.data?.detail

      setError(
        Array.isArray(detail)
          ? detail.map(item => item.msg).join(', ')
          : typeof detail === 'string'
            ? detail
            : 'Unable to run simulation.'
      )
    } finally {
      setLoading(false)
    }
  }

  const resultCards = result ? [
    {
      title: 'Baseline Closing Balance',
      value: result.baseline?.closing_balance,
      color: '#2563eb',
    },
    {
      title: 'Simulated Closing Balance',
      value: result.simulated?.closing_balance,
      color: '#059669',
    },
    {
      title: 'Lowest Projected Balance',
      value: result.simulated?.lowest_balance,
      color: '#d97706',
    },
    {
      title: 'Difference',
      value: result.difference,
      color: Number(result.difference) >= 0 ? '#059669' : '#dc2626',
    },
  ] : []

  return (
    <div>
      <PageHeader title="What-If Simulator" />

      <div style={{ padding: '24px' }}>
        <h2>What-If Simulator</h2>
        <p>Test financial scenarios before making business decisions.</p>

        <form
          onSubmit={handleSubmit}
          style={{
            background: 'white',
            padding: '24px',
            borderRadius: '12px',
            display: 'grid',
            gap: '16px',
            marginTop: '20px',
          }}
        >
          <h3>Invoice Delay Scenario</h3>

          <label>Select Unpaid Invoice</label>
          <select
            required
            value={form.delay_invoice_id}
            disabled={loadingInvoices || invoices.length === 0}
            onChange={e => update('delay_invoice_id', e.target.value)}
          >
            {loadingInvoices && (
              <option value="">Loading invoices...</option>
            )}

            {!loadingInvoices && invoices.length === 0 && (
              <option value="">No unpaid invoices available</option>
            )}

            {invoices.map(invoice => (
              <option key={invoice.id} value={invoice.id}>
                Invoice #{invoice.id} - {money(invoice.amount)} - {invoice.status}
              </option>
            ))}
          </select>

          <label>Delay Days</label>
          <input
            type="number"
            min="0"
            value={form.delay_days}
            onChange={e => update('delay_days', e.target.value)}
          />

          <h3>Unexpected Expense</h3>

          <label>Expense Amount (₹)</label>
          <input
            type="number"
            min="0"
            step="0.01"
            required
            value={form.unexpected_expense.amount}
            onChange={e =>
              setForm(prev => ({
                ...prev,
                unexpected_expense: {
                  ...prev.unexpected_expense,
                  amount: e.target.value,
                },
              }))
            }
          />

          <label>Expense Date</label>
          <input
            type="date"
            required
            value={form.unexpected_expense.date}
            onChange={e =>
              setForm(prev => ({
                ...prev,
                unexpected_expense: {
                  ...prev.unexpected_expense,
                  date: e.target.value,
                },
              }))
            }
          />

          <h3>Additional Income</h3>

          <label>Additional Income (₹)</label>
          <input
            type="number"
            min="0"
            step="0.01"
            required
            value={form.additional_income.amount}
            onChange={e =>
              setForm(prev => ({
                ...prev,
                additional_income: {
                  ...prev.additional_income,
                  amount: e.target.value,
                },
              }))
            }
          />

          <label>Income Date</label>
          <input
            type="date"
            required
            value={form.additional_income.date}
            onChange={e =>
              setForm(prev => ({
                ...prev,
                additional_income: {
                  ...prev.additional_income,
                  date: e.target.value,
                },
              }))
            }
          />

          <h3>Forecast Duration</h3>

          <select
            value={form.forecast_days}
            onChange={e => update('forecast_days', e.target.value)}
          >
            <option value="30">30 Days</option>
            <option value="60">60 Days</option>
            <option value="90">90 Days</option>
          </select>

          <button
            type="submit"
            disabled={loading || loadingInvoices || invoices.length === 0}
          >
            {loading ? 'Running Simulation...' : 'Run Simulation'}
          </button>
        </form>

        {error && (
          <p style={{ color: '#dc2626', marginTop: '20px' }}>
            {error}
          </p>
        )}

        {result && (
          <div style={{ marginTop: '28px' }}>
            <h2 style={{ marginBottom: '18px' }}>
              Simulation Results
            </h2>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
              gap: '16px',
            }}>
              {resultCards.map((item, index) => (
                <div
                  key={index}
                  style={{
                    background: 'white',
                    padding: '22px',
                    borderRadius: '12px',
                    border: '1px solid #e5e7eb',
                  }}
                >
                  <p style={{ color: '#64748b', margin: 0 }}>
                    {item.title}
                  </p>
                  <h2 style={{
                    color: item.color,
                    marginBottom: 0,
                  }}>
                    {money(item.value)}
                  </h2>
                </div>
              ))}
            </div>

            <div style={{
              background: 'white',
              padding: '22px',
              borderRadius: '12px',
              marginTop: '18px',
              border: '1px solid #e5e7eb',
            }}>
              <h3>Cash Flow Risk Analysis</h3>

              <p>
                Negative Balance Risk:{' '}
                <strong style={{
                  color: result.simulated?.risk_of_negative_balance
                    ? '#dc2626' : '#059669',
                }}>
                  {result.simulated?.risk_of_negative_balance ? 'Yes' : 'No'}
                </strong>
              </p>

              <p>
                Lowest Balance Date:{' '}
                <strong>
                  {result.simulated?.lowest_balance_date || 'N/A'}
                </strong>
              </p>

              <p>
                Forecast Duration:{' '}
                <strong>{result.forecast_days} Days</strong>
              </p>

              <p>
                Applied Scenarios:{' '}
                <strong>
                  {result.applied_scenarios?.join(', ') || 'None'}
                </strong>
              </p>
            </div>

            <div style={{
              background: 'white',
              padding: '22px',
              borderRadius: '12px',
              marginTop: '18px',
              border: '1px solid #e5e7eb',
              overflowX: 'auto',
            }}>
              <h3>Daily Simulation Forecast</h3>

              <table style={{
                width: '100%',
                borderCollapse: 'collapse',
                marginTop: '16px',
                textAlign: 'left',
              }}>
                <thead>
                  <tr style={{ background: '#f1f5f9' }}>
                    {[
                      'Date',
                      'Baseline Balance',
                      'Simulated Balance',
                      'Income',
                      'Expenses',
                    ].map(heading => (
                      <th key={heading} style={{ padding: '12px' }}>
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody>
                  {(result.daily_forecast || []).map((day, index) => (
                    <tr key={index} style={{
                      borderBottom: '1px solid #e5e7eb',
                    }}>
                      <td style={{ padding: '12px' }}>{day.date}</td>
                      <td style={{ padding: '12px' }}>
                        {money(day.baseline_balance)}
                      </td>
                      <td style={{
                        padding: '12px',
                        color: day.simulated_balance < 0
                          ? '#dc2626' : '#059669',
                      }}>
                        {money(day.simulated_balance)}
                      </td>
                      <td style={{ padding: '12px' }}>
                        {money(day.simulated_income)}
                      </td>
                      <td style={{ padding: '12px' }}>
                        {money(day.simulated_expenses)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
