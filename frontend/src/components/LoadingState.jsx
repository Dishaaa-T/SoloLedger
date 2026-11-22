import { Loader2 } from 'lucide-react'

export default function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-gray-500">
      <Loader2 className="h-6 w-6 animate-spin text-indigo-600" aria-hidden="true" />
      <span className="text-sm">Loading…</span>
    </div>
  )
}
