import { useEffect, useState, useSyncExternalStore } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { thumbnailConfig } from '../../api/thumbnailConfig'
import type { TrackedCardView } from '../../types/domain'
import { ProductImage } from './ProductImage'

export function CatalogThumbnail({ card }: { card: Pick<TrackedCardView, 'id' | 'title' | 'imageUrl'> }) {
  const revision = useSyncExternalStore(thumbnailConfig.subscribe, thumbnailConfig.snapshot)
  const image = useQuery({
    queryKey: ['thumbnails', revision, card.id, card.imageUrl],
    queryFn: ({ signal }) => api.getThumbnail(card.id, signal),
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
  return <ProductImage card={{ title: card.title, imageUrl: object && object.blob === blob ? object.url : null }} />
}
