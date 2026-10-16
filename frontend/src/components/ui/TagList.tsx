export function TagList({ tags }: { tags?: string[] }) {
  if (!tags?.length) return null
  return <span className="tag-list">{tags.map((tag) => <span className="tag" key={tag}>{tag}</span>)}</span>
}
