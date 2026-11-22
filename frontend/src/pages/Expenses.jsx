import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'

export default function Expenses() {
  return (
    <div>
      <PageHeader title="Expenses" />
      <EmptyState
        title="No expenses yet"
        message="No data yet. Connect the backend to load expenses."
      />
    </div>
  )
}
