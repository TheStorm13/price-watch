import { Fragment, memo, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ArrowDown, ArrowUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCaption } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import type { Deal, ProductGroup, TrackedCardView } from '../../types/domain'
import { columnLabels, type ColumnSortKey, type DisplayItem, type Sort } from './catalogItems'
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
 view:'list'|'grid';items:DisplayItem[];groupedCards:Map<number,TrackedCardView[]>;deals:Map<number,Deal>
 selectedIds:Set<number>;onSelect:(id:number)=>void;collapsedGroups:number[]
 onToggleGroup:(id:number)=>void;onEditGroup:(group:ProductGroup)=>void;sort:Sort;onSort:(key:ColumnSortKey)=>void;returnTo:string
}
export const CatalogResults = memo(function CatalogResults(props:Props) {
 const {view,items,groupedCards,deals,selectedIds,onSelect,collapsedGroups,onToggleGroup,onEditGroup,sort,onSort,returnTo}=props
 const [columns,setColumns]=useState(1)
 const rows=useMemo(()=>catalogRows(items,groupedCards,collapsedGroups,view==='grid'?columns:1),[items,groupedCards,collapsedGroups,view,columns])
 const keys=useMemo(()=>rows.map(row=>row.key),[rows])
 const saved=useRef(positions.get(location.pathname+location.search))
 const windowed=useVirtualRows(keys,view==='grid'?460:82, saved.current?.width===window.innerWidth?saved.current:undefined)
 const {root,virtualizer,virtual,margin}=windowed
 useLayoutEffect(()=>{if(windowed.width) setColumns(Math.max(1,Math.floor((windowed.width+8)/228)))},[windowed.width])
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
   if(row.kind==='group') return <CatalogGroup group={row.item.group} view={view} collapsed={collapsedGroups.includes(row.item.id)}
     onToggle={onToggleGroup} onEdit={onEditGroup} index={index} blockEnd={endsBlock(rows[index+1])} measure={virtual && view==='list'?virtualizer.measureElement:undefined} />
   const cards=row.cards.map(({card,nested})=><CatalogProduct key={card.id} card={card} nested={nested} view={view}
     selected={selectedIds.has(card.id)} onToggle={onSelect} savings={deals.get(card.id)?.savings ?? null} returnTo={returnTo}
     index={index} blockEnd={endsBlock(rows[index+1])} measure={virtual && view==='list'?virtualizer.measureElement:undefined} />)
   return view==='list'?cards:<ul className={cn('cards-grid',row.cards[0]?.nested && 'cards-grid--nested')} style={{gridTemplateColumns:`repeat(${columns},minmax(0,1fr))`}}>{cards}</ul>
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
 return <div ref={root} onFocusCapture={windowed.focus} onPointerDownCapture={windowed.focus} onBlurCapture={windowed.blur} data-catalog-results>
   {view==='grid'?<ul className="virtual-grid" data-virtual-start aria-label="Отслеживаемые карточки маркетплейсов">
     {body}{tail>0?<li aria-hidden="true" style={{height:tail}} />:null}
   </ul>:<Table className="cards-table" aria-rowcount={rows.length+1}>
     <TableCaption className="sr-only">Отслеживаемые карточки маркетплейсов</TableCaption>
     <TableHeader><TableRow><TableHead className="cards-table__selection py-0"><span className="sr-only">Выбор</span></TableHead>
       {(Object.entries(columnLabels) as [ColumnSortKey,string][]).map(([key,label])=>{
         const direction=sort?.key===key?sort.direction:null
         return <TableHead key={key} scope="col" aria-sort={direction==='asc'?'ascending':direction==='desc'?'descending':'none'}>
           <Button variant="ghost" type="button" className={cn('cards-table__sort h-11.5 px-0',direction&&'is-active')} onClick={()=>onSort(key)}
             title={direction==='asc'?'Сортировать по убыванию':direction==='desc'?'Сбросить сортировку':'Сортировать по возрастанию'}>
             {label}<span className="cards-table__sort-icon" aria-hidden="true">{direction==='desc'?<ArrowDown />:<ArrowUp />}</span>
           </Button></TableHead>
       })}<TableHead><span className="sr-only">Действия</span></TableHead></TableRow></TableHeader>
     <TableBody data-virtual-start>{body}{tail>0?<tr aria-hidden="true" className="virtual-spacer"><td colSpan={9} style={{height:tail}} /></tr>:null}</TableBody>
   </Table>}
 </div>
})
