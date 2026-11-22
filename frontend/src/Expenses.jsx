
import { useEffect, useState } from 'react';
import { api } from '../services/api';
import './Expenses.css';

const initialForm = {
  description: '',
  category: 'Teaching Materials',
  amount: '',
  expense_date: new Date().toLocaleDateString('en-CA'),
  status: 'paid',
};

export default function Expenses() {
  const [expenses, setExpenses] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function loadExpenses() {
    try {
      setError('');
      const data = await api.getExpenses();
      setExpenses(data);
    } catch (err) {
      setError(err.message || 'Failed to load expenses.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadExpenses();
  }, []);

  async function addExpense(e) {
    e.preventDefault();

    try {
      setError('');

      const expenseData = {
        title: form.description,
        description: form.description,
        category: form.category,
        amount: Number(form.amount),
        expense_date: form.expense_date,
        status: form.status,
      };

      await api.addExpense(expenseData);
      await loadExpenses();

      setForm(initialForm);
      setShowForm(false);
    } catch (err) {
      setError(err.message || 'Failed to add expense.');
    }
  }

  async function deleteExpense(id) {
    if (!window.confirm('Delete this expense?')) return;

    try {
      setError('');
      await api.deleteExpense(id);
      await loadExpenses();
    } catch (err) {
      setError(err.message || 'Failed to delete expense.');
    }
  }

  const total = expenses.reduce(
    (sum, item) => sum + Number(item.amount || 0), 0
  );

  const money = value =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(value);

  return (
    <div className="expenses-page">
      <div className="expenses-heading">
        <div>
          <h1>Expenses</h1>
          <p>Track your business spending and costs.</p>
        </div>
        <button onClick={() => setShowForm(!showForm)}>
          + Add Expense
        </button>
      </div>

      {error && <p style={{ color: 'red' }}>{error}</p>}

      <div className="expense-summary">
        <span>Total Recorded Expenses</span>
        <h2>{money(total)}</h2>
        <p>{expenses.length} expense records</p>
      </div>

      {showForm && (
        <form className="expense-form" onSubmit={addExpense}>
          <h2>Add New Expense</h2>

          <input
            placeholder="Expense description"
            required
            value={form.description}
            onChange={e =>
              setForm({ ...form, description: e.target.value })
            }
          />

          <select
            value={form.category}
            onChange={e =>
              setForm({ ...form, category: e.target.value })
            }
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
            onChange={e =>
              setForm({ ...form, amount: e.target.value })
            }
          />

          <input
            type="date"
            required
            value={form.expense_date}
            onChange={e =>
              setForm({ ...form, expense_date: e.target.value })
            }
          />

          <select
            value={form.status}
            onChange={e =>
              setForm({ ...form, status: e.target.value })
            }
          >
            <option value="paid">Paid</option>
            <option value="upcoming">Upcoming</option>
          </select>

          <button type="submit">Save Expense</button>

          <button
            type="button"
            className="expense-cancel"
            onClick={() => setShowForm(false)}
          >
            Cancel
          </button>
        </form>
      )}

      <div className="expense-table">
        <h2>Expense History</h2>

        {loading ? (
          <p>Loading expenses...</p>
        ) : expenses.length === 0 ? (
          <p>No expenses recorded. Add your first expense.</p>
        ) : (
          <div className="expense-scroll">
            <table>
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
                      <button
                        className="expense-delete"
                        onClick={() => deleteExpense(item.id)}
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
      </div>
    </div>
  );
}
