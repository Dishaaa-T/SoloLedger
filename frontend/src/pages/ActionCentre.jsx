import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'

export default function ActionCentre() {
  return (
    <div>
      <PageHeader title="Action Centre" />
      <EmptyState
        title="No actions yet"
        message="No data yet. Connect the backend to load your action centre."
      />
    </div>
  )
}
