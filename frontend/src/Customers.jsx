
import { useEffect, useState } from 'react';
import { api } from './services/api';
import './Customers.css';

export default function Customers() {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);

  const emptyForm = {
    name: '',
    email: '',
    phone: '',
    company: '',
    notes: '',
  };

  const [form, setForm] = useState(emptyForm);

  async function loadCustomers() {
    try {
      setError('');
      const data = await api.getCustomers();
      setCustomers(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCustomers();
  }, []);

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  function handleEdit(customer) {
    setEditingId(customer.id);
    setForm({
      name: customer.name || '',
      email: customer.email || '',
      phone: customer.phone || '',
      company: customer.company || '',
      notes: customer.notes || '',
    });
    setShowForm(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();

    try {
      setError('');

      if (editingId) {
        await api.updateCustomer(editingId, form);
      } else {
        await api.addCustomer(form);
      }

      setForm(emptyForm);
      setEditingId(null);
      setShowForm(false);
      await loadCustomers();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(customer) {
    if (!window.confirm(`Delete ${customer.name}?`)) return;

    try {
      setError('');
      await api.deleteCustomer(customer.id);
      await loadCustomers();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="customers-page">
      <div className="customers-heading">
        <div>
          <h1>Customers</h1>
          <p>Manage your students and customer information.</p>
        </div>

        <button onClick={() => {
          setEditingId(null);
          setForm(emptyForm);
          setShowForm(!showForm);
        }}>
          + Add Customer
        </button>
      </div>

      {error && <div className="customer-error">{error}</div>}

      {showForm && (
        <form className="customer-form" onSubmit={handleSubmit}>
          <h2>{editingId ? 'Edit Customer' : 'Add New Customer'}</h2>

          <input name="name" placeholder="Customer name *"
            value={form.name} onChange={handleChange} required />

          <input name="email" type="email" placeholder="Email"
            value={form.email} onChange={handleChange} />

          <input name="phone" placeholder="Phone number"
            value={form.phone} onChange={handleChange} />

          <input name="company" placeholder="Company / School"
            value={form.company} onChange={handleChange} />

          <textarea name="notes" placeholder="Additional notes"
            value={form.notes} onChange={handleChange} />

          <div className="form-actions">
            <button type="submit">
              {editingId ? 'Update Customer' : 'Save Customer'}
            </button>
            <button type="button" className="cancel-btn"
              onClick={() => setShowForm(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="customer-list">
        <h2>All Customers ({customers.length})</h2>

        {loading ? (
          <p>Loading customers...</p>
        ) : customers.length === 0 ? (
          <p>No customers found. Add your first customer!</p>
        ) : (
          <div className="customer-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>Company / School</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {customers.map(customer => (
                  <tr key={customer.id}>
                    <td>{customer.name}</td>
                    <td>{customer.email || '-'}</td>
                    <td>{customer.phone || '-'}</td>
                    <td>{customer.company || '-'}</td>
                    <td>
                      <button className="edit-btn"
                        onClick={() => handleEdit(customer)}>Edit</button>
                      <button className="delete-btn"
                        onClick={() => handleDelete(customer)}>Delete</button>
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
