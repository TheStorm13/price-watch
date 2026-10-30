import type { Availability, Marketplace, RunStatus } from '../types/domain'

export { formatMoney as formatPrice } from './money'

const dateTimeFormatter = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
const shortDateFormatter = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' })
const relativeFormatter = new Intl.RelativeTimeFormat('ru', { numeric: 'auto' })

export const formatDateTime = (value: string | null | undefined) =>
  value ? dateTimeFormatter.format(new Date(value)) : '—'

export const formatShortDate = (value: string) =>
  shortDateFormatter.format(new Date(value))

export function formatRelativeTime(value: string | null): string {
  if (!value) return 'Нет данных'
  const seconds = Math.max(0, Math.round((Date.now() - Date.parse(value)) / 1000))
  const formatter = relativeFormatter
  if (seconds < 60) return formatter.format(-seconds, 'second')
  if (seconds < 3_600) return formatter.format(-Math.round(seconds / 60), 'minute')
  if (seconds < 86_400) return formatter.format(-Math.round(seconds / 3_600), 'hour')
  return formatter.format(-Math.round(seconds / 86_400), 'day')
}

export const availabilityLabel: Record<Availability, string> = {
  in_stock: 'В наличии',
  out_of_stock: 'Нет в наличии',
  unknown: 'Неизвестно',
}

export const marketplaceLabel: Record<Marketplace, string> = {
  ozon: 'Ozon',
  wildberries: 'Wildberries',
  aliexpress: 'AliExpress',
  'yandex-market': 'Яндекс Маркет',
}

export const runStatusLabel: Record<RunStatus, string> = {
  queued: 'В очереди',
  running: 'Выполняется',
  waiting_for_user: 'Требуется проверка',
  completed: 'Завершён',
  completed_with_errors: 'Завершён с ошибками',
  failed: 'Ошибка',
}

export function formatDuration(startedAt: string, finishedAt: string | null) {
  const end = finishedAt ? Date.parse(finishedAt) : Date.now()
  const seconds = Math.max(0, Math.round((end - Date.parse(startedAt)) / 1000))
  if (seconds < 60) return `${seconds} сек.`
  return `${Math.floor(seconds / 60)} мин. ${seconds % 60} сек.`
}
