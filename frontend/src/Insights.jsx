
import { useEffect, useState } from 'react';
import { api } from './services/api';
import './Insights.css';

export default function Insights() {
  const [customers, setCustomers] = useState([]);
  const [invoices, setInvoices] = useState([]);

  useEffect(() => {
    Promise.all([api.getCustomers(), api.getInvoices()])
      .then(([c, i]) => {
        setCustomers(c);
        setInvoices(i);
      })
      .catch(console.error);
  }, []);

  const pending = invoices.filter(i => i.status === 'pending');
  const overdue = invoices.filter(i => i.status === 'overdue');

  const money = amount =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(amount);

  const pendingAmount = pending.reduce((s, i) => s + Number(i.amount), 0);
  const overdueAmount = overdue.reduce((s, i) => s + Number(i.amount), 0);

  return (
    <div className="insights-page">
      <h1>Business Insights</h1>
      <p>Understand your business performance at a glance.</p>

      <div className="insights-grid">
        <div className="insight-card">
          <h3>Total Customers</h3>
          <h2>{customers.length}</h2>
          <p>Registered customers</p>
        </div>

        <div className="insight-card">
          <h3>Total Invoices</h3>
          <h2>{invoices.length}</h2>
          <p>Invoices created</p>
        </div>

        <div className="insight-card">
          <h3>Pending Payments</h3>
          <h2>{money(pendingAmount)}</h2>
          <p>{pending.length} pending invoices</p>
        </div>

        <div className="insight-card">
          <h3>Overdue Payments</h3>
          <h2>{money(overdueAmount)}</h2>
          <p>{overdue.length} overdue invoices</p>
        </div>
      </div>

      <div className="insight-recommendations">
        <h2>Business Recommendations</h2>
        {overdue.length > 0 && (
          <p>⚠ Follow up on {overdue.length} overdue invoice(s).</p>
        )}
        {pending.length > 0 && (
          <p>💰 Contact customers regarding pending payments.</p>
        )}
        {customers.length === 0 && (
          <p>👥 Add customers to start managing your business.</p>
        )}
        {overdue.length === 0 && pending.length === 0 && customers.length > 0 && (
          <p>✓ Great! No pending or overdue invoices.</p>
        )}
        <p>📊 Keep recording invoices and expenses to monitor performance.</p>
      </div>
    </div>
  );
}
