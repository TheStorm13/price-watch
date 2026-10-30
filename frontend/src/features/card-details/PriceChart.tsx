import { memo, useMemo } from 'react'
import { compareMoney, type DecimalString } from '../../utils/money'
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription } from '@/components/ui/empty'
import { CartesianGrid, LabelList, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PriceHistoryPoint } from '../../types/domain'
import { availabilityLabel, formatPrice, formatShortDate } from '../../utils/format'

const compactPrice = new Intl.NumberFormat('ru-RU', { notation: 'compact' })
const tooltipDate = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'long', timeStyle: 'short' })

interface Props {
  history: PriceHistoryPoint[]
  midpoint: DecimalString | null
}

export function priceDomain(history: PriceHistoryPoint[]): [number, number] {
  const prices = history.flatMap((point) => point.price === null ? [] : [Number(point.price)])
  if (prices.length === 0) return [0, 1]
  let minimum = Infinity, maximum = -Infinity
  for (const price of prices) { minimum = Math.min(minimum, price); maximum = Math.max(maximum, price) }
  const padding = maximum === minimum ? Math.max(maximum * 0.1, 1) : (maximum - minimum) * 0.1
  return [Math.max(0, minimum - padding), maximum + padding]
}

export function turningPointIndices(history: PriceHistoryPoint[]): Set<number> {
  const priced = history.flatMap((point, index) => point.price === null ? [] : [{ index, price: point.price }])
  if (priced.length < 2 || priced.every((point) => point.price === priced[0].price)) return new Set()
  let minimum = priced[0].price, maximum = priced[0].price
  for (const point of priced) {
    if (compareMoney(point.price, minimum) < 0) minimum = point.price
    if (compareMoney(point.price, maximum) >= 0) maximum = point.price
  }
  const candidates = priced.filter((point, position) => {
    const previous = priced[position - 1]
    const next = priced[position + 1]
    return point.price === minimum || point.price === maximum ||
      !!previous && !!next && (compareMoney(point.price, previous.price) > 0 && compareMoney(point.price, next.price) > 0 || compareMoney(point.price, previous.price) < 0 && compareMoney(point.price, next.price) < 0)
  })
  const spacing = Math.max(2, Math.ceil(history.length / 7))
  const selected: number[] = []
  for (const point of candidates.sort((a, b) => {
    const aGlobal = a.price === minimum || a.price === maximum ? 1 : 0
    const bGlobal = b.price === minimum || b.price === maximum ? 1 : 0
    return bGlobal - aGlobal || a.index - b.index
  })) {
    if (selected.length >= 6) break
    if (selected.every((index) => Math.abs(index - point.index) >= spacing)) selected.push(point.index)
  }
  return new Set(selected)
}

export const PriceChart = memo(function PriceChart({ history, midpoint }: Props) {
  const data = useMemo(() => history.map((point) => ({ ...point, plotPrice: point.price === null ? null : Number(point.price), label: formatShortDate(point.observedAt) })), [history])
  const domain = useMemo(() => priceDomain(history), [history])
  const labels = useMemo(() => turningPointIndices(history), [history])
  if (data.length === 0) return <Empty className="mb-8 h-[250px]"><EmptyHeader><EmptyTitle>Данных за этот период нет</EmptyTitle><EmptyDescription>Запустите обновление цены, чтобы увидеть динамику.</EmptyDescription></EmptyHeader></Empty>
  return (
    <div className="price-chart" aria-label="График истории цены">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 30, right: 36, bottom: 14, left: 8 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: 'var(--input)' }} tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }} minTickGap={36} />
          <YAxis domain={domain} tickLine={false} axisLine={false} tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }} tickFormatter={(value: number) => compactPrice.format(value)} width={58} />
          <Tooltip
            contentStyle={{ border: '1px solid var(--border)', borderRadius: 8, boxShadow: '0 12px 24px rgba(16,24,40,.10)', fontSize: 13 }}
            formatter={(_value, _name, item) => [formatPrice(item.payload.price), 'Цена']}
            labelFormatter={(_, payload) => payload[0]?.payload ? `${tooltipDate.format(new Date(payload[0].payload.observedAt))} · ${availabilityLabel[payload[0].payload.availability as keyof typeof availabilityLabel]}` : ''}
          />
          {midpoint !== null ? <ReferenceLine y={Number(midpoint)} stroke="var(--muted-foreground)" strokeDasharray="6 5" /> : null}
          <Line type="linear" dataKey="plotPrice" stroke="var(--primary)" strokeWidth={2.5} dot={{ r: 3, fill: 'var(--background)', strokeWidth: 2 }} activeDot={{ r: 5 }} connectNulls={false} isAnimationActive={false}>
            <LabelList dataKey="plotPrice" content={(props) => {
              const index = Number(props.index)
              if (!labels.has(index) || typeof props.x !== 'number' || typeof props.y !== 'number') return null
              const first = index === 0
              const last = index === history.length - 1
              return <text x={props.x + (first ? 12 : last ? -12 : 0)} y={props.y - 12} textAnchor={first ? 'start' : last ? 'end' : 'middle'} fill="var(--foreground)" fontSize={11} fontWeight={600}>{formatPrice(history[index].price)}</text>
            }} />
          </Line>
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
})
