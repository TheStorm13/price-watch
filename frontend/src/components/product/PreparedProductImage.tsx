import { useEffect, useState, useSyncExternalStore } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type ThumbnailProfile } from '../../api/client'
import { thumbnailConfig } from '../../api/thumbnailConfig'
import type { TrackedCardView } from '../../types/domain'
import { ProductImage } from './ProductImage'
import { useThumbnailScale } from './useThumbnailScale'

interface Props {
  card: Pick<TrackedCardView, 'id' | 'title' | 'imageUrl'>
  profile?: ThumbnailProfile
  variantId?: number
  alt?: string
  eager?: boolean
}

export function PreparedProductImage({ card, profile = 'list', variantId, alt, eager }: Props) {
  const revision = useSyncExternalStore(thumbnailConfig.subscribe, thumbnailConfig.snapshot)
  const scale = useThumbnailScale()
  const image = useQuery({
    queryKey: ['thumbnails', revision, card.id, card.imageUrl, variantId, profile, scale],
    queryFn: ({ signal }) => api.getThumbnail(card.id, { profile, scale, variantId }, signal),
    enabled: Boolean(card.imageUrl),
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
    retry: false,
  })
  const blob = card.imageUrl ? image.data : undefined
  const [object, setObject] = useState<{ blob: Blob; url: string } | null>(null)
  useEffect(() => {
    if (!blob) return
    const url = URL.createObjectURL(blob)
    setObject({ blob, url })
    return () => URL.revokeObjectURL(url)
  }, [blob])
  return <ProductImage large={profile === 'tile'} alt={alt} eager={eager} card={{ title: card.title, imageUrl: object && object.blob === blob ? object.url : null }} />
}
