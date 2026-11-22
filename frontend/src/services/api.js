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

export const getBalance = () => api.get('/settings/balance')

export const getCashflow = (days) =>
  api.get('/forecast/cashflow', { params: { days } })

export const getActionCentre = () => api.get('/action-centre')

export default api
