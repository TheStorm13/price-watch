import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { catalogOptions, usePurchaseSettings } from '../../api/queries'
import { targetTransitions, type TargetCheckpoints } from './targetNotifications'
import { notifyTarget } from './notificationTransport'
import { formatPrice } from '../../utils/format'
import { Alert, AlertDescription } from '@/components/ui/alert'

/** Mounted above routes; catalog polling also sees collections started elsewhere. */
export function TargetNotificationObserver() {
  const settings = usePurchaseSettings()
  const catalog = useQuery({ ...catalogOptions, refetchInterval: settings.data?.targetNotificationsEnabled ? 5000 : false, refetchIntervalInBackground: true })
  const state = useRef<{ instance: string; enabled: boolean; points: TargetCheckpoints } | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (!settings.data || !catalog.data) return
    const { instanceId, targetNotificationsEnabled: enabled } = settings.data
    // Never baseline cached data while an invalidated catalog is being refreshed.
    if (catalog.isFetching || catalog.data.instanceId !== instanceId) return
    const old = state.current
    const baseline = !old || old.instance !== instanceId || !old.enabled || !enabled
    const { next, notifications } = targetTransitions(catalog.data.cards, old?.instance === instanceId ? old.points : {}, baseline)
    state.current = { instance: instanceId, enabled, points: next }
    // Checkpoint before transport: failed/denied delivery must not create a retry loop.
    try { localStorage.setItem(`price-watch-target-notifications-v1:${instanceId}`, JSON.stringify(next)) }
    catch { setError('Не удалось сохранить состояние уведомлений. При перезапуске будет создана новая точка отсчёта.') }
    if (!enabled) return
    for (const card of notifications) {
      void notifyTarget('Достигнута целевая цена', `${card.title ?? card.externalId}: ${formatPrice(card.currentPrice)}, цель ${formatPrice(card.targetPrice)}`)
        .catch(reason => setError(`Не удалось отправить уведомление: ${String(reason)}`))
    }
  }, [settings.data, catalog.data, catalog.isFetching])
  return error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null
}
