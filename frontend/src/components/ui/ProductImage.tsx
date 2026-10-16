import type { MarketplaceCard } from '../../types/domain'

interface Props {
  card: MarketplaceCard
  large?: boolean
}

export function ProductImage({ card, large = false }: Props) {
  return (
    <span className={`product-placeholder${large ? ' product-placeholder--large' : ''}`} aria-hidden="true">
      <span>{(card.title ?? 'Т').slice(0, 1)}</span>
      {card.imageUrl ? (
        <img key={card.imageUrl} src={card.imageUrl} alt="" loading="lazy" referrerPolicy="no-referrer"
          onError={(event) => { event.currentTarget.style.display = 'none' }} />
      ) : null}
    </span>
  )
}
