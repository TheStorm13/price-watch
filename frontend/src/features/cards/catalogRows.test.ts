import { expect, it } from 'vitest'
import { catalogRows } from './catalogRows'
import type { DisplayItem } from './catalogItems'
import type { TrackedCardView } from '../../types/domain'

it('splits large groups into bounded visual rows and retains every member once',()=>{
  const cards=Array.from({length:5000},(_,id)=>({id}) as TrackedCardView)
  const group={kind:'group',id:1,group:{id:1}} as DisplayItem
  const rows=catalogRows([group],new Map([[1,cards]]),[],4)
  expect(rows[0].kind).toBe('group')
  expect(rows.slice(1).every(row=>row.kind==='cards' && row.cards.length<=4)).toBe(true)
  expect(rows.flatMap(row=>row.kind==='cards'?row.cards.map(x=>x.card.id):[])).toEqual(cards.map(x=>x.id))
  expect(catalogRows([group],new Map([[1,cards]]),[1],4)).toHaveLength(1)
})
