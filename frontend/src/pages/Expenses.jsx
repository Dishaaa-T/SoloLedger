
import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import { getExpenses, addExpense, deleteExpense } from '../services/api'

export default function Expenses() {
  const [expenses, setExpenses] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)

  const [form, setForm] = useState({
    description: '',
    category: 'Teaching Materials',
    amount: '',
    expense_date: new Date().toLocaleDateString('en-CA'),
    status: 'paid',
  })

  const loadExpenses = async () => {
    try {
      setError('')
      const response = await getExpenses()
      setExpenses(response.data)
    } catch (err) {
      setError('Unable to load expenses. Check backend connection.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadExpenses()
  }, [])

  const handleAdd = async (e) => {
    e.preventDefault()

    try {
      await addExpense({
        title: form.description,
        description: form.description,
        category: form.category,
        amount: Number(form.amount),
        expense_date: form.expense_date,
        status: form.status,
      })

      setForm({
        description: '',
        category: 'Teaching Materials',
        amount: '',
        expense_date: new Date().toLocaleDateString('en-CA'),
        status: 'paid',
      })

      setShowForm(false)
      await loadExpenses()
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to add expense.')
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this expense?')) return

    try {
      await deleteExpense(id)
      await loadExpenses()
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to delete expense.')
    }
  }

  const money = (value) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(value)

  const total = expenses.reduce(
    (sum, item) => sum + Number(item.amount || 0), 0
  )

  return (
    <div>
      <PageHeader title="Expenses" />

      <div style={{ padding: '24px' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px'
        }}>
          <div>
            <h2>Expense Management</h2>
            <p>Track your business spending and costs.</p>
          </div>

          <button onClick={() => setShowForm(!showForm)}>
            + Add Expense
          </button>
        </div>

        {error && <p style={{ color: 'red' }}>{error}</p>}

        <div style={{
          background: 'white',
          padding: '20px',
          borderRadius: '12px',
          marginBottom: '24px'
        }}>
          <p>Total Recorded Expenses</p>
          <h2>{money(total)}</h2>
          <p>{expenses.length} expense records</p>
        </div>

        {showForm && (
          <form onSubmit={handleAdd} style={{
            background: 'white',
            padding: '20px',
            borderRadius: '12px',
            marginBottom: '24px',
            display: 'grid',
            gap: '12px'
          }}>
            <h3>Add New Expense</h3>

            <input
              placeholder="Expense description"
              required
              value={form.description}
              onChange={e => setForm({
                ...form, description: e.target.value
              })}
            />

            <select
              value={form.category}
              onChange={e => setForm({
                ...form, category: e.target.value
              })}
            >
              <option>Teaching Materials</option>
              <option>Rent</option>
              <option>Electricity</option>
              <option>Internet</option>
              <option>Transportation</option>
              <option>Other</option>
            </select>

            <input
              type="number"
              min="0.01"
              step="0.01"
              placeholder="Amount in ₹"
              required
              value={form.amount}
              onChange={e => setForm({
                ...form, amount: e.target.value
              })}
            />

            <input
              type="date"
              required
              value={form.expense_date}
              onChange={e => setForm({
                ...form, expense_date: e.target.value
              })}
            />

            <select
              value={form.status}
              onChange={e => setForm({
                ...form, status: e.target.value
              })}
            >
              <option value="paid">Paid</option>
              <option value="upcoming">Upcoming</option>
            </select>

            <button type="submit">Save Expense</button>

            <button type="button" onClick={() => setShowForm(false)}>
              Cancel
            </button>
          </form>
        )}

        <div style={{
          background: 'white',
          padding: '20px',
          borderRadius: '12px',
          overflowX: 'auto'
        }}>
          <h3>Expense History</h3>

          {loading ? (
            <p>Loading expenses...</p>
          ) : expenses.length === 0 ? (
            <EmptyState
              title="No expenses yet"
              message="Add your first expense to get started."
            />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th>Description</th>
                  <th>Category</th>
                  <th>Date</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>

              <tbody>
                {expenses.map(item => (
                  <tr key={item.id}>
                    <td>{item.description || item.title}</td>
                    <td>{item.category}</td>
                    <td>{item.expense_date}</td>
                    <td>{money(Number(item.amount))}</td>
                    <td>{item.status}</td>
                    <td>
                      <button onClick={() => handleDelete(item.id)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
