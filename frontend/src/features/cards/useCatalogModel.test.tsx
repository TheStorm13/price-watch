import { renderHook, cleanup } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { useCatalogModel } from './useCatalogModel'
import { performanceData } from '../../test/performanceData'
afterEach(cleanup)
it('reuses projection across view/unrelated params and equivalent filters, refreshes changed inputs', () => {
 const snapshot=performanceData(100,'mixed',true)
 const {result,rerender}=renderHook(({data,search})=>useCatalogModel(data,new URLSearchParams(search)),{initialProps:{data:snapshot,search:'q=Тестовый&tags=Тег+1&tags=Тег+2'}})
 const previous=result.current
 rerender({data:snapshot,search:'view=grid&perf=5000&markets=invalid&tags=Тег+2&tags=Тег+1&q=тестовый'})
 expect(result.current.orderedItems).toBe(previous.orderedItems)
 expect(result.current.groupedCards).toBe(previous.groupedCards)
 expect(result.current.deals).toBe(previous.deals)
 rerender({data:snapshot,search:'q=кабель'})
 expect(result.current.orderedItems).not.toBe(previous.orderedItems)
 expect(result.current.matchingCount).toBe(25)
 const changed=result.current
 rerender({data:{...snapshot,cards:snapshot.cards.slice(0,50)},search:'q=кабель'})
 expect(result.current.totalCount).toBe(50)
 expect(result.current.orderedItems).not.toBe(changed.orderedItems)
})
