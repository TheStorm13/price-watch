import { useMemo } from 'react'
import type { CatalogSnapshot } from '../../types/domain'
import { buildCatalog, prepareCatalog, catalogFilterKey } from './catalogModel'

export function useCatalogModel(snapshot: CatalogSnapshot | undefined, params: URLSearchParams) {
  const deals = useMemo(() => new Map((snapshot?.deals ?? []).map((deal) => [deal.card.id, deal])), [snapshot?.deals])
  const prepared = useMemo(() => prepareCatalog(snapshot, deals), [snapshot, deals])
  const key = catalogFilterKey(params)
  const model = useMemo(() => buildCatalog(prepared, new URLSearchParams(key)), [prepared, key])
  return { ...model, deals }
}
