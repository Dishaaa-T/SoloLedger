import { BrowserRouter, Route, Routes } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import Dashboard from './pages/Dashboard'
import Clients from './pages/Clients'
import Invoices from './pages/Invoices'
import Expenses from './pages/Expenses'
import CashFlow from './pages/CashFlow'
import WhatIf from './pages/WhatIf'
import ActionCentre from './pages/ActionCentre'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="/clients" element={<Clients />} />
          <Route path="/invoices" element={<Invoices />} />
          <Route path="/expenses" element={<Expenses />} />
          <Route path="/cash-flow" element={<CashFlow />} />
          <Route path="/what-if" element={<WhatIf />} />
          <Route path="/action-centre" element={<ActionCentre />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
