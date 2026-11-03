import { expect, test, type Page } from '@playwright/test'

async function bottom(page:Page, name:string) {
  const last=page.getByRole('checkbox',{name:`Выбрать карточку ${name}`})
  // Virtual row measurements can change the bottom after each scroll/resize.
  // Keep scrolling while waiting, rather than passively waiting at an old bottom.
  await expect.poll(async()=>{
    if(await last.isVisible()) return true
    await page.evaluate(()=>window.scrollTo(0,document.documentElement.scrollHeight))
    return false
  },{timeout:10000,intervals:[80,100,200]}).toBe(true)
  return last
}

for(const shape of ['plain','mixed','group']) test(`bounded catalog and last item: ${shape}`,async({page})=>{
  const errors:string[]=[]
  page.on('pageerror',error=>errors.push(error.message))
  await page.goto(`/cards?perf=5000&shape=${shape}`)
  const firstName=shape==='mixed'?'00001':'00000'
  const lastName=shape==='mixed'?'04998':'04999'
  const first=page.getByRole('checkbox',{name:`Выбрать карточку Тестовый товар ${firstName}`})
  await expect(first).toBeVisible()
  expect(await page.locator('.cards-table__product').count()).toBeLessThan(40)
  await first.check()
  const last=await bottom(page,`Тестовый товар ${lastName}`)
  await last.check()
  await expect(page.getByRole('group',{name:'Действия с выбранными карточками'})).toContainText('Выбрано карточек: 2')
  expect(await page.locator('.cards-table__product').count()).toBeLessThan(50)
  await page.evaluate(()=>window.scrollTo(0,0))
  await page.getByRole('radio',{name:'Сетка'}).click()
  expect(await page.locator('.cards-grid__item').count()).toBeLessThan(100)
  if (shape === 'group') {
    const gridRows = page.locator('.cards-grid--nested')
    const first = await gridRows.nth(0).locator('.cards-grid__item').first().boundingBox()
    const next = await gridRows.nth(1).locator('.cards-grid__item').first().boundingBox()
    expect(first).not.toBeNull()
    expect(next).not.toBeNull()
    expect(next!.y - first!.y - first!.height).toBeCloseTo(8, 0)
  }
  await bottom(page,`Тестовый товар ${lastName}`)
  expect(await page.locator('.cards-grid__item').count()).toBeLessThan(120)
  await page.setViewportSize({width:1024,height:768})
  await bottom(page,`Тестовый товар ${lastName}`)
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
  expect(errors).toEqual([])
})

test('large group editor saves the complete offscreen membership',async({page})=>{
 await page.goto('/cards?perf=5000&shape=group')
 await page.getByRole('button',{name:'Изменить группу Тестовая группа 1'}).click()
 const dialog=page.getByRole('dialog')
 await expect(dialog).toContainText('Выбрано карточек: 5000')
 expect(await dialog.getByRole('checkbox').count()).toBeLessThan(30)
 await dialog.getByRole('textbox',{name:'Поиск карточек'}).fill('04999')
 const last=dialog.getByRole('checkbox',{name:/Тестовый товар 04999/})
 await expect(last).toBeVisible()
 await last.uncheck()
 await dialog.getByRole('button',{name:'Сохранить',exact:true}).click()
 const ids=await page.evaluate(()=>((window as any).__pwPerf.lastGroupInput as {cardIds:number[]}).cardIds)
 expect(ids.length).toBe(4999)
 expect(ids).not.toContain(14999)
 expect(new Set(ids).size).toBe(4999)
})

test('progress updates leave unchanged catalog DOM untouched',async({page})=>{
 await page.goto('/cards?perf=1000')
 await expect(page.getByRole('checkbox',{name:'Выбрать карточку Тестовый товар 00000'})).toBeVisible()
 await page.evaluate(()=> (window as any).__pwPerf.progress(0))
 await expect(page.getByRole('complementary',{name:'Состояние обновления цен'})).toBeVisible()
 const mutations=await page.evaluate(async()=>{
   let changes=0
   const observer=new MutationObserver(records=>{changes+=records.length})
   observer.observe(document.querySelector('[data-catalog-results]')!,{subtree:true,childList:true,attributes:true,characterData:true})
   for(let i=1;i<=30;i++) {
     ;(window as any).__pwPerf.progress(i)
     await new Promise(resolve=>setTimeout(resolve,5))
   }
   observer.disconnect()
   return changes
 })
 expect(mutations).toBe(0)
})

test('virtualized catalog restores position after card details',async({page})=>{
 await page.goto('/cards?perf=5000')
 await expect(page.getByRole('checkbox',{name:'Выбрать карточку Тестовый товар 00000'})).toBeVisible()
 await bottom(page,'Тестовый товар 04999')
 const offset=await page.evaluate(()=>window.scrollY)
 await page.getByRole('link',{name:'Тестовый товар 04999',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Тестовый товар 04999',exact:true})).toBeVisible()
 await page.getByRole('link',{name:/Назад|карточкам/}).click()
 await expect(page.getByRole('checkbox',{name:'Выбрать карточку Тестовый товар 04999'})).toBeVisible()
 expect(Math.abs(await page.evaluate(()=>window.scrollY)-offset)).toBeLessThan(200)
})

test('an offscreen action owner survives its menu and confirmation',async({page})=>{
 await page.goto('/cards?perf=5000')
 const trigger=page.getByRole('button',{name:'Действия с карточкой Тестовый товар 00000'})
 await trigger.click()
 await page.evaluate(()=>window.scrollTo(0,document.documentElement.scrollHeight))
 // The modal menu prevents user scrolling; force a virtual-window change
 // and use its keyboard path to verify ownership survives offscreen.
 await page.keyboard.press('End')
 await expect(page.getByRole('menuitem',{name:'Удалить карточку',exact:true})).toBeFocused()
 await page.keyboard.press('Enter')
 await expect(page.getByRole('alertdialog')).toBeVisible()
 await page.getByRole('button',{name:'Отмена',exact:true}).click()
 await expect(trigger).toBeFocused()
 expect(await page.locator('.cards-table__product').count()).toBeLessThan(50)
})

test('tab navigation reaches cards beyond the initial virtual window',async({page})=>{
 await page.goto('/cards?perf=1000')
 await page.getByRole('checkbox',{name:'Выбрать карточку Тестовый товар 00000'}).focus()
 for(let i=0;i<90;i++) await page.keyboard.press('Tab')
 const title=await page.evaluate(()=>document.activeElement?.closest('.cards-table__product')?.textContent)
 expect(title).toMatch(/Тестовый товар 000[23][0-9]/)
 expect(await page.locator('.cards-table__product').count()).toBeLessThan(50)
})
