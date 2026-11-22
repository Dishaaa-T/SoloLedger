// Pure data helpers for the dashboard charts. No React imports here.

const SHORT_MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

const UNCATEGORISED = 'Uncategorised'

/** Coerce a value to a number; null / '' / NaN become 0. */
export function toAmount(value) {
  if (value == null || value === '') return 0
  const amount = Number(value)
  return Number.isNaN(amount) ? 0 : amount
}

/**
 * Return 'YYYY-MM' for an ISO-like date string ('YYYY-MM-DD'), or null.
 * Parsed by string slicing on purpose: new Date('YYYY-MM-DD') is timezone-sensitive.
 */
export function monthKey(isoDate) {
  if (typeof isoDate !== 'string' || !/^\d{4}-\d{2}/.test(isoDate)) return null
  const year = isoDate.slice(0, 4)
  const month = isoDate.slice(5, 7)
  const monthNumber = Number(month)
  if (monthNumber < 1 || monthNumber > 12) return null
  return `${year}-${month}`
}

/** Convert 'YYYY-MM' into a continuous month index for range arithmetic. */
function monthIndex(key) {
  return Number(key.slice(0, 4)) * 12 + (Number(key.slice(5, 7)) - 1)
}

/** Convert a month index back into a 'YYYY-MM' key. */
function keyFromIndex(index) {
  const year = Math.floor(index / 12)
  const month = (index % 12) + 1
  return `${year}-${String(month).padStart(2, '0')}`
}

/**
 * Monthly income (paid invoices, grouped by paid_date) and monthly expenses
 * (all expense records, grouped by expense_date).
 *
 * Decision: 'upcoming' expense records are INCLUDED. They are real stored
 * records with a date, and the same record set feeds the category donut so
 * the two charts' totals match.
 *
 * Range runs from the earliest month with data to the latest month with data,
 * filling gaps with zeros. Nothing is padded beyond the data range, and the
 * current month is not added. If the range exceeds maxMonths, the most recent
 * maxMonths are kept.
 */
export function buildMonthlyPerformance(invoices, expenses, maxMonths = 12) {
  const incomeByMonth = new Map()
  const expensesByMonth = new Map()

  for (const invoice of invoices ?? []) {
    if (invoice?.status !== 'paid') continue
    const key = monthKey(invoice.paid_date)
    if (!key) continue
    incomeByMonth.set(key, (incomeByMonth.get(key) ?? 0) + toAmount(invoice.amount))
  }

  for (const expense of expenses ?? []) {
    const key = monthKey(expense?.expense_date)
    if (!key) continue
    expensesByMonth.set(key, (expensesByMonth.get(key) ?? 0) + toAmount(expense.amount))
  }

  const dataKeys = [...new Set([...incomeByMonth.keys(), ...expensesByMonth.keys()])]
  if (dataKeys.length === 0) {
    return { months: [], maxValue: 0 }
  }

  const indices = dataKeys.map(monthIndex)
  const first = Math.min(...indices)
  const last = Math.max(...indices)

  let rangeIndices = []
  for (let i = first; i <= last; i += 1) rangeIndices.push(i)
  if (rangeIndices.length > maxMonths) {
    rangeIndices = rangeIndices.slice(rangeIndices.length - maxMonths)
  }

  let maxValue = 0
  const months = rangeIndices.map((index) => {
    const key = keyFromIndex(index)
    const income = incomeByMonth.get(key) ?? 0
    const expenseTotal = expensesByMonth.get(key) ?? 0
    maxValue = Math.max(maxValue, income, expenseTotal)
    const year = Math.floor(index / 12)
    const monthNumber = (index % 12) + 1
    return {
      key,
      label: `${SHORT_MONTHS[monthNumber - 1]} ${year}`,
      income,
      expenses: expenseTotal,
    }
  })

  return { months, maxValue }
}

/**
 * Group expenses by trimmed, case-insensitive category.
 * Blank categories become 'Uncategorised'. Zero-amount records are skipped.
 * Percentages are computed against the sum of included amounts.
 */
export function buildExpenseCategoryBreakdown(expenses) {
  const groups = new Map()

  for (const expense of expenses ?? []) {
    const amount = toAmount(expense?.amount)
    if (amount === 0) continue

    const trimmed = typeof expense?.category === 'string' ? expense.category.trim() : ''
    const displayName = trimmed || UNCATEGORISED
    const groupKey = displayName.toLowerCase()

    const existing = groups.get(groupKey)
    if (existing) {
      existing.amount += amount
    } else {
      groups.set(groupKey, { name: displayName, amount })
    }
  }

  const grouped = [...groups.values()]
  const total = grouped.reduce((sum, group) => sum + group.amount, 0)

  const categories = grouped
    .map((group) => ({
      name: group.name,
      amount: group.amount,
      percent: total > 0 ? (group.amount / total) * 100 : 0,
    }))
    .sort((a, b) => b.amount - a.amount)

  return { total, categories }
}

/**
 * Keep the first `limit` categories and fold the rest into 'Other'.
 * Percentages are recomputed against the total of all categories.
 */
export function groupTopCategories(categories, limit = 7) {
  if (!categories || categories.length <= limit) return categories

  const total = categories.reduce((sum, category) => sum + category.amount, 0)
  const top = categories.slice(0, limit)
  const restAmount = categories
    .slice(limit)
    .reduce((sum, category) => sum + category.amount, 0)

  const withPercent = (name, amount) => ({
    name,
    amount,
    percent: total > 0 ? (amount / total) * 100 : 0,
  })

  return [
    ...top.map((category) => withPercent(category.name, category.amount)),
    withPercent('Other', restAmount),
  ]
}

/**
 * Build a CSS conic-gradient string from categories with cumulative percents.
 * Returns '' when there are no categories or the total is 0.
 */
export function buildConicGradient(categories, colors) {
  if (!categories || categories.length === 0 || !colors || colors.length === 0) return ''

  const total = categories.reduce((sum, category) => sum + category.amount, 0)
  if (total === 0) return ''

  let cumulative = 0
  const stops = categories.map((category, index) => {
    const start = cumulative
    cumulative = index === categories.length - 1 ? 100 : cumulative + (category.amount / total) * 100
    const color = colors[index % colors.length]
    return `${color} ${start}% ${cumulative}%`
  })

  return `conic-gradient(${stops.join(', ')})`
}
