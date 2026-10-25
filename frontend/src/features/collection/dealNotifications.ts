import { compareMoney, priceText } from '../../utils/money'
import type { CatalogSnapshot } from '../../types/domain'

export const NOTIFICATIONS_KEY = 'price-watch-deal-notifications'
const OLD_PRICES = 'price-watch-notified-prices'
const OLD_RUN = 'price-watch-notified-run'
interface State { version: 2; pending: number[]; processed: number; prices: Record<string, string | null> }
const validId = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) > 0

/** Durable work is independent of the currently displayed collection panel. */
export class DealNotifications {
  private state: State
  private active = false
  private generation = 0
  private busy = false
  private attempts = 0
  private timer: ReturnType<typeof setTimeout> | undefined

  constructor(private storage: Storage, private fetchCatalog: () => Promise<CatalogSnapshot>, private notify: (count: number) => void) {
    this.state = { version: 2, pending: [], processed: 0, prices: {} }
    try {
      const value = JSON.parse(storage.getItem(NOTIFICATIONS_KEY) ?? 'null')
      if ([1, 2].includes(value?.version) && Array.isArray(value.pending) && Number.isSafeInteger(value.processed)
          && value.processed >= 0) {
        this.state = { version: 2, pending: [...new Set<number>(value.pending.filter(validId))].filter((id) => id > value.processed),
          processed: value.processed, prices: this.prices(value.prices) }
      } else {
        const oldId = Number(storage.getItem(OLD_RUN))
        this.state.processed = validId(oldId) ? oldId : 0
        this.state.prices = this.prices(JSON.parse(storage.getItem(OLD_PRICES) ?? '{}'))
      }
      storage.setItem(NOTIFICATIONS_KEY, JSON.stringify(this.state))
      storage.removeItem(OLD_PRICES)
      storage.removeItem(OLD_RUN)
    } catch { /* Invalid or unavailable storage starts an in-memory queue. */ }
  }

  private prices(value: unknown): Record<string, string | null> {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
    return Object.fromEntries(Object.entries(value).flatMap<[string, string | null]>(([key, price]) => {
      if (price === null) return [[key, null]]
      const text = typeof price === 'number' && Number.isFinite(price) ? String(price) : price
      if (typeof text !== 'string') return []
      try {
        if (compareMoney(text, '0') < 0 || compareMoney(text, '1000000000000') >= 0) return []
        return [[key, priceText(text)]]
      } catch { return [] }
    }))
  }
  private persist() {
    try { this.storage.setItem(NOTIFICATIONS_KEY, JSON.stringify(this.state)) } catch { /* Keep pending work in memory. */ }
  }
  enqueue(id: number) {
    if (!validId(id) || id <= this.state.processed || this.state.pending.includes(id)) return
    this.state.pending.push(id)
    this.state.pending.sort((a, b) => a - b)
    this.persist()
    this.schedule(0)
  }
  start() { if (this.active) return; this.active = true; this.generation += 1; this.schedule(0) }
  stop() {
    this.active = false
    this.generation += 1
    this.busy = false
    clearTimeout(this.timer)
    this.timer = undefined
  }
  private schedule(delay: number) {
    if (!this.active || this.busy || this.timer !== undefined || !this.state.pending.length) return
    this.timer = setTimeout(() => { this.timer = undefined; void this.process() }, delay)
  }
  private async process() {
    const generation = this.generation
    const pending = [...this.state.pending]
    this.busy = true
    let delay = 0
    try {
      const catalog = await this.fetchCatalog()
      if (!this.active || generation !== this.generation) return
      const fresh = catalog.deals.filter((deal) => deal.lastCollectionRunId !== null && pending.includes(deal.lastCollectionRunId)
        && this.state.prices[String(deal.card.id)] !== (deal.card.currentPrice === null ? null : priceText(deal.card.currentPrice)))
      this.state = { version: 2, pending: this.state.pending.filter((id) => !pending.includes(id)),
        processed: Math.max(this.state.processed, ...pending),
        prices: Object.fromEntries(catalog.deals.map((deal) => [deal.card.id, deal.card.currentPrice === null ? null : priceText(deal.card.currentPrice)])) }
      this.persist()
      this.attempts = 0
      if (fresh.length) this.notify(fresh.length)
    } catch {
      delay = Math.min(30_000, 1_000 * 2 ** Math.min(this.attempts++, 5))
    } finally {
      if (this.active && generation === this.generation) { this.busy = false; this.schedule(delay) }
    }
  }
}
