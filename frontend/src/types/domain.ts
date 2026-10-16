export type Marketplace = 'ozon' | 'wildberries' | 'aliexpress'
export type Availability = 'in_stock' | 'out_of_stock' | 'unknown'
export type RunStatus =
  | 'queued'
  | 'running'
  | 'waiting_for_user'
  | 'completed'
  | 'completed_with_errors'
  | 'failed'

export interface MarketplaceCard {
  id: number
  marketplace: Marketplace
  externalId: string
  title: string | null
  url: string | null
  imageUrl: string | null
  isActive: boolean
  groupId?: number | null
  currentPrice: number | null
  minimumPrice?: number | null
  averagePrice?: number | null
  currentAvailability: Availability | null
  lastObservedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface PriceHistoryPoint {
  id: number
  cardId: number
  collectionRunId: number | null
  price: number | null
  availability: Availability
  observedAt: string
}

export interface PriceStatistics {
  cardId: number
  days: number
  averagePrice: number | null
  minimumPrice: number | null
  maximumPrice: number | null
  observationsCount: number
  observedDays: number
}

export interface CardHistoryResponse {
  card: MarketplaceCard
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
  cardId: number | null
  marketplace: Marketplace | null
  externalId: string | null
  at: string
  type: string
  message: string
  traceback: string
}

export interface CollectionRun {
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
}

export interface Deal {
  card: MarketplaceCard
  averagePrice: number
  savings: number
  baselineDays: number
  lastCollectionRunId: number | null
}

export interface CreateCardInput {
  marketplace: Marketplace
  externalId: string
  title?: string
  url?: string
}

export interface UpdateCardInput {
  title?: string | null
  url?: string | null
  isActive?: boolean
  groupId?: number | null
}

export interface ProductGroup {
  id: number
  name: string
  cardIds: number[]
  currentPrice: number | null
  minimumPrice: number | null
}

export interface GroupInput {
  name: string
  cardIds: number[]
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
  isActive: boolean
  createdAt: string
  history: TransferHistoryPoint[]
}

export interface TransferDocument {
  version: 1
  cards: TransferCard[]
  groups?: { name: string; cards: { marketplace: string; externalId: string }[] }[]
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
