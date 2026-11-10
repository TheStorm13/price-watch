import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { defaultRangeExtractor, useWindowVirtualizer, type VirtualItem } from '@tanstack/react-virtual'

// Only one focus owner and its adjacent rows can be pinned, so keyboard
// navigation/portaled menus do not grow the DOM.
export function useVirtualRows(keys: string[], estimate: number, saved?: {offset:number;measurements:VirtualItem[]}, { blockSize = 1, naturalLimit = 40 }: { blockSize?: number; naturalLimit?: number } = {}) {
  const root = useRef<HTMLDivElement>(null)
  const [margin, setMargin] = useState(0)
  const [width, setWidth] = useState(0)
  const [pinned, setPinned] = useState<string | null>(null)
  const virtual = keys.length > naturalLimit
  const estimateSize = useCallback(() => estimate, [estimate])
  const getItemKey = useCallback((index: number) => keys[index], [keys])
  const pinnedIndex = pinned === null ? -1 : keys.indexOf(pinned)
  const rangeExtractor = useCallback((range: Parameters<typeof defaultRangeExtractor>[0]) => {
    const visible = defaultRangeExtractor(range)
    // Keep the DOM window stable within a block instead of replacing a table
    // row at every row boundary. Include the full overscan range and focus pins.
    const start = Math.floor(visible[0] / blockSize) * blockSize
    const end = Math.min(range.count, Math.ceil((visible.at(-1)! + 1) / blockSize) * blockSize)
    const indices = Array.from({ length: end - start }, (_, index) => start + index)
    if(pinnedIndex>=0) for(let i=Math.max(0,pinnedIndex-1); i<=Math.min(keys.length-1,pinnedIndex+1); i++) indices.push(i)
    return [...new Set(indices)].sort((a,b)=>a-b)
  }, [pinnedIndex,keys.length,blockSize])
  const virtualizer = useWindowVirtualizer({count:keys.length, estimateSize, enabled: virtual, useFlushSync: false,
    getItemKey, scrollMargin:margin, overscan:4, rangeExtractor,
    initialRect:{width:window.innerWidth,height:window.innerHeight},
    initialOffset:saved?.offset, initialMeasurementsCache:saved?.measurements,
  })
  // The list can move without resizing (selection toolbar, errors above it).
  // Refresh its document offset after every commit, as well as on resize.
  const measureLayout = useCallback(() => {
    const element = root.current
    if (!element) return
    const start = element.querySelector('[data-virtual-start]') ?? element
    setMargin(start.getBoundingClientRect().top + window.scrollY)
    setWidth(element.clientWidth)
  }, [])
  useLayoutEffect(measureLayout)
  useLayoutEffect(() => {
    const element = root.current
    if (!element) return
    const observer = new ResizeObserver(measureLayout)
    observer.observe(element)
    if (element.parentElement) observer.observe(element.parentElement)
    window.addEventListener('resize', measureLayout)
    return () => { observer.disconnect(); window.removeEventListener('resize', measureLayout) }
  }, [measureLayout])
  const focus = useCallback((event: React.SyntheticEvent)=>{
    const row=(event.target as HTMLElement).closest<HTMLElement>('[data-vrow]')
    if(row) setPinned(keys[Number(row.dataset.vrow)] ?? null)
  },[keys])
  const blur = useCallback(()=>{
    queueMicrotask(()=>{
      if(!root.current?.contains(document.activeElement) && !document.querySelector('[role="menu"], [role="dialog"], [role="alertdialog"]')) setPinned(null)
    })
  },[])
  const previousWidth = useRef(0)
  useEffect(()=>{
    if(previousWidth.current && previousWidth.current !== width) virtualizer.measure()
    previousWidth.current=width
  },[width,virtualizer])
  // Small collections retain their natural layout and are also usable in jsdom.
  const items = !virtual ? keys.map((key,index)=>({key,index,start:0,end:0,size:0,lane:0})) : virtualizer.getVirtualItems()
  return {root,width,virtualizer,items,margin,focus,blur,virtual}
}
