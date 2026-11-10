import { useState } from 'react'
import { Star } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { AvailabilityStatus } from '../../components/product/AvailabilityStatus'
import { useUpdateCard, useVariantTracking } from '../../api/queries'
import type { TrackedCardView, TrackedVariant } from '../../types/domain'
import { formatDateTime, formatPrice } from '../../utils/format'
import { HelpHint } from '@/components/product/HelpHint'
import { PreparedProductImage } from '../../components/product/PreparedProductImage'
import { sortVariants, variantColor, variantLabel } from './variantDisplay'

export function VariantPanel({ card, variants }: { card: TrackedCardView; variants: TrackedVariant[] }) {
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const mutation = useUpdateCard()
  const tracking = useVariantTracking()
  const busy = mutation.isPending || tracking.isPending
  const matches = sortVariants(variants).filter((v) => `${variantLabel(v)} ${v.externalId}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()))

  async function makePrimary(id: number) {
    setError(null)
    try { await mutation.mutateAsync({ cardId: card.id, input: { primaryVariantId: id } }) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Не удалось выбрать главный вариант') }
  }

  async function setTracking(enabled: boolean, variantId?: number) {
    setError(null)
    try { await tracking.mutateAsync({ cardId: card.id, enabled, variantId }) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Не удалось изменить отслеживание') }
  }

  return <section className="variant-section" aria-label="Варианты товара">
    <div className="variant-heading"><div className="flex items-center gap-1"><h2>Варианты товара <Badge variant="secondary">{variants.length}</Badge></h2><HelpHint label="Варианты товара">Главный вариант обновляется всегда. Включите другие варианты для обновления их цен. При отключении история сохраняется.</HelpHint></div>
      {variants.length > 4 ? <FieldGroup className="w-full sm:w-[280px]"><Field><FieldLabel className="sr-only" htmlFor="variant-search">Поиск варианта</FieldLabel><Input id="variant-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Название, размер или цвет" /></Field></FieldGroup> : null}
    </div>
    <div className="mb-3 flex flex-wrap gap-2">
      <Button variant="outline" size="sm" disabled={busy || variants.every((v) => v.id === card.primaryVariantId || v.trackingEnabled)} onClick={() => void setTracking(true)}>Включить остальные</Button>
      <Button variant="outline" size="sm" disabled={busy || variants.every((v) => v.id === card.primaryVariantId || !v.trackingEnabled)} onClick={() => void setTracking(false)}>Выключить остальные</Button>
    </div>
    {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
    <div className="variant-table table-surface"><Table>
      <TableHeader><TableRow><TableHead>Вариант</TableHead><TableHead>Цена</TableHead><TableHead>Наличие</TableHead><TableHead>Обновлён</TableHead><TableHead>Отслеживание</TableHead><TableHead><span className="sr-only">Главный вариант</span></TableHead></TableRow></TableHeader>
      <TableBody>{matches.map((variant) => {
        const primary = variant.id === card.primaryVariantId
        const label = variantLabel(variant)
        const historical = !primary && ['wildberries', 'aliexpress'].includes(card.marketplace) && !variant.externalId.includes(':')
        return <TableRow key={variant.id} data-primary={primary || undefined}>
          <TableCell><div className="variant-name"><PreparedProductImage card={{ id: card.id, title: label, imageUrl: variant.imageUrl ?? null }} variantId={variant.id} /><span className="variant-color" style={{ backgroundColor: variantColor(variant.externalId) }} /><div><strong title={label}>{label}</strong></div></div></TableCell>
          <TableCell className="price-cell">{formatPrice(variant.currentPrice)}</TableCell>
          <TableCell><AvailabilityStatus value={variant.currentAvailability} /></TableCell>
          <TableCell>{formatDateTime(variant.updatedAt)}</TableCell>
          <TableCell><FieldGroup><Field orientation="horizontal" data-disabled={primary || historical || busy}>
            <Checkbox id={`track-${variant.id}`} aria-label={`Отслеживать: ${label}`} checked={primary || variant.trackingEnabled} disabled={primary || historical || busy} onCheckedChange={(value) => void setTracking(value === true, variant.id)} />
            <FieldLabel htmlFor={`track-${variant.id}`}><span className="sr-only">Отслеживать: {label}</span>{historical ? 'Общая история' : primary ? 'Всегда' : variant.trackingEnabled ? 'Включено' : 'Выключено'}</FieldLabel>
          </Field></FieldGroup></TableCell>
          <TableCell>{primary ? <Badge variant="secondary"><Star aria-hidden="true" />Главный</Badge> : <Button variant="outline" size="sm" disabled={busy || historical} aria-label={`Сделать главным: ${label}`} onClick={() => void makePrimary(variant.id)}>Сделать главным</Button>}</TableCell>
        </TableRow>
      })}</TableBody>
    </Table>{matches.length === 0 ? <p className="p-4 text-sm text-muted-foreground">Варианты не найдены</p> : null}</div>
  </section>
}
