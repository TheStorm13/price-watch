import { Badge } from '../ui/badge'

export function TagList({ tags }: { tags?: string[] }) {
  if (!tags?.length) return null
  return <span className="tag-list">{tags.map((tag) => <Badge variant="tag" className="tag" key={tag} title={tag}>{tag}</Badge>)}</span>
}
