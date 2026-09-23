import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PriceHistoryPoint } from '../../types/domain'
import { availabilityLabel, formatPrice, formatShortDate } from '../../utils/format'

interface Props {
  history: PriceHistoryPoint[]
  midpoint: number | null
}

export function PriceChart({ history, midpoint }: Props) {
  const data = history.map((point) => ({ ...point, label: formatShortDate(point.observedAt) }))
  if (data.length === 0) return <div className="chart-empty"><strong>Данных за этот период нет</strong><span>Запустите обновление цены, чтобы увидеть динамику.</span></div>
  return (
    <div className="price-chart" aria-label="График истории цены">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 18, right: 16, bottom: 0, left: 8 }}>
          <CartesianGrid stroke="#e4e7ec" vertical={false} />
          <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: '#d0d5dd' }} tick={{ fill: '#667085', fontSize: 12 }} minTickGap={36} />
          <YAxis domain={[0, (dataMax: number) => Math.max(1, dataMax * 1.05)]} tickLine={false} axisLine={false} tick={{ fill: '#667085', fontSize: 12 }} tickFormatter={(value: number) => new Intl.NumberFormat('ru-RU', { notation: 'compact' }).format(value)} width={58} />
          <Tooltip
            contentStyle={{ border: '1px solid #e4e7ec', borderRadius: 8, boxShadow: '0 12px 24px rgba(16,24,40,.10)', fontSize: 13 }}
            formatter={(value) => [formatPrice(Number(value)), 'Цена']}
            labelFormatter={(_, payload) => payload[0]?.payload ? `${new Intl.DateTimeFormat('ru-RU', { dateStyle: 'long', timeStyle: 'short' }).format(new Date(payload[0].payload.observedAt))} · ${availabilityLabel[payload[0].payload.availability as keyof typeof availabilityLabel]}` : ''}
          />
          {midpoint !== null ? <ReferenceLine y={midpoint} stroke="#98a2b3" strokeDasharray="6 5" /> : null}
          <Line type="linear" dataKey="price" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 3, fill: '#fff', strokeWidth: 2 }} activeDot={{ r: 5 }} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
