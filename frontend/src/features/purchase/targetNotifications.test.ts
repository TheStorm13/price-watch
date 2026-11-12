import { expect, it } from 'vitest'
import { targetTransitions } from './targetNotifications'
import type { TrackedCardView } from '../../types/domain'
const card = { id: 1, primaryVariantId: 2, targetPrice: '100', currentPrice: '101', currentAvailability: 'in_stock', lastObservedAt: '2026-11-01', lastCollectionRunId: 1 } as TrackedCardView
const below = { ...card, currentPrice: '100', lastObservedAt: '2026-11-02', lastCollectionRunId: 2 }
it('baselines startup and reports only a new crossing, not polling or restart', () => {
  const first = targetTransitions([card], {}, true)
  const reached = targetTransitions([below], first.next)
  expect(reached.notifications).toEqual([below])
  expect(targetTransitions([below], reached.next).notifications).toEqual([])
  expect(targetTransitions([{ ...below, lastCollectionRunId: 3 }], reached.next).notifications).toEqual([])
  const stored = JSON.parse(JSON.stringify(reached.next))
  expect(targetTransitions([below], stored, true).notifications).toEqual([])
  expect(targetTransitions([below], {}, true).notifications).toEqual([])
})
it('rearms above goal or unavailable, and matches return to stock', () => {
  for (const other of [card, { ...card, currentAvailability: 'out_of_stock' as const, currentPrice: null }]) {
    const previous = targetTransitions([other], targetTransitions([below], {}, true).next)
    expect(targetTransitions([below], previous.next).notifications).toEqual([below])
  }
})
it('target edit, creation, enable and primary changes establish a baseline', () => {
  const previous = targetTransitions([card], {}, true).next
  expect(targetTransitions([{ ...below, targetPrice: '102' }], previous).notifications).toEqual([])
  expect(targetTransitions([{ ...below, primaryVariantId: 3 }], previous).notifications).toEqual([])
  expect(targetTransitions([below], {}, false).notifications).toEqual([])
  expect(targetTransitions([below], previous, true).notifications).toEqual([])
  expect(targetTransitions([{ ...below, targetPrice: null }], previous).next).toEqual({})
})
it('only a fresh observation or collection can trigger a notification', () => {
  const previous = targetTransitions([card], {}, true).next
  expect(targetTransitions([{ ...card, currentPrice: '99' }], previous).notifications).toEqual([])
  expect(targetTransitions([{ ...below, currentPrice: null }], previous).notifications).toEqual([])
})
