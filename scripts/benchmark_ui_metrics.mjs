export function percentile(values, fraction) {
  if (!values.length || values.some(value => !Number.isFinite(value) || value < 0)) throw new Error('Invalid timing samples')
  return values.toSorted((a, b) => a - b)[Math.ceil(values.length * fraction) - 1]
}

export function budgets(summary, baseline) {
  if (baseline && Object.keys(summary).some(name => !baseline[name])) throw new Error('Incomplete baseline actions')
  return Object.fromEntries(Object.entries(summary).map(([name, timing]) => {
    const before = baseline?.[name]?.p95
    const limit = before > 200 ? before * .7 : 200
    return [name, { p95: timing.p95, baselineP95: before ?? null, limit, passed: timing.p95 <= limit,
      changePercent: before ? (timing.p95 / before - 1) * 100 : null }]
  }))
}
