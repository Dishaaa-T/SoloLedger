import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'

export default function Invoices() {
  return (
    <div>
      <PageHeader title="Invoices" />
      <EmptyState
        title="No invoices yet"
        message="No data yet. Connect the backend to load invoices."
      />
    </div>
  )
}
