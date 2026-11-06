import { expect, it } from 'vitest'
import { performanceData } from './performanceData'
it('builds reproducible varied data for every benchmark size and shape', () => {
 for(const count of [100,1000,5000]) for(const shape of ['plain','mixed','group']) {
  const a=performanceData(count,shape,true),b=performanceData(count,shape,true)
  expect(a).toEqual(b)
  expect(a.cards).toHaveLength(count)
  expect(new Set(a.cards.map(c=>c.marketplace)).size).toBe(4)
  expect(a.cards.some(c=>c.currentPrice===null)).toBe(true)
  expect(a.cards.some(c=>c.tags?.length)).toBe(true)
  expect(a.deals.length).toBeGreaterThan(0)
  const grouped=a.groups.flatMap(g=>g.cardIds)
  expect(new Set(grouped).size).toBe(grouped.length)
  expect(grouped.length).toBe(shape==='plain'?0:shape==='group'?count:count/2)
 }
 expect(performanceData(100,'plain').cards[0].title).toBe('Тестовый товар 00000')
})
