import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'

export default function Clients() {
  return (
    <div>
      <PageHeader title="Clients" />
      <EmptyState
        title="No clients yet"
        message="No data yet. Connect the backend to load clients."
      />
    </div>
  )
}
