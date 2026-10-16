import type { MarketplaceCard } from '../../types/domain'

interface Props {
  card: MarketplaceCard
  large?: boolean
  alt?: string
  eager?: boolean
}

export function ProductImage({ card, large = false, alt, eager = false }: Props) {
  return (
    <span className={`product-placeholder${large ? ' product-placeholder--large' : ''}${card.imageUrl ? ' product-placeholder--with-image' : ''}`} aria-hidden={alt ? undefined : true}>
      <span>{(card.title ?? 'Т').slice(0, 1)}</span>
      {card.imageUrl ? (
        <img key={card.imageUrl} src={card.imageUrl} alt={alt ?? ''} loading={eager ? 'eager' : 'lazy'} referrerPolicy="no-referrer"
          onError={(event) => {
            event.currentTarget.style.display = 'none'
            event.currentTarget.parentElement?.classList.remove('product-placeholder--with-image')
          }} />
      ) : null}
    </span>
  )
}
