
import axios from 'axios'

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

export const getDashboardSummary = (period) =>
  api.get('/dashboard/summary', { params: { period } })

export const getClients = () => api.get('/clients')

export const getInvoices = () => api.get('/invoices')

export const getExpenses = () => api.get('/expenses')

export const addExpense = (data) => api.post('/expenses', data)

export const deleteExpense = (id) => api.delete(`/expenses/${id}`)

export const getBalance = () => api.get('/settings/balance')

export const getCashflow = (days) =>
  api.get('/forecast/cashflow', { params: { days } })

export const getActionCentre = () => api.get('/action-centre')

export const getClientPaymentRisk = (clientId, invoiceAmount) =>
  api.get(`/clients/${clientId}/payment-risk`, {
    params: invoiceAmount ? { invoice_amount: invoiceAmount } : {},
  })

export const createClient = (data) => api.post('/clients', data)

export const updateClient = (id, data) => api.put(`/clients/${id}`, data)

export const deleteClient = (id) => api.delete(`/clients/${id}`)


export const runWhatIf = (data) =>
  api.post('/simulator/what-if', data)

// Named export
export { api }

// Default export
export default api
