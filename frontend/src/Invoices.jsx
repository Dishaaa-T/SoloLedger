
import { useEffect, useState } from 'react';
import { api } from './services/api';
import './Invoices.css';

export default function Invoices() {
  const [invoices, setInvoices] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [customerFilter, setCustomerFilter] = useState('all');

  const today = new Date().toLocaleDateString('en-CA');

  const emptyForm = {
    client_id: '',
    invoice_number: '',
    description: '',
    amount: '',
    issue_date: today,
    due_date: today,
  };

  const [form, setForm] = useState(emptyForm);

  async function loadData() {
    try {
      setError('');

      const [invoiceData, customerData] = await Promise.all([
        api.getInvoices(),
        api.getCustomers(),
      ]);

      setInvoices(invoiceData);
      setCustomers(customerData);
    } catch (err) {
      setError(err.message || 'Unable to load invoices.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  function openCreateForm() {
    setEditingId(null);
    setForm(emptyForm);
    setShowForm(true);
  }

  function handleEdit(invoice) {
    setEditingId(invoice.id);
    setForm({
      client_id: String(invoice.client_id),
      invoice_number: invoice.invoice_number,
      description: invoice.description || '',
      amount: String(invoice.amount),
      issue_date: invoice.issue_date,
      due_date: invoice.due_date,
    });
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm);
  }

  async function handleSubmit(e) {
    e.preventDefault();

    try {
      setError('');

      const payload = {
        ...form,
        client_id: Number(form.client_id),
        amount: Number(form.amount),
      };

      if (editingId) {
        await api.updateInvoice(editingId, payload);
      } else {
        await api.addInvoice(payload);
      }

      closeForm();
      await loadData();
    } catch (err) {
      setError(err.message || 'Unable to save invoice.');
    }
  }

  async function handleMarkPaid(id) {
    if (!window.confirm('Mark this invoice as paid?')) return;

    try {
      setError('');
      await api.markPaid(id);
      await loadData();
    } catch (err) {
      setError(err.message || 'Unable to mark invoice as paid.');
    }
  }

  async function handleDelete(id) {
    if (!window.confirm('Are you sure you want to delete this invoice?')) {
      return;
    }

    try {
      setError('');
      await api.deleteInvoice(id);
      await loadData();
    } catch (err) {
      setError(err.message || 'Unable to delete invoice.');
    }
  }

  const filteredInvoices = invoices.filter((invoice) => {
    const matchesStatus =
      statusFilter === 'all' || invoice.status === statusFilter;

    const matchesCustomer =
      customerFilter === 'all' ||
      String(invoice.client_id) === customerFilter;

    return matchesStatus && matchesCustomer;
  });

  const money = (amount) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(Number(amount));

  return (
    <div className="invoices-page">
      <div className="invoices-heading">
        <div>
          <h1>Invoices</h1>
          <p>Create invoices and track student payments.</p>
        </div>

        <button onClick={openCreateForm}>
          + Create Invoice
        </button>
      </div>

      {error && <div className="invoice-error">{error}</div>}

      {showForm && (
        <form className="invoice-form" onSubmit={handleSubmit}>
          <h2>{editingId ? 'Edit Invoice' : 'Create New Invoice'}</h2>

          <label>Customer *</label>
          <select
            name="client_id"
            value={form.client_id}
            onChange={handleChange}
            required
          >
            <option value="">Select customer</option>
            {customers.map((customer) => (
              <option key={customer.id} value={customer.id}>
                {customer.name}
              </option>
            ))}
          </select>

          <label>Invoice Number *</label>
          <input
            name="invoice_number"
            placeholder="INV-001"
            value={form.invoice_number}
            onChange={handleChange}
            required
          />

          <label>Description</label>
          <input
            name="description"
            placeholder="Monthly tuition fees"
            value={form.description}
            onChange={handleChange}
          />

          <label>Amount (₹) *</label>
          <input
            name="amount"
            type="number"
            min="0.01"
            step="0.01"
            placeholder="5000"
            value={form.amount}
            onChange={handleChange}
            required
          />

          <label>Issue Date *</label>
          <input
            name="issue_date"
            type="date"
            value={form.issue_date}
            onChange={handleChange}
            required
          />

          <label>Due Date *</label>
          <input
            name="due_date"
            type="date"
            min={form.issue_date}
            value={form.due_date}
            onChange={handleChange}
            required
          />

          <div className="invoice-form-actions">
            <button type="submit">
              {editingId ? 'Update Invoice' : 'Save Invoice'}
            </button>

            <button
              type="button"
              className="invoice-cancel"
              onClick={closeForm}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="invoice-list">
        <h2>All Invoices ({filteredInvoices.length})</h2>

        <div className="invoice-filters">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="paid">Paid</option>
            <option value="overdue">Overdue</option>
          </select>

          <select
            value={customerFilter}
            onChange={(e) => setCustomerFilter(e.target.value)}
          >
            <option value="all">All Customers</option>
            {customers.map((customer) => (
              <option key={customer.id} value={customer.id}>
                {customer.name}
              </option>
            ))}
          </select>
        </div>

        {loading ? (
          <p>Loading invoices...</p>
        ) : filteredInvoices.length === 0 ? (
          <p>No matching invoices found.</p>
        ) : (
          <div className="invoice-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Customer</th>
                  <th>Description</th>
                  <th>Amount</th>
                  <th>Due Date</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {filteredInvoices.map((invoice) => (
                  <tr key={invoice.id}>
                    <td>#{invoice.invoice_number}</td>
                    <td>{invoice.client?.name || 'Customer'}</td>
                    <td>{invoice.description || '-'}</td>
                    <td>{money(invoice.amount)}</td>
                    <td>{invoice.due_date}</td>

                    <td>
                      <span className={`invoice-status ${invoice.status}`}>
                        {invoice.status}
                      </span>
                    </td>

                    <td>
                      <div className="invoice-actions">
                        <button
                          type="button"
                          className="invoice-edit-btn"
                          onClick={() => handleEdit(invoice)}
                        >
                          Edit
                        </button>

                        {invoice.status !== 'paid' ? (
                          <button
                            type="button"
                            className="mark-paid-btn"
                            onClick={() => handleMarkPaid(invoice.id)}
                          >
                            Mark Paid
                          </button>
                        ) : (
                          <span className="paid-label">✓ Paid</span>
                        )}

                        <button
                          type="button"
                          className="invoice-delete-btn"
                          onClick={() => handleDelete(invoice.id)}
                        >
                          Delete
                        </button>
                      </div>
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
