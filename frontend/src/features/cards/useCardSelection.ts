import { useCallback, useEffect, useState } from 'react'
import type { TrackedCardView } from '../../types/domain'

export function useCardSelection(cards: TrackedCardView[] | undefined) {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => new Set())

  useEffect(() => {
    if (!cards) return
    const existing = new Set(cards.map((card) => card.id))
    setSelectedIds((previous) => {
      if ([...previous].every((id) => existing.has(id))) return previous
      return new Set([...previous].filter((id) => existing.has(id)))
    })
  }, [cards])

  const toggle = useCallback((cardId: number) => {
    setSelectedIds((previous) => {
      const next = new Set(previous)
      if (next.has(cardId)) next.delete(cardId)
      else next.add(cardId)
      return next
    })
  }, [])

  const clearProcessed = useCallback((ids: number[]) => {
    setSelectedIds((previous) => {
      const next = new Set(previous)
      ids.forEach((id) => next.delete(id))
      return next
    })
  }, [])

  const clear = useCallback(() => setSelectedIds(new Set()), [])
  return { selectedIds, toggle, clearProcessed, clear }
}
