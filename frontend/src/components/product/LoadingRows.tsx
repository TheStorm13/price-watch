import { Skeleton } from '../ui/skeleton'

export function LoadingRows({ count = 6 }: { count?: number }) {
  return (
    <div className="loading-rows" aria-label="Загрузка">
      {Array.from({ length: count }, (_, index) => (
        <div className="loading-row" key={index}>
          <Skeleton className="h-8" />
          <Skeleton className="h-3" />
          <Skeleton className="h-3" />
          <Skeleton className="h-3" />
        </div>
      ))}
    </div>
  )
}
