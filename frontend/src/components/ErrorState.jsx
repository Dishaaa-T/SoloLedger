import { API_BASE_URL } from '../services/api'

export default function ErrorState({ onRetry }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
      <h3 className="text-base font-semibold text-red-700">
        Backend connection needed
      </h3>
      <p className="mt-2 text-sm text-red-600">
        Could not reach the API at {API_BASE_URL}. Start the FastAPI backend and
        refresh this page.
      </p>
      <button
        type="button"
        onClick={() => onRetry?.()}
        className="mt-4 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
      >
        Retry
      </button>
    </div>
  )
}
