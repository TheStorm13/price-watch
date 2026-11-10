import { HelpHint } from '@/components/product/HelpHint'
import { Fragment, memo, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCaption } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import type { Deal, ProductGroup, TrackedCardView } from '../../types/domain'
import { Button } from '@/components/ui/button'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { columnLabels, parseColumnSort, type ColumnSortKey, type DisplayItem } from './catalogItems'
import { catalogRows, type CatalogRow } from './catalogRows'
import { CatalogProduct } from './CatalogProduct'
import { CatalogGroup } from './CatalogGroup'
import { useVirtualRows } from './useVirtualRows'

type Measurements = ReturnType<typeof useVirtualRows>['virtualizer']['measurementsCache']
function endsBlock(next:CatalogRow | undefined) {
 return !(next?.kind==='cards' && next.cards[0]?.nested)
}
const positions = new Map<string,{offset:number;width:number;measurements:Measurements}>()
interface Props {
 sort:string|null;onSort:(value:string)=>void
 view:'list'|'grid';items:DisplayItem[];groupedCards:Map<number,TrackedCardView[]>;deals:Map<number,Deal>
 selectedIds:Set<number>;onSelect:(id:number)=>void;collapsedGroups:number[]
 onToggleGroup:(id:number)=>void;onEditGroup:(group:ProductGroup)=>void;returnTo:string
}
function CatalogColumnHeaders({ sort: value, onSort }: Pick<Props, 'sort' | 'onSort'>) {
 const sort = parseColumnSort(value)
 return <>{(Object.entries(columnLabels) as [ColumnSortKey, string][]).map(([key, label]) => {
   const active = sort?.key === key
   const direction = active && sort.direction === 'asc' ? 'desc' : 'asc'
   const Icon = active ? sort.direction === 'asc' ? ArrowUp : ArrowDown : ArrowUpDown
   return <TableHead key={key} scope="col" className={key !== 'title' ? 'text-center' : undefined}
     aria-sort={active ? sort.direction === 'asc' ? 'ascending' : 'descending' : undefined}>
     <Button variant="ghost" size="sm" className="h-auto max-w-full gap-1 px-0 py-1 text-xs whitespace-normal" aria-label={label} onClick={() => onSort(`${key}-${direction}`)}>
       <span className={cn('min-w-0', key === 'savings' && 'catalog-savings-heading')}>{key === 'savings' ? 'Выгода / макс.' : key === 'minimum' ? 'Мини\u00adмальная' : key === 'marketplace' ? 'Маркет\u00adплейс' : label}</span><Icon aria-hidden="true" className="size-3" />
     </Button>{key === 'savings' ? <HelpHint label="Выгода">Текущая выгода — средняя цена минус текущая, если товар доступен и разница положительна. Максимальная — средняя минус минимальная.</HelpHint> : null}
   </TableHead>
 })}</>
}
// Observe horizontal geometry only; virtual row height changes do not need it.
function observeTableOverflow(element: HTMLElement | null, onChange: (value: boolean) => void) {
 const container=element?.querySelector<HTMLElement>('[data-slot="table-container"]')
 const table=container?.querySelector('table')
 if(!container || !table) {onChange(false);return}
 const widths=new WeakMap<Element,number>()
 const measure=()=>onChange(container.scrollWidth>container.clientWidth+1)
 measure()
 const observer=new ResizeObserver(entries=>{
   let changed=false
   for(const entry of entries) {
     if(widths.get(entry.target)!==entry.contentRect.width) changed=true
     widths.set(entry.target,entry.contentRect.width)
   }
   if(changed) measure()
 })
 observer.observe(container)
 observer.observe(table)
 return ()=>observer.disconnect()
}

