const toneClasses = {
  positive: 'text-emerald-600',
  negative: 'text-rose-600',
  neutral: 'text-gray-900',
}

export default function StatCard({ label, value, tone = 'neutral' }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <p
        className={`mt-2 text-2xl font-bold ${
          toneClasses[tone] ?? toneClasses.neutral
        }`}
      >
        {value}
      </p>
    </div>
  )
}
