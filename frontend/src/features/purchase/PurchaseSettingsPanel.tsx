import { useState } from 'react'
import { usePurchaseSettings, useUpdatePurchaseSettings } from '../../api/queries'
import type { PurchaseSettings } from '../../types/domain'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldGroup, FieldLabel, FieldDescription } from '@/components/ui/field'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ensureNotificationPermission } from './notificationTransport'

export function PurchaseSettingsPanel() {
  const query = usePurchaseSettings()
  const [saved, setSaved] = useState(false)
  if (query.isPending) return <p>Загрузка условий покупки…</p>
  if (query.isError) return <Alert variant="destructive"><AlertDescription>Не удалось загрузить условия покупки.<Button variant="outline" onClick={() => void query.refetch()}>Повторить</Button></AlertDescription></Alert>
  return <><SettingsForm key={JSON.stringify(query.data)} settings={query.data} onSaved={() => setSaved(true)} onEdit={() => setSaved(false)} />{saved ? <p role="status">Условия покупки сохранены</p> : null}</>
}

function SettingsForm({ settings, onSaved, onEdit }: { settings: PurchaseSettings; onSaved: () => void; onEdit: () => void }) {
  const save = useUpdatePurchaseSettings()
  const [rangeOn, setRangeOn] = useState(settings.smallRangeTolerance !== null)
  const [range, setRange] = useState(settings.smallRangeTolerance ?? '')
  const [shareOn, setShareOn] = useState(settings.historicalSavingsShare !== null)
  const [share, setShare] = useState(settings.historicalSavingsShare ?? '')
  const [notify, setNotify] = useState(settings.targetNotificationsEnabled)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  return <form className="w-full max-w-3xl" onChange={onEdit} onSubmit={async event => {
    event.preventDefault(); setError(null); setPending(true)
    try {
      if (notify && !await ensureNotificationPermission()) throw new Error('Разрешение ОС на уведомления не получено. Условия покупки продолжают работать.')
      await save.mutateAsync({ smallRangeTolerance: rangeOn ? range.replace(',', '.') : null,
        historicalSavingsShare: shareOn ? share.replace(',', '.') : null, targetNotificationsEnabled: notify })
      onSaved()
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)) }
    finally { setPending(false) }
  }}>
    <FieldGroup>
      <Field orientation="horizontal"><Checkbox disabled={pending} id="purchase-range-on" checked={rangeOn} onCheckedChange={value => setRangeOn(value === true)} /><FieldLabel htmlFor="purchase-range-on">Небольшие колебания цены</FieldLabel></Field>
      <Field data-invalid={!!error} data-disabled={!rangeOn}>
        <FieldLabel htmlFor="purchase-range">Допустимая разница, ₽</FieldLabel>
        <Input aria-invalid={!!error} id="purchase-range" inputMode="decimal" disabled={!rangeOn || pending} required={rangeOn} value={range} onChange={e => setRange(e.target.value)} />
        <FieldDescription>Если разница между максимумом и минимумом не больше этой суммы, товар можно покупать без ожидания. Например, диапазон 315–340 ₽ подходит при пороге 50 ₽. Нужна история больше 30 дней.</FieldDescription>
      </Field>
      <Field orientation="horizontal"><Checkbox disabled={pending} id="purchase-share-on" checked={shareOn} onCheckedChange={value => setShareOn(value === true)} /><FieldLabel htmlFor="purchase-share-on">Доля максимальной выгоды</FieldLabel></Field>
      <Field data-invalid={!!error} data-disabled={!shareOn}>
        <FieldLabel htmlFor="purchase-share">Доля выгоды, %</FieldLabel>
        <Input aria-invalid={!!error} id="purchase-share" inputMode="decimal" disabled={!shareOn || pending} required={shareOn} value={share} onChange={e => setShare(e.target.value)} />
        <FieldDescription>Какая часть пути от средней цены к минимуму вас устраивает: от 0 до 100%, не включая 0. При средней 1000 ₽ и минимуме 800 ₽ порог 70% означает цену 860 ₽ или ниже. Это не скидка 70% от средней. Нужна история больше 30 дней.</FieldDescription>
      </Field>
      <FieldDescription>Минимум, максимум и средняя по времени берутся за последние два года. Звезда появляется, когда выполнено хотя бы одно условие. Целевую цену можно задать в карточке товара — для неё месяц истории не нужен.</FieldDescription>
      <Field orientation="horizontal"><Checkbox disabled={pending} id="purchase-notify" checked={notify} onCheckedChange={value => setNotify(value === true)} /><FieldLabel htmlFor="purchase-notify">Уведомлять о достижении целевой цены</FieldLabel></Field>
      <FieldDescription>Системные уведомления работают, пока приложение запущено, в том числе в трее. После включения уведомляем только о новых достижениях цели. В демо доставка в ОС не выполняется.</FieldDescription>
      {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
      <Button type="submit" disabled={pending}>{pending ? 'Сохранение…' : 'Сохранить условия'}</Button>
    </FieldGroup>
  </form>
}