export const CatalogResults = memo(function CatalogResults(props:Props) {
 const {view,items,groupedCards,deals,selectedIds,onSelect,collapsedGroups,onToggleGroup,onEditGroup,returnTo}=props
 const [columns,setColumns]=useState(1)
 const [overflow,setOverflow]=useState(false)
 const rows=useMemo(()=>catalogRows(items,groupedCards,collapsedGroups,view==='grid'?columns:1),[items,groupedCards,collapsedGroups,view,columns])
 const keys=useMemo(()=>rows.map(row=>row.key),[rows])
 const saved=useRef(positions.get(location.pathname+location.search))
 const windowed=useVirtualRows(keys,view==='grid'?484:82, saved.current?.width===window.innerWidth?saved.current:undefined,{blockSize:view==='list'?4:1,naturalLimit:view==='list'&&!overflow?100:40})
 const {root,virtualizer,virtual,margin}=windowed
 useLayoutEffect(()=>{if(windowed.width) setColumns(Math.max(1,Math.floor((windowed.width+8)/288)))},[windowed.width])
 // Sticky cells are expensive to paint in WebKit; only pin them when needed.
 useLayoutEffect(()=>observeTableOverflow(root.current,setOverflow),[root,view])
 const current=useRef({returnTo,virtualizer})
 current.current={returnTo,virtualizer}
 useLayoutEffect(()=>{
   const saved=positions.get(location.pathname+location.search)
   if(saved && saved.width===window.innerWidth) {
     requestAnimationFrame(()=>window.scrollTo(0,saved.offset))
   }
   return ()=>{
     const {returnTo:key,virtualizer:v}=current.current
     if(positions.size>=5) positions.delete(positions.keys().next().value!)
     positions.set(key,{offset:window.scrollY,width:window.innerWidth,measurements:[...v.measurementsCache]})
   }
 },[])
 const previousLayout=useRef({view,columns})
 useEffect(()=>{
   if(previousLayout.current.view!==view || previousLayout.current.columns!==columns) virtualizer.measure()
   previousLayout.current={view,columns}
 },[view,columns,virtualizer])
 const rendered=windowed.items
 function content(index:number) {
   const row=rows[index]
   if(row.kind==='group') return <CatalogGroup group={row.item.group} matchingCardCount={row.item.matchingCardCount} view={view} collapsed={collapsedGroups.includes(row.item.id)}
     onToggle={onToggleGroup} onEdit={onEditGroup} index={index} blockEnd={endsBlock(rows[index+1])} measure={virtual && view==='list'?virtualizer.measureElement:undefined} />
   const cards=row.cards.map(({card,nested})=><CatalogProduct key={card.id} card={card} nested={nested} view={view}
     selected={selectedIds.has(card.id)} onToggle={onSelect} savings={deals.get(card.id)?.savings ?? null} returnTo={returnTo}
     index={index} blockEnd={endsBlock(rows[index+1])} measure={virtual && view==='list'?virtualizer.measureElement:undefined} />)
   return view==='list'?cards:<ul className={cn('cards-grid',row.cards[0]?.nested && 'cards-grid--nested')} style={{gridTemplateColumns:`repeat(${columns},280px)`}}>{cards}</ul>
 }
 let last=margin
 const body=rendered.map(item=>{
   const record=rows[item.index]
   const gap=virtual?Math.max(0,item.start-last):0
   last=item.end
   if(view==='grid') return <Fragment key={item.key}>
     {gap>0?<li aria-hidden="true" style={{height:gap}} />:null}
     <li data-index={item.index} data-vrow={item.index} ref={virtual?virtualizer.measureElement:undefined}
       data-group-member={record.kind==='cards' && record.cards[0]?.nested || undefined}
       data-block-end={endsBlock(rows[item.index+1]) || undefined}
       className={rows[item.index].kind==='group'?'cards-grid__group':'virtual-grid-row'}>{content(item.index)}</li>
   </Fragment>
   return <Fragment key={item.key}>{gap>0?<tr aria-hidden="true" className="virtual-spacer"><td colSpan={9} style={{height:gap}} /></tr>:null}{content(item.index)}</Fragment>
 })
 const tail=virtual?Math.max(0,virtualizer.getTotalSize()-(last-margin)):0
 return <div ref={root} onFocusCapture={windowed.focus} onPointerDownCapture={windowed.focus} onBlurCapture={windowed.blur} data-catalog-results data-horizontal-overflow={overflow || undefined}>
   {view==='grid'?<ul className="virtual-grid" data-virtual-start aria-label="Отслеживаемые карточки маркетплейсов">
     {body}{tail>0?<li aria-hidden="true" style={{height:tail}} />:null}
   </ul>:<Table className="cards-table" aria-rowcount={rows.length+1}>
     <TableCaption className="sr-only">Отслеживаемые карточки маркетплейсов</TableCaption>
     <TableHeader><TableRow><TableHead className="cards-table__selection py-0"><span className="sr-only">Выбор</span></TableHead>
       <CatalogColumnHeaders sort={props.sort} onSort={props.onSort} /><TableHead className="text-center"><span className="sr-only">Действия</span></TableHead></TableRow></TableHeader>
     <TableBody data-virtual-start>{body}{tail>0?<tr aria-hidden="true" className="virtual-spacer"><td colSpan={9} style={{height:tail}} /></tr>:null}</TableBody>
   </Table>}
 </div>
})
