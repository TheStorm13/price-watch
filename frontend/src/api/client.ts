import { mockApi } from './mockApi'
import type {
  ApiErrorPayload,
  CardHistoryResponse,
  CollectionRun,
  CreateCardInput,
  MarketplaceCard,
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
const apiBaseUrl = isDesktopMode ? 'http://127.0.0.1:8000' : ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
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

  listRuns: (): Promise<CollectionRun[]> =>
    isDemoMode ? mockApi.listRuns() : request('/api/runs?page=1&pageSize=50'),

  startRun: (cardId?: number): Promise<CollectionRun> =>
    isDemoMode
      ? mockApi.startRun(cardId)
      : request('/api/runs', {
          method: 'POST',
          body: JSON.stringify(cardId === undefined ? {} : { cardId }),
        }),

  getRun: (runId: number): Promise<CollectionRun> =>
    isDemoMode ? mockApi.getRun(runId) : request(`/api/runs/${runId}`),

  continueRun: (runId: number): Promise<CollectionRun> =>
    isDemoMode
      ? mockApi.continueRun(runId)
      : request(`/api/runs/${runId}/continue`, { method: 'POST' }),
}

export const apiModeLabel = isDemoMode ? 'Демо-данные' : isDesktopMode ? 'Desktop' : 'API'
