import type { DisplayItem } from './catalogItems'
import type { TrackedCardView } from '../../types/domain'

export type CatalogRow = { key: string; kind: 'group'; item: Extract<DisplayItem, {kind:'group'}> }
  | { key: string; kind: 'cards'; cards: {card: TrackedCardView; nested: boolean}[] }

export function catalogRows(items: DisplayItem[], members: Map<number, TrackedCardView[]>, collapsed: number[], columns: number): CatalogRow[] {
  const rows: CatalogRow[] = []
  let pending: {card: TrackedCardView; nested: boolean}[] = []
  function flush() {
    if (pending.length) rows.push({ kind:'cards', key:`cards-${pending.map(x=>x.card.id).join('-')}`, cards:pending })
    pending=[]
  }
  function push(card: TrackedCardView, nested: boolean) {
    pending.push({card,nested})
    if(pending.length===columns) flush()
  }
  for(const item of items) {
    if(item.kind==='group') {
      flush()
      rows.push({key:`group-${item.id}`,kind:'group',item})
      if(!collapsed.includes(item.id)) for(const card of members.get(item.id) ?? []) push(card,true)
      flush()
    } else push(item.card,false)
  }
  flush()
  return rows
}
