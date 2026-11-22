import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'

export default function CashFlow() {
  return (
    <div>
      <PageHeader title="Cash Flow Forecast" />
      <EmptyState
        title="No forecast yet"
        message="No data yet. Connect the backend to load the cash flow forecast."
      />
    </div>
  )
}
