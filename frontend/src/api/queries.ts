import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { CreateCardInput, UpdateCardInput, GroupInput } from '../types/domain'

export const queryKeys = {
  cards: ['cards'] as const,
  groups: ['groups'] as const,
  card: (id: number) => ['cards', id] as const,
  history: (id: number, days: number, page: number) => ['cards', id, 'history', days, page] as const,
  chart: (id: number, days: number) => ['cards', id, 'chart', days] as const,
  runs: ['runs'] as const,
  deals: ['deals'] as const,
  run: (id: number, includeErrors = false) => ['runs', id, includeErrors] as const,
}

export function useCards() {
  return useQuery({ queryKey: queryKeys.cards, queryFn: api.listCards })
}

export function useGroups() {
  return useQuery({ queryKey: queryKeys.groups, queryFn: api.listGroups })
}

export function useSaveGroup() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id?: number; input: GroupInput }) =>
      id === undefined ? api.createGroup(input) : api.updateGroup(id, input),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.groups })
      client.invalidateQueries({ queryKey: queryKeys.cards })
    },
  })
}

export function useDeleteGroup() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: api.deleteGroup,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.groups })
      client.invalidateQueries({ queryKey: queryKeys.cards })
    },
  })
}

export function useCard(cardId: number) {
  return useQuery({ queryKey: queryKeys.card(cardId), queryFn: () => api.getCard(cardId), enabled: Number.isFinite(cardId) })
}

export function useCardHistory(cardId: number, days: number, page = 1) {
  return useQuery({
    queryKey: queryKeys.history(cardId, days, page),
    queryFn: () => api.getHistory(cardId, days, page),
    enabled: Number.isFinite(cardId),
  })
}

export function useCardChart(cardId: number, days: number) {
  return useQuery({ queryKey: queryKeys.chart(cardId, days), queryFn: () => api.getChart(cardId, days), enabled: Number.isFinite(cardId) })
}

export function useCreateCard() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateCardInput) => api.createCard(input),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.cards }),
  })
}

export function useUpdateCard() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ cardId, input }: { cardId: number; input: UpdateCardInput }) => api.updateCard(cardId, input),
    onSuccess: (card) => {
      client.invalidateQueries({ queryKey: queryKeys.cards })
      client.invalidateQueries({ queryKey: queryKeys.groups })
      client.invalidateQueries({ queryKey: queryKeys.deals })
      client.setQueryData(queryKeys.card(card.id), card)
    },
  })
}

export function useDeleteCard() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (cardId: number) => api.deleteCard(cardId),
    onSuccess: (_result, cardId) => {
      client.removeQueries({ queryKey: queryKeys.card(cardId) })
      client.invalidateQueries({ queryKey: queryKeys.cards })
      client.invalidateQueries({ queryKey: queryKeys.groups })
      client.invalidateQueries({ queryKey: queryKeys.deals })
    },
  })
}

export function useRuns() {
  return useQuery({ queryKey: queryKeys.runs, queryFn: api.listRuns })
}

export function useDeals() {
  return useQuery({ queryKey: queryKeys.deals, queryFn: api.listDeals })
}

export function useRun(runId: number | null, includeErrors = false) {
  return useQuery({
    queryKey: queryKeys.run(runId ?? -1, includeErrors),
    queryFn: () => api.getRun(runId as number, includeErrors),
    enabled: runId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && ['completed', 'completed_with_errors', 'failed'].includes(status) ? false : 1_000
    },
  })
}
