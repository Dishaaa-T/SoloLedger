
import { useEffect, useState } from 'react'
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
      <div style={{ padding: '24px' }}>

        <style>{`
          .wi-cards { display: grid; gap: 16px; }
          .wi-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
          }
          .wi-card-title { margin: 0; font-size: 16px; font-weight: 600; color: #1F2937; }
          .wi-card-sub { margin: 4px 0 0; font-size: 13px; color: #64748b; }
          .wi-fields { display: grid; gap: 14px; }
          .wi-field { display: flex; flex-direction: column; min-width: 0; }
          .wi-label { font-size: 13px; font-weight: 600; color: #1F2937; margin-bottom: 6px; }
          .wi-input {
            width: 100%;
            height: 42px;
            box-sizing: border-box;
            padding: 0 12px;
            font-size: 14px;
            color: #1F2937;
            background: white;
            border: 1px solid rgba(100, 116, 139, 0.45);
            border-radius: 8px;
            outline: none;
            transition: border-color 0.15s, box-shadow 0.15s;
          }
          .wi-input::placeholder { color: #94a3b8; }
          .wi-input:focus {
            border-color: #2563eb;
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
          }
          .wi-input:disabled { opacity: 0.6; cursor: not-allowed; background: #f1f5f9; }
          .wi-select {
            appearance: none;
            -webkit-appearance: none;
            padding-right: 36px;
            cursor: pointer;
            background-color: white;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' fill='none' stroke='%2364748b' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 12px center;
            background-size: 12px 8px;
          }
          .wi-input[type='date'] { color-scheme: light; }
          .wi-actions {
            display: flex;
            flex-wrap: wrap;
            align-items: flex-end;
            justify-content: space-between;
            gap: 16px;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 16px 20px;
          }
          .wi-forecast { width: 220px; max-width: 100%; }
          .wi-submit {
            height: 42px;
            padding: 0 28px;
            font-size: 15px;
            font-weight: 600;
            color: white;
            background: #2563eb;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            box-shadow: 0 2px 6px rgba(37, 99, 235, 0.3);
            transition: opacity 0.15s;
          }
          .wi-submit:hover:not(:disabled) { opacity: 0.9; }
          .wi-submit:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.35); }
          .wi-submit:disabled { opacity: 0.5; cursor: not-allowed; box-shadow: none; }
          @media (min-width: 900px) {
            .wi-cards { grid-template-columns: 1fr 1fr; }
            .wi-card-wide { grid-column: 1 / -1; }
            .wi-fields-2 { grid-template-columns: 1fr 1fr; }
            .wi-span-2 { grid-column: 1 / -1; }
          }
        `}</style>

        <form
          onSubmit={handleSubmit}
          style={{ marginTop: '20px', maxWidth: '960px' }}
        >
          <div className="wi-cards">
            <section className="wi-card wi-card-wide">
              <div>
                <h3 className="wi-card-title">Invoice Delay Scenario</h3>
                <p className="wi-card-sub">
                  Simulate paying a selected unpaid invoice later than planned.
                </p>
              </div>

              <div className="wi-fields wi-fields-2">
                <div className="wi-field wi-span-2">
                  <label htmlFor="wi-invoice" className="wi-label">
                    Select Unpaid Invoice
                  </label>
                  <select
                    id="wi-invoice"
                    className="wi-input wi-select"
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
                </div>

                <div className="wi-field">
                  <label htmlFor="wi-delay" className="wi-label">
                    Delay Days
                  </label>
                  <input
                    id="wi-delay"
                    className="wi-input"
                    type="number"
                    min="0"
                    placeholder="e.g. 7"
                    value={form.delay_days}
                    onChange={e => update('delay_days', e.target.value)}
                  />
                </div>
              </div>
            </section>

            <section className="wi-card">
              <div>
                <h3 className="wi-card-title">Unexpected Expense</h3>
                <p className="wi-card-sub">
                  A one-off cash outflow on a specific date.
                </p>
              </div>

              <div className="wi-fields">
                <div className="wi-field">
                  <label htmlFor="wi-expense-amount" className="wi-label">
                    Expense Amount (₹)
                  </label>
                  <input
                    id="wi-expense-amount"
                    className="wi-input"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
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
                </div>

                <div className="wi-field">
                  <label htmlFor="wi-expense-date" className="wi-label">
                    Expense Date
                  </label>
                  <input
                    id="wi-expense-date"
                    className="wi-input"
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
                </div>
              </div>
            </section>

            <section className="wi-card">
              <div>
                <h3 className="wi-card-title">Additional Income</h3>
                <p className="wi-card-sub">
                  An extra cash inflow expected on a specific date.
                </p>
              </div>

              <div className="wi-fields">
                <div className="wi-field">
                  <label htmlFor="wi-income-amount" className="wi-label">
                    Additional Income (₹)
                  </label>
                  <input
                    id="wi-income-amount"
                    className="wi-input"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
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
                </div>

                <div className="wi-field">
                  <label htmlFor="wi-income-date" className="wi-label">
                    Income Date
                  </label>
                  <input
                    id="wi-income-date"
                    className="wi-input"
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
                </div>
              </div>
            </section>
          </div>

          <div className="wi-actions" style={{ marginTop: '16px' }}>
            <div className="wi-field wi-forecast">
              <label htmlFor="wi-forecast" className="wi-label">
                Forecast Duration
              </label>
              <select
                id="wi-forecast"
                className="wi-input wi-select"
                value={form.forecast_days}
                onChange={e => update('forecast_days', e.target.value)}
              >
                <option value="30">30 Days</option>
                <option value="60">60 Days</option>
                <option value="90">90 Days</option>
              </select>
            </div>

            <button
              type="submit"
              className="wi-submit"
              disabled={loading || loadingInvoices || invoices.length === 0}
            >
              {loading ? 'Running Simulation...' : 'Run Simulation'}
            </button>
          </div>
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
