import { useMemo } from 'react'
import type { CatalogSnapshot } from '../../types/domain'
import { buildCatalog } from './catalogModel'

export function useCatalogModel(snapshot: CatalogSnapshot | undefined, params: URLSearchParams) {
  const deals = useMemo(() => new Map((snapshot?.deals ?? []).map((deal) => [deal.card.id, deal])), [snapshot?.deals])
  const model = useMemo(() => buildCatalog(snapshot, params, deals), [snapshot, params, deals])
  return { ...model, deals }
}
