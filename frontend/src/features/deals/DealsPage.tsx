import { Link } from 'react-router-dom'
import { useDeals } from '../../api/queries'
import { AvailabilityStatus } from '../../components/ui/AvailabilityStatus'
import { Button } from '../../components/ui/Button'
import { formatDateTime, formatPrice } from '../../utils/format'

export function DealsPage() {
  const query = useDeals()
  const deals = query.data ?? []
  return <section className="page deals-page">
    <header className="page-header"><div><h1>Выгодные предложения</h1><p>Текущая цена ниже средней за предыдущие дни наблюдений</p></div><Button onClick={() => void query.refetch()}>Обновить</Button></header>
    {query.isLoading ? <div className="state-message">Загрузка предложений…</div> : query.isError ?
      <div className="state-message"><h2>Не удалось загрузить предложения</h2><Button onClick={() => void query.refetch()}>Повторить</Button></div> :
      deals.length === 0 ? <div className="state-message"><h2>Предложений пока нет</h2><p>Здесь появятся товары, которые отслеживаются больше недели и подешевели относительно своей истории.</p></div> :
        <div className="table-surface"><table className="deals-table"><caption className="sr-only">Выгодные предложения</caption><thead><tr><th>Товар</th><th>Текущая цена</th><th>Средняя ранее</th><th>Выгода</th><th>Обновлено</th></tr></thead><tbody>{deals.map((deal) =>
          <tr key={deal.card.id}><td><Link className="text-link" to={`/cards/${deal.card.id}`}>{deal.card.title ?? `ID ${deal.card.externalId}`}</Link><div><AvailabilityStatus value={deal.card.currentAvailability} /></div></td><td className="price-cell">{formatPrice(deal.card.currentPrice)}</td><td>{formatPrice(deal.averagePrice)}</td><td className="deal-savings">{formatPrice(deal.savings)}</td><td>{formatDateTime(deal.card.updatedAt)}</td></tr>)}</tbody></table></div>}
  </section>
}
