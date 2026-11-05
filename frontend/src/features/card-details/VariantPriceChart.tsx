import { useMemo, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription } from '@/components/ui/empty'
import type { PriceHistoryPoint, TrackedVariant } from '../../types/domain'
import { formatPrice, formatShortDate } from '../../utils/format'
import { sortVariants, variantColor, variantLabel } from './variantDisplay'
import { priceDomain } from './priceDomain'

interface Props { history: PriceHistoryPoint[]; variants: TrackedVariant[]; primaryVariantId?: number | null }
const dateLabel = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })
const priceLabel = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })

export function VariantPriceChart({ history, variants, primaryVariantId }: Props) {
  const [hidden, setHidden] = useState<Set<number>>(() => new Set(variants.filter((v) => v.id !== (primaryVariantId ?? variants[0]?.id)).map((v) => v.id)))
  const series = useMemo(() => {
    const byId = new Map<number, PriceHistoryPoint[]>()
    for (const point of history) {
      if (point.variantId == null) continue
      const points = byId.get(point.variantId) ?? []
      points.push(point)
      byId.set(point.variantId, points)
    }
    return sortVariants(variants).map((v) => ({ variant: v, data: (byId.get(v.id) ?? [])
      .toSorted((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt) || a.id - b.id)
      .map((p) => ({ ...p, time: Date.parse(p.observedAt), value: p.price === null || p.availability === 'out_of_stock' ? null : Number(p.price) })) }))
  }, [history, variants])
  const visiblePoints = history.filter((p) => p.variantId != null && !hidden.has(p.variantId))
  const domain = priceDomain(visiblePoints)
  const times = [...new Set(visiblePoints.map((p) => Date.parse(p.observedAt)))].sort((a,b) => a-b)
  const ticks = times.filter((_time,index) => index % Math.max(1,Math.ceil(times.length/6)) === 0 || index === times.length-1)

  return <div className="variant-chart-section">
    <div className="variant-legend" aria-label="Варианты на графике">{series.map(({ variant: v }) => <label key={v.id} className="variant-legend-item">
      <Checkbox checked={!hidden.has(v.id)} onCheckedChange={(checked) => setHidden((current) => {
        const next = new Set(current)
        if (checked) next.delete(v.id); else next.add(v.id)
        return next
      })} aria-label={`Показать на графике: ${variantLabel(v)}`} />
      <span className="variant-color" style={{ backgroundColor: variantColor(v.externalId) }} />
      <span>{variantLabel(v)}{v.id === primaryVariantId ? ' · главный' : ''}</span>
    </label>)}{hidden.size ? <Button size="sm" variant="ghost" onClick={() => setHidden(new Set())}>Показать все</Button> : null}</div>
    {visiblePoints.length === 0 ? <Empty className="min-h-[250px]"><EmptyHeader><EmptyTitle>{history.length ? hidden.size === variants.length ? 'Все линии скрыты' : 'Нет измерений выбранных вариантов' : 'Пока нет измерений'}</EmptyTitle><EmptyDescription>{history.length ? 'Включите варианты в легенде.' : 'Обновите товар, чтобы сравнить цены его вариантов.'}</EmptyDescription></EmptyHeader></Empty> :
      <div className="price-chart" aria-label="График цен вариантов товара">
        <ResponsiveContainer width="100%" height="100%"><LineChart margin={{ top: 20, right: 24, bottom: 14, left: 8 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis ticks={ticks} type="number" dataKey="time" domain={['dataMin', 'dataMax']} tickFormatter={(time: number) => formatShortDate(new Date(time).toISOString())} tickLine={false} minTickGap={48} tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }} />
          <YAxis type="number" domain={domain} width={76} allowDecimals={false} tickFormatter={(price: number) => priceLabel.format(price)} tickLine={false} axisLine={false} tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }} />
          <Tooltip labelFormatter={(time) => typeof time === 'number' ? dateLabel.format(new Date(time)) : ''} formatter={(_value, name, entry) => [formatPrice(entry.payload.price), name]} contentStyle={{ background: 'var(--popover)', color: 'var(--popover-foreground)', border: '1px solid var(--border)', borderRadius: 8 }} />
          {series.filter(({ variant }) => !hidden.has(variant.id)).map(({ variant, data }) => <Line key={variant.id} data={data} name={variantLabel(variant)} type="linear" dataKey="value" stroke={variantColor(variant.externalId)} strokeWidth={variant.id === primaryVariantId ? 3 : 2} dot={{ r: 3 }} activeDot={{ r: 5 }} connectNulls={false} isAnimationActive={false} />)}
        </LineChart></ResponsiveContainer>
      </div>}
  </div>
}
