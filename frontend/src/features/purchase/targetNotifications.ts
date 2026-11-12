import type { TrackedCardView } from '../../types/domain'
import { compareMoney } from '../../utils/money'

interface Checkpoint { target: string; reached: boolean; observation: string | null; runId: number | null }
export type TargetCheckpoints = Record<string, Checkpoint>

/** Pure snapshot transition, shared by the observer and restart/dedup tests. */
export function targetTransitions(cards: TrackedCardView[], previous: TargetCheckpoints, baseline = false) {
  const next: TargetCheckpoints = {}, notifications: TrackedCardView[] = []
  for (const card of cards) {
    if (card.targetPrice == null || card.primaryVariantId == null) continue
    const key = `${card.id}:${card.primaryVariantId}`
    const reached = card.currentAvailability === 'in_stock' && card.currentPrice !== null && compareMoney(card.currentPrice, card.targetPrice) <= 0
    const old = previous[key]
    // Goal changes only establish a baseline; formatting does not change the goal.
    const sameTarget = old && compareMoney(old.target, card.targetPrice) === 0
    const fresh = !old || old.observation !== card.lastObservedAt || old.runId !== (card.lastCollectionRunId ?? null)
    if (!baseline && sameTarget && fresh && !old.reached && reached) notifications.push(card)
    next[key] = { target: card.targetPrice, reached, observation: card.lastObservedAt, runId: card.lastCollectionRunId ?? null }
  }
  return { next, notifications }
}
