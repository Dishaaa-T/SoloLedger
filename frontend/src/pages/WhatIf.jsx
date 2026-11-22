import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'

export default function WhatIf() {
  return (
    <div>
      <PageHeader title="What-If Simulator" />
      <EmptyState
        title="No scenarios yet"
        message="No data yet. Connect the backend to run what-if scenarios."
      />
    </div>
  )
}
