import { memo, useCallback, useRef, useState } from 'react'
import { defaultRangeExtractor, useVirtualizer } from '@tanstack/react-virtual'
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldLegend, FieldSet } from '@/components/ui/field'
import { Checkbox } from '@/components/ui/checkbox'
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription } from '@/components/ui/empty'
import type { TrackedCardView } from '../../types/domain'

export const GroupCandidates = memo(function GroupCandidates({cards,selected,onToggle}: {
  cards:TrackedCardView[];selected:Set<number>;onToggle:(id:number,checked:boolean)=>void
}) {
 const parent=useRef<HTMLDivElement>(null)
 const [focused,setFocused]=useState<number|null>(null)
 const index=focused===null?-1:cards.findIndex(card=>card.id===focused)
 const rangeExtractor=useCallback((range:Parameters<typeof defaultRangeExtractor>[0])=>{
   const indices=defaultRangeExtractor(range)
   if(index>=0) for(let i=Math.max(0,index-1);i<=Math.min(cards.length-1,index+1);i++) indices.push(i)
   return [...new Set(indices)].sort((a,b)=>a-b)
 },[index,cards.length])
 const v=useVirtualizer({count:cards.length,getScrollElement:()=>parent.current,estimateSize:()=>68,
   getItemKey:index=>cards[index].id,overscan:3,rangeExtractor})
 const virtual=cards.length>40
 const items=virtual?v.getVirtualItems():cards.map((card,index)=>({key:card.id,index,start:0}))
 return <FieldSet><FieldLegend className="sr-only">Товары группы</FieldLegend><FieldGroup className="gap-0">
   <div ref={parent} style={{maxHeight:260,overflowY:'auto'}} onBlur={()=>{
     queueMicrotask(()=>{if(!parent.current?.contains(document.activeElement)) setFocused(null)})
   }}>
     <div style={virtual?{height:v.getTotalSize(),position:'relative'}:undefined}>
       {items.map(item=>{
         const card=cards[item.index]
         return <Field key={item.key} data-index={item.index} ref={virtual?v.measureElement:undefined} orientation="horizontal"
           className="group-dialog__card" onFocusCapture={()=>setFocused(card.id)}
           style={virtual?{position:'absolute',top:0,left:0,width:'100%',transform:`translateY(${item.start}px)`}:undefined}>
           <Checkbox id={`group-card-${card.id}`} checked={selected.has(card.id)} onCheckedChange={checked=>onToggle(card.id,checked===true)} />
           <FieldLabel htmlFor={`group-card-${card.id}`}><span><strong>{card.title ?? card.externalId}</strong><FieldDescription>{card.marketplace} · ID: {card.externalId}</FieldDescription></span></FieldLabel>
         </Field>
       })}
     </div>
   </div>
   {cards.length===0?<Empty><EmptyHeader><EmptyTitle>Карточки не найдены</EmptyTitle><EmptyDescription>Измените или очистите запрос.</EmptyDescription></EmptyHeader></Empty>:null}
 </FieldGroup></FieldSet>
})
