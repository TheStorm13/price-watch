import { mockApi } from './mockApi'
import type {
  ApiErrorPayload,
  CardHistoryResponse,
  ChartResponse,
  CollectionRun,
  CreateCardInput,
  Deal,
  MarketplaceCard,
  TransferDocument,
  ImportSummary,
  UpdateCardInput,
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

export const isDemoMode = import.meta.env.VITE_DEMO_MODE === 'true'
export const isDesktopMode = import.meta.env.VITE_DESKTOP_MODE === 'true'

export interface DesktopApiConfig {
  baseUrl: string
  token: string | null
}

let desktopApiConfig: DesktopApiConfig | null = null

export function configureDesktopApi(config: DesktopApiConfig) {
  desktopApiConfig = config
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (isDesktopMode && !desktopApiConfig) {
    throw new Error('Локальный API ещё не запущен')
  }
  const apiBaseUrl = isDesktopMode ? desktopApiConfig!.baseUrl : ''
  const response = await fetch(`${apiBaseUrl}${path}`, {
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
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  exportCards: (): Promise<TransferDocument> =>
    isDemoMode ? mockApi.exportCards() : request('/api/cards/export'),

  previewImportCards: (document: TransferDocument): Promise<ImportSummary> =>
    isDemoMode ? mockApi.previewImportCards(document) : request('/api/cards/import/preview', {
      method: 'POST', body: JSON.stringify(document),
    }),

  importCards: (document: TransferDocument): Promise<ImportSummary> =>
    isDemoMode ? mockApi.importCards(document) : request('/api/cards/import', {
      method: 'POST', body: JSON.stringify(document),
    }),

  listCards: (): Promise<MarketplaceCard[]> =>
    isDemoMode ? mockApi.listCards() : request('/api/cards'),

  getCard: (cardId: number): Promise<MarketplaceCard> =>
    isDemoMode ? mockApi.getCard(cardId) : request(`/api/cards/${cardId}`),

  createCard: (input: CreateCardInput): Promise<MarketplaceCard> =>
    isDemoMode
      ? mockApi.createCard(input)
      : request('/api/cards', { method: 'POST', body: JSON.stringify(input) }),

  updateCard: (cardId: number, input: UpdateCardInput): Promise<MarketplaceCard> =>
    isDemoMode
      ? mockApi.updateCard(cardId, input)
      : request(`/api/cards/${cardId}`, { method: 'PATCH', body: JSON.stringify(input) }),

  deleteCard: (cardId: number): Promise<void> =>
    isDemoMode
      ? mockApi.deleteCard(cardId)
      : request(`/api/cards/${cardId}`, { method: 'DELETE' }),

  getHistory: (cardId: number, days: number, page = 1, pageSize = 50): Promise<CardHistoryResponse> =>
    isDemoMode
      ? mockApi.getHistory(cardId, days, page, pageSize)
      : request(`/api/cards/${cardId}/history?days=${days}&page=${page}&pageSize=${pageSize}`),

  getChart: (cardId: number, days: number): Promise<ChartResponse> =>
    isDemoMode ? mockApi.getChart(cardId, days) : request(`/api/cards/${cardId}/chart?days=${days}`),

  listDeals: (): Promise<Deal[]> =>
    isDemoMode ? mockApi.listDeals() : request('/api/cards/deals'),

  listRuns: (): Promise<CollectionRun[]> =>
    isDemoMode ? mockApi.listRuns() : request('/api/runs?page=1&pageSize=50'),

  startRun: (cardId?: number): Promise<CollectionRun> =>
    isDemoMode
      ? mockApi.startRun(cardId)
      : request('/api/runs', {
          method: 'POST',
          body: JSON.stringify(cardId === undefined ? {} : { cardId }),
        }),

  getRun: (runId: number, includeErrors = false): Promise<CollectionRun> =>
    isDemoMode ? mockApi.getRun(runId, includeErrors) : request(`/api/runs/${runId}?includeErrors=${includeErrors}`),

  continueRun: (runId: number): Promise<CollectionRun> =>
    isDemoMode
      ? mockApi.continueRun(runId)
      : request(`/api/runs/${runId}/continue`, { method: 'POST' }),

  retryRun: (runId: number): Promise<CollectionRun> =>
    isDemoMode ? mockApi.retryRun(runId) : request(`/api/runs/${runId}/retry`, { method: 'POST' }),
}

export const apiModeLabel = isDemoMode ? 'Демо-данные' : isDesktopMode ? 'Desktop' : 'API'
