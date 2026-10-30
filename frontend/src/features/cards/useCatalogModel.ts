import { useMemo } from 'react'
import type { CatalogSnapshot, TrackedCardView } from '../../types/domain'
import { cardItem, catalogItems, compareItems, matchesItem, type Sort } from './catalogItems'
const collator = new Intl.Collator('ru', { numeric: true, sensitivity: 'base' })
export function useCatalogModel(snapshot: CatalogSnapshot | undefined, deferredQuery: string, marketplace: string, status: string, selectedTag: string, dealsOnly: boolean, sort: Sort) {
  const deals = useMemo(() => new Map((snapshot?.deals ?? []).map((deal) => [deal.card.id, deal])), [snapshot?.deals])
  const allItems = useMemo(() => catalogItems(snapshot?.cards ?? [], snapshot?.groups ?? [], deals),
    [snapshot?.cards, snapshot?.groups, deals])
  const availableTags = useMemo(() => [...new Set(allItems.flatMap((item) => item.card?.tags ?? []))].sort(collator.compare), [allItems])

  const orderedItems = useMemo(() => allItems.filter((item) => matchesItem(item, {
    query: deferredQuery, marketplace, status, tag: selectedTag, dealsOnly,
  })).toSorted((left, right) => compareItems(left, right, sort)),
  [allItems, deferredQuery, marketplace, status, selectedTag, dealsOnly, sort])

  const groupedCards = useMemo(() => {
    const byGroup = new Map<number, TrackedCardView[]>()
    for (const card of snapshot?.cards ?? []) {
      if (card.groupId == null) continue
      const members = byGroup.get(card.groupId) ?? []
      members.push(card)
      byGroup.set(card.groupId, members)
    }
    for (const members of byGroup.values()) members.sort((left, right) =>
      compareItems(cardItem(left, deals), cardItem(right, deals), sort))
    return byGroup
  }, [snapshot?.cards, deals, sort])

 return { deals, allItems, availableTags, orderedItems, groupedCards }
}
