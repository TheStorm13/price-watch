import { useState } from 'react'
import { Star } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { AvailabilityStatus } from '../../components/product/AvailabilityStatus'
import { useUpdateCard } from '../../api/queries'
import type { TrackedCardView, TrackedVariant } from '../../types/domain'
import { formatDateTime, formatPrice } from '../../utils/format'
import { ProductImage } from '../../components/product/ProductImage'
import { sortVariants, variantColor, variantLabel } from './variantDisplay'

export function VariantPanel({ card, variants }: { card: TrackedCardView; variants: TrackedVariant[] }) {
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const mutation = useUpdateCard()
  const matches = sortVariants(variants).filter((v) => `${variantLabel(v)} ${v.externalId}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()))

  async function makePrimary(id: number) {
    setError(null)
    try { await mutation.mutateAsync({ cardId: card.id, input: { primaryVariantId: id } }) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Не удалось выбрать главный вариант') }
  }

  return <section className="variant-section" aria-label="Варианты товара">
    <div className="variant-heading"><div><h2>Варианты товара <Badge variant="secondary">{variants.length}</Badge></h2><p className="text-sm text-muted-foreground">Отслеживаются все варианты. Главный отображается в каталоге.</p></div>
      {variants.length > 4 ? <FieldGroup className="w-full sm:w-[280px]"><Field><FieldLabel className="sr-only" htmlFor="variant-search">Поиск варианта</FieldLabel><Input id="variant-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Название, размер или цвет" /></Field></FieldGroup> : null}
    </div>
    {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
    <div className="variant-table table-surface"><Table>
      <TableHeader><TableRow><TableHead>Вариант</TableHead><TableHead>Цена</TableHead><TableHead>Наличие</TableHead><TableHead>Обновлён</TableHead><TableHead><span className="sr-only">Главный вариант</span></TableHead></TableRow></TableHeader>
      <TableBody>{matches.map((variant) => {
        const primary = variant.id === card.primaryVariantId
        const label = variantLabel(variant)
        return <TableRow key={variant.id} data-primary={primary || undefined}>
          <TableCell><div className="variant-name"><ProductImage card={{ title: label, imageUrl: variant.imageUrl ?? null }} /><span className="variant-color" style={{ backgroundColor: variantColor(variant.externalId) }} /><div><strong>{label}</strong></div></div></TableCell>
          <TableCell className="price-cell">{formatPrice(variant.currentPrice)}</TableCell>
          <TableCell><AvailabilityStatus value={variant.currentAvailability} /></TableCell>
          <TableCell>{formatDateTime(variant.updatedAt)}</TableCell>
          <TableCell>{primary ? <Badge variant="secondary"><Star aria-hidden="true" />Главный</Badge> : <Button variant="outline" size="sm" disabled={mutation.isPending} aria-label={`Сделать главным: ${label}`} onClick={() => void makePrimary(variant.id)}>Сделать главным</Button>}</TableCell>
        </TableRow>
      })}</TableBody>
    </Table>{matches.length === 0 ? <p className="p-4 text-sm text-muted-foreground">Варианты не найдены</p> : null}</div>
  </section>
}
