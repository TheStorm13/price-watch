export function LoadingRows({ count = 6 }: { count?: number }) {
  return (
    <div className="loading-rows" aria-label="Загрузка">
      {Array.from({ length: count }, (_, index) => (
        <div className="loading-row" key={index}>
          <span className="skeleton skeleton--wide" />
          <span className="skeleton" />
          <span className="skeleton" />
          <span className="skeleton" />
        </div>
      ))}
    </div>
  )
}
