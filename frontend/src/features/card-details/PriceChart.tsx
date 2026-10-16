import { CartesianGrid, LabelList, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PriceHistoryPoint } from '../../types/domain'
import { availabilityLabel, formatPrice, formatShortDate } from '../../utils/format'

interface Props {
  history: PriceHistoryPoint[]
  midpoint: number | null
}

export function priceDomain(history: PriceHistoryPoint[]): [number, number] {
  const prices = history.flatMap((point) => point.price === null ? [] : [point.price])
  if (prices.length === 0) return [0, 1]
  const minimum = Math.min(...prices)
  const maximum = Math.max(...prices)
  const padding = maximum === minimum ? Math.max(maximum * 0.1, 1) : (maximum - minimum) * 0.1
  return [Math.max(0, minimum - padding), maximum + padding]
}

export function turningPointIndices(history: PriceHistoryPoint[]): Set<number> {
  const priced = history.flatMap((point, index) => point.price === null ? [] : [{ index, price: point.price }])
  if (priced.length < 2 || priced.every((point) => point.price === priced[0].price)) return new Set()
  const minimum = Math.min(...priced.map((point) => point.price))
  const maximum = Math.max(...priced.map((point) => point.price))
  const candidates = priced.filter((point, position) => {
    const previous = priced[position - 1]
    const next = priced[position + 1]
    return point.price === minimum || point.price === maximum ||
      !!previous && !!next && (point.price > previous.price && point.price > next.price || point.price < previous.price && point.price < next.price)
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

export function PriceChart({ history, midpoint }: Props) {
  const data = history.map((point) => ({ ...point, label: formatShortDate(point.observedAt) }))
  const domain = priceDomain(history)
  const labels = turningPointIndices(history)
  if (data.length === 0) return <div className="chart-empty"><strong>Данных за этот период нет</strong><span>Запустите обновление цены, чтобы увидеть динамику.</span></div>
  return (
    <div className="price-chart" aria-label="График истории цены">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 30, right: 36, bottom: 14, left: 8 }}>
          <CartesianGrid stroke="#e4e7ec" vertical={false} />
          <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: '#d0d5dd' }} tick={{ fill: '#667085', fontSize: 12 }} minTickGap={36} />
          <YAxis domain={domain} tickLine={false} axisLine={false} tick={{ fill: '#667085', fontSize: 12 }} tickFormatter={(value: number) => new Intl.NumberFormat('ru-RU', { notation: 'compact' }).format(value)} width={58} />
          <Tooltip
            contentStyle={{ border: '1px solid #e4e7ec', borderRadius: 8, boxShadow: '0 12px 24px rgba(16,24,40,.10)', fontSize: 13 }}
            formatter={(value) => [formatPrice(Number(value)), 'Цена']}
            labelFormatter={(_, payload) => payload[0]?.payload ? `${new Intl.DateTimeFormat('ru-RU', { dateStyle: 'long', timeStyle: 'short' }).format(new Date(payload[0].payload.observedAt))} · ${availabilityLabel[payload[0].payload.availability as keyof typeof availabilityLabel]}` : ''}
          />
          {midpoint !== null ? <ReferenceLine y={midpoint} stroke="#98a2b3" strokeDasharray="6 5" /> : null}
          <Line type="linear" dataKey="price" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 3, fill: '#fff', strokeWidth: 2 }} activeDot={{ r: 5 }} connectNulls={false} isAnimationActive={false}>
            <LabelList dataKey="price" content={(props) => {
              const index = Number(props.index)
              if (!labels.has(index) || typeof props.x !== 'number' || typeof props.y !== 'number') return null
              const first = index === 0
              const last = index === history.length - 1
              return <text x={props.x + (first ? 12 : last ? -12 : 0)} y={props.y - 12} textAnchor={first ? 'start' : last ? 'end' : 'middle'} fill="#344054" fontSize={11} fontWeight={600}>{formatPrice(history[index].price)}</text>
            }} />
          </Line>
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
