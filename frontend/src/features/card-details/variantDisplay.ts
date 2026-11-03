import type { TrackedVariant } from '../../types/domain'

export function variantLabel(variant: TrackedVariant) {
  return Object.entries(variant.options).map(([key, value]) => `${key}: ${value}`).join(' · ') || variant.title || `Вариант ${variant.externalId.split(':').at(-1)}`
}

/** Identity-based colors stay stable when variants are filtered or reordered. */
export function variantColor(externalId: string) {
  let hash = 0
  for (const char of externalId) hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  return `hsl(${(hash * 137.508) % 360} 65% 43%)`
}
