import type { DecimalString } from '../utils/money'
export type Marketplace = 'ozon' | 'wildberries' | 'aliexpress' | 'yandex-market'
export type Availability = 'in_stock' | 'out_of_stock' | 'unknown'
export type RunStatus =
  | 'queued'
  | 'running'
  | 'waiting_for_user'
  | 'completed'
  | 'completed_with_errors'
  | 'failed'

export interface TrackedCardView {
  id: number
  marketplace: Marketplace
  externalId: string
  title: string | null
  url: string | null
  imageUrl: string | null
  options?: Record<string, string>
  dealsEnabled: boolean
  primaryVariantId?: number | null
  lastCollectedAt?: string | null
  groupId?: number | null
  tags?: string[]
  currentPrice: DecimalString | null
  minimumPrice?: DecimalString | null
  averagePrice?: DecimalString | null
  currentAvailability: Availability | null
  lastObservedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface TrackedVariant {
  trackingEnabled: boolean
  isTracked: boolean
  imageUrl?: string | null
  productTitle?: string | null
  id: number
  cardId: number
  externalId: string
  title: string
  url: string | null
  options: Record<string, string>
  currentPrice: DecimalString | null
  currentAvailability: Availability | null
  lastObservedAt: string | null
  updatedAt: string | null
}

export interface PriceHistoryPoint {
  variantId?: number | null
  id: number
  cardId: number
  collectionRunId: number | null
  price: DecimalString | null
  availability: Availability
  observedAt: string
}

export interface PriceStatistics {
  cardId: number
  windowStart: string
  windowEnd: string
  averagePrice: DecimalString | null
  minimumPrice: DecimalString | null
  maximumPrice: DecimalString | null
  observationsCount: number
  observedDays: number
}

export interface CardHistoryResponse {
  card: TrackedCardView
  statistics: PriceStatistics
  history: PriceHistoryPoint[]
  page: number
  pageSize: number
  totalCount: number
}

export interface ChartResponse {
  points: PriceHistoryPoint[]
}

export interface RunError {
  variantId?: number | null
  cardId: number | null
  marketplace: Marketplace | null
  externalId: string | null
  at: string
  type: string
  message: string
  traceback: string
}

export interface CollectionRun {
  diagnosticsStatus: 'complete' | 'limited' | 'expired'
  id: number
  status: RunStatus
  totalCount: number
  successCount: number
  failureCount: number
  current: {
    cardId: number
    marketplace: Marketplace
    externalId: string
  } | null
  challenge: {
    type: 'browser_verification'
    message: string
  } | null
  startedAt: string
  finishedAt: string | null
  errors?: RunError[] | null
  retryOfRunId?: number | null
  retryableCount: number
  retryScopeIncomplete: boolean
}

export interface Deal {
  card: TrackedCardView
  averagePrice: DecimalString
  savings: DecimalString
  baselineDays: number
  lastCollectionRunId: number | null
}

export interface CreateCardInput {
  marketplace: Marketplace
  externalId: string
  title?: string
  url?: string
  tags?: string[]
}

export interface UpdateCardInput {
  title?: string | null
  url?: string | null
  dealsEnabled?: boolean
  primaryVariantId?: number | null
  groupId?: number | null
  tags?: string[]
}

export interface ProductGroup {
  id: number
  name: string
  tags?: string[]
  cardIds: number[]
  currentPrice: DecimalString | null
  minimumPrice: DecimalString | null
  representativeCardId: number | null
  representativeCard: TrackedCardView | null
  savings: DecimalString | null
  baselineDays: number
  isDeal: boolean
  hasMemberDeals: boolean
}

export interface GroupInput {
  name: string
  cardIds: number[]
  tags?: string[]
}

export interface TransferHistoryPoint {
  price: string | null
  availability: Availability
  observedAt: string
}

export interface TransferCard {
  marketplace: string
  externalId: string
  title: string | null
  url: string | null
  imageUrl?: string | null
  tags?: string[]
  dealsEnabled: boolean
  createdAt: string
  primaryExternalId: string
  variants: TransferVariant[]
}

export interface TransferVariant {
  trackingEnabled?: boolean
  imageUrl?: string | null
  productTitle?: string | null
  externalId: string
  title?: string
  url: string | null
  options?: Record<string, string>
  updatedAt?: string | null
  history: TransferHistoryPoint[]
}

export interface TransferDocument {
  version: 3
  cards: TransferCard[]
  groups?: { name: string; tags?: string[]; cards: { marketplace: string; externalId: string }[] }[]
}

export interface ImportSummary {
  cardsAdded: number
  cardsMerged: number
  observationsAdded: number
  observationsRemoved: number
  observationsSkipped: number
  groupsAdded?: number
}

export interface ApiErrorPayload {
  error: {
    code: string
    message: string
    field?: string
    requestId?: string
  }
}

export interface CatalogSnapshot {
  cards: TrackedCardView[]
  groups: ProductGroup[]
  deals: Deal[]
}
