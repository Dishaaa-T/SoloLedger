import { Inbox } from 'lucide-react'

export default function EmptyState({ title, message }) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-gray-200 bg-gray-50 px-6 py-12 text-center">
      <Inbox className="mb-3 h-10 w-10 text-gray-400" aria-hidden="true" />
      <h3 className="text-base font-semibold text-gray-700">{title}</h3>
      {message && <p className="mt-1 text-sm text-gray-500">{message}</p>}
    </div>
  )
}
