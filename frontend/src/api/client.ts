export type ThumbnailProfile = 'list' | 'tile' | 'detail'
import { thumbnailConfig } from './thumbnailConfig'
import { mockApi } from './mockApi'
import type {
  ApiErrorPayload,
  CatalogSnapshot,
  CardHistoryResponse,
  ChartResponse,
  CollectionRun,
  CreateCardInput,
  TrackedCardView,
  TrackedVariant,
  TransferDocument,
  ImportSummary,
  UpdateCardInput,
  ProductGroup,
  GroupInput,
} from '../types/domain'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code = 'unknown_error',
    readonly field?: string,
  ) {
    super(message)
  }
}

export const isE2ETestMode = import.meta.env.VITE_E2E_TEST_MODE === 'true'
export const isDesktopMode = import.meta.env.VITE_DESKTOP_MODE === 'true'

export interface DesktopApiConfig {
  baseUrl: string
  token: string | null
}

let desktopApiConfig: DesktopApiConfig | null = null

export function configureDesktopApi(config: DesktopApiConfig) {
  const changed = desktopApiConfig?.baseUrl !== config.baseUrl || desktopApiConfig?.token !== config.token
  desktopApiConfig = config
  if (changed) thumbnailConfig.changed()
  return changed
}

async function request<T>(path: string, init?: RequestInit, binary = false): Promise<T> {
  if (!desktopApiConfig) {
    throw new Error('Локальный API ещё не запущен')
  }
  const response = await fetch(`${desktopApiConfig.baseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(desktopApiConfig?.token ? { 'X-Price-Watch-Token': desktopApiConfig.token } : {}),
      ...init?.headers,
    },
  })
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiErrorPayload | null
    throw new ApiError(
      payload?.error.message ?? 'Не удалось выполнить запрос',
      payload?.error.code,
      payload?.error.field,
    )
  }
  if (binary) return response.blob() as Promise<T>
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  getThumbnail: (cardId: number, options: { profile: ThumbnailProfile; scale: number; variantId?: number }, signal?: AbortSignal): Promise<Blob> => {
    const params = new URLSearchParams({ profile: options.profile, scale: String(options.scale) })
    if (options.variantId !== undefined) params.set('variantId', String(options.variantId))
    return isE2ETestMode ? mockApi.getThumbnail(cardId, options.profile, options.scale, options.variantId) : request(`/api/cards/${cardId}/thumbnail?${params}`, { signal }, true)
  },
  getCatalog: (signal?: AbortSignal): Promise<CatalogSnapshot> =>
    isE2ETestMode ? mockApi.getCatalog() : request('/api/catalog', { signal }),
  createGroup: (input: GroupInput): Promise<ProductGroup> =>
    isE2ETestMode ? mockApi.createGroup(input) : request('/api/groups', { method: 'POST', body: JSON.stringify(input) }),
  updateGroup: (id: number, input: GroupInput): Promise<ProductGroup> =>
    isE2ETestMode ? mockApi.updateGroup(id, input) : request(`/api/groups/${id}`, { method: 'PUT', body: JSON.stringify(input) }),
  deleteGroup: (id: number): Promise<void> =>
    isE2ETestMode ? mockApi.deleteGroup(id) : request(`/api/groups/${id}`, { method: 'DELETE' }),
  exportCards: (): Promise<TransferDocument> =>
    isE2ETestMode ? mockApi.exportCards() : request('/api/cards/export'),

  previewImportCards: (document: TransferDocument): Promise<ImportSummary> =>
    isE2ETestMode ? mockApi.previewImportCards(document) : request('/api/cards/import/preview', {
      method: 'POST', body: JSON.stringify(document),
    }),

  importCards: (document: TransferDocument): Promise<ImportSummary> =>
    isE2ETestMode ? mockApi.importCards(document) : request('/api/cards/import', {
      method: 'POST', body: JSON.stringify(document),
    }),

  setVariantTracking: (cardId: number, enabled: boolean, variantId?: number): Promise<TrackedVariant[]> =>
    isE2ETestMode ? mockApi.setVariantTracking(cardId, enabled, variantId) : request(`/api/cards/${cardId}/variant-tracking`, {
      method: 'PATCH', body: JSON.stringify({ enabled, variantId }),
    }),

  getVariants: (cardId: number): Promise<TrackedVariant[]> =>
    isE2ETestMode ? mockApi.getVariants(cardId) : request(`/api/cards/${cardId}/variants`),

  getCard: (cardId: number): Promise<TrackedCardView> =>
    isE2ETestMode ? mockApi.getCard(cardId) : request(`/api/cards/${cardId}`),

  createCard: (input: CreateCardInput): Promise<TrackedCardView> =>
    isE2ETestMode
      ? mockApi.createCard(input)
      : request('/api/cards', { method: 'POST', body: JSON.stringify(input) }),

  updateCard: (cardId: number, input: UpdateCardInput): Promise<TrackedCardView> =>
    isE2ETestMode
      ? mockApi.updateCard(cardId, input)
      : request(`/api/cards/${cardId}`, { method: 'PATCH', body: JSON.stringify(input) }),

  deleteCard: (cardId: number): Promise<void> =>
    isE2ETestMode
      ? mockApi.deleteCard(cardId)
      : request(`/api/cards/${cardId}`, { method: 'DELETE' }),

  getHistory: (cardId: number, days: number, page = 1, pageSize = 50, variantId?: number): Promise<CardHistoryResponse> =>
    isE2ETestMode
      ? mockApi.getHistory(cardId, days, page, pageSize, variantId)
      : request(`/api/cards/${cardId}/history?days=${days}&page=${page}&pageSize=${pageSize}${variantId === undefined ? '' : `&variantId=${variantId}`}`),

  getChart: (cardId: number, days: number): Promise<ChartResponse> =>
    isE2ETestMode ? mockApi.getChart(cardId, days) : request(`/api/cards/${cardId}/chart?days=${days}`),

  listRuns: (): Promise<CollectionRun[]> =>
    isE2ETestMode ? mockApi.listRuns() : request('/api/runs?page=1&pageSize=50'),

  startRun: (cardId?: number): Promise<CollectionRun> =>
    isE2ETestMode
      ? mockApi.startRun(cardId)
      : request('/api/runs', {
          method: 'POST',
          body: JSON.stringify(cardId === undefined ? {} : { cardId }),
        }),

  getRun: (runId: number, includeErrors = false): Promise<CollectionRun> =>
    isE2ETestMode ? mockApi.getRun(runId, includeErrors) : request(`/api/runs/${runId}?includeErrors=${includeErrors}`),

  continueRun: (runId: number): Promise<CollectionRun> =>
    isE2ETestMode
      ? mockApi.continueRun(runId)
      : request(`/api/runs/${runId}/continue`, { method: 'POST' }),

  retryRun: (runId: number): Promise<CollectionRun> =>
    isE2ETestMode ? mockApi.retryRun(runId) : request(`/api/runs/${runId}/retry`, { method: 'POST' }),
}

export const apiModeLabel = isE2ETestMode ? 'Тестовые данные' : 'Desktop'
