import type { TrackedVariant } from '../../types/domain'

export function variantLabel(variant: TrackedVariant) {
  return Object.entries(variant.options).map(([key, value]) => `${key}: ${value}`).join(' · ') || variant.title || 'Без названия'
}

const variantNames = new Intl.Collator('ru', { numeric: true, sensitivity: 'base' })

export function sortVariants(variants: TrackedVariant[]) {
  return variants.toSorted((a, b) => variantNames.compare(variantLabel(a), variantLabel(b)))
}

/** Identity-based colors stay stable when variants are filtered or reordered. */
export function variantColor(externalId: string) {
  let hash = 0
  for (const char of externalId) hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  return `hsl(${(hash * 137.508) % 360} 65% 43%)`
}
