import { useState } from 'react'
import { useCatalog, useUpdateCard } from '../../api/queries'
import type { TrackedCardView } from '../../types/domain'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Field, FieldGroup, FieldLabel, FieldDescription } from '@/components/ui/field'
import { Alert, AlertDescription } from '@/components/ui/alert'

export function TargetPriceForm({ card }: { card: TrackedCardView }) {
  const save = useUpdateCard()
  const catalog = useCatalog()
  const assessment = catalog.data?.cards.find(item => item.id === card.id)?.purchaseAssessment
  const [value, setValue] = useState(card.targetPrice ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  return <section className="target-price-panel" aria-label="Целевая цена">
    <form onSubmit={async event => {
      event.preventDefault(); setError(null); setSaved(false)
      try { await save.mutateAsync({ cardId: card.id, input: { targetPrice: value.trim() ? value.replace(',', '.') : null } }); setSaved(true) }
      catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)) }
    }}><FieldGroup>
      <Field data-invalid={!!error}><FieldLabel htmlFor="target-price">Куплю за, ₽</FieldLabel>
        <Input aria-invalid={!!error} disabled={save.isPending} id="target-price" inputMode="decimal" value={value} onChange={e => { setValue(e.target.value); setSaved(false) }} />
        <FieldDescription>Цена для главного варианта. Звезда появится, когда товар в наличии и стоит не больше этой суммы. Очистите поле, чтобы убрать цель.</FieldDescription>
      </Field>
      {!assessment?.historyEligible ? <FieldDescription>Для условий по диапазону и доле выгоды нужна история больше 30 дней. Целевая цена работает сразу.</FieldDescription> : null}
      <Button variant="outline" type="submit" disabled={save.isPending}>Сохранить целевую цену</Button>
      {saved ? <p role="status">Целевая цена сохранена</p> : null}
      {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
    </FieldGroup></form>
  </section>
}
