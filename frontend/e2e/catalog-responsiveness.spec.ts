import { expect, test } from '@playwright/test'

test('rapid search, view and reset preserve the latest filter and details return context',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message))
 await page.goto('/cards?perf=1000')
 const search=page.getByRole('textbox',{name:'Поиск по названию или артикулу'})
 await search.fill('Тестовый')
 await search.fill('0000')
 await search.fill('00000')
 await expect(page.getByRole('main')).toContainText('1 из 1000')
 await page.getByRole('radio',{name:'Сетка',exact:true}).click()
 await page.getByRole('checkbox',{name:'Только в наличии',exact:true}).check()
 const context=page.url()
 await page.getByRole('link',{name:'Тестовый товар 00000',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Тестовый товар 00000',exact:true})).toBeVisible()
 await page.getByRole('link',{name:/К товарам/}).click()
 await expect(page).toHaveURL(context)
 await expect(search).toHaveValue('00000')
 await expect(page.getByRole('radio',{name:'Сетка',exact:true})).toBeChecked()
 await page.getByRole('button',{name:'Сбросить',exact:true}).click()
 // A following control must use the reset URL, not resurrect the old search.
 await page.getByRole('checkbox',{name:'Только в наличии',exact:true}).check()
 await expect(search).toHaveValue('')
 await expect(page.getByRole('main')).toContainText(/1000 из 1000|1000 товаров/)
 expect(new URL(page.url()).searchParams.has('q')).toBe(false)
 await expect(page.getByRole('radio',{name:'Сетка',exact:true})).toBeChecked()
 expect(errors).toEqual([])
})

test('collection counters preserve an open group draft and focus',async({page})=>{
 await page.goto('/cards?perf=1000&shape=group')
 await page.getByRole('button',{name:'Изменить группу Тестовая группа 1',exact:true}).click()
 const dialog=page.getByRole('dialog',{name:'Изменить группу',exact:true})
 const name=dialog.getByRole('textbox',{name:'Название',exact:true})
 await name.fill('Черновик группы')
 await name.focus()
 await page.evaluate(async()=>{
  for(let i=0;i<30;i++){
   ;(window as any).__pwPerf.progress(i)
   await new Promise(resolve=>setTimeout(resolve,5))
  }
 })
 await expect(name).toHaveValue('Черновик группы')
 await expect(name).toBeFocused()
 await expect(dialog).toContainText('Выбрано: 1000')
 await dialog.getByRole('button',{name:'Отмена',exact:true}).click()
 await expect(page.getByRole('button',{name:'Изменить группу Тестовая группа 1',exact:true})).toBeFocused()
 await expect(page.getByRole('button',{name:'Обновить все цены',exact:true})).toBeDisabled()
})

test('an immediate click while search is deferred returns to the displayed catalog context',async({page})=>{
 await page.goto('/cards?perf=1000')
 await page.getByRole('link',{name:'Тестовый товар 00000',exact:true}).waitFor()
 await page.evaluate(()=>{
  const input=document.querySelector<HTMLInputElement>('.catalog-search input')!
  const link=document.querySelector<HTMLAnchorElement>('.card-identity__link')!
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,'missing-product')
  input.dispatchEvent(new Event('input',{bubbles:true}))
  // Same browser task: click the still-rendered result before background filtering.
  link.click()
 })
 await expect(page.getByRole('heading',{name:'Тестовый товар 00000',exact:true})).toBeVisible()
 expect(await page.evaluate(()=>history.state.usr.returnTo)).toBe('/cards?perf=1000')
 await page.getByRole('link',{name:/К товарам/}).click()
 await expect(page.getByRole('textbox',{name:'Поиск по названию или артикулу'})).toHaveValue('')
 await expect(page.getByRole('main')).toContainText(/1000 из 1000|1000 товаров/)
})

for (const view of ['list', 'grid']) test(`selection remains interactive after scrolling in ${view}`, async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`/cards?perf=5000&view=${view}`)
  const box = page.getByRole('checkbox', { name: 'Выбрать карточку Тестовый товар 00000', exact: true })
  await box.check()
  const toolbar = page.getByRole('group', { name: 'Действия с выбранными карточками' })
  for (let round = 0; round < 3; round++) {
    await page.evaluate(() => window.scrollTo(0, 15000))
    await expect(toolbar).toBeInViewport()
    await page.mouse.wheel(0, 900)
    await page.evaluate(() => window.scrollTo(0, 0))
    await expect(box).toBeVisible()
  }
  await box.uncheck({ timeout: 2000 })
  await expect(toolbar).toBeHidden()
  await box.check({ timeout: 2000 })
  await page.getByRole('button', { name: 'Снять выбор', exact: true }).click({ timeout: 2000 })
  await expect(box).not.toBeChecked()
  await page.getByRole('link', { name: 'Тестовый товар 00000', exact: true }).click({ timeout: 2000 })
  await expect(page.getByRole('heading', { name: 'Тестовый товар 00000', exact: true })).toBeVisible()
  expect(errors).toEqual([])
})

test('card action labels fit a single line in catalog and details', async ({ page }) => {
  await page.goto('/cards')
  for (const details of [false, true]) {
    if (details) {
      await page.locator('.card-identity__link').first().click()
      await expect(page.getByRole('link', { name: 'К товарам', exact: true })).toBeVisible()
    }
    await page.getByRole('button', { name: /^Действия с карточкой/ }).first().click()
    const menu = page.getByRole('menu')
    await expect(menu).toBeVisible()
    const items = await menu.getByRole('menuitem').evaluateAll(elements => elements.map(element => {
      const range = document.createRange()
      const text = [...element.childNodes].find(node => node.nodeType === Node.TEXT_NODE)!
      range.selectNodeContents(text)
      return { lines: range.getClientRects().length, fits: element.scrollWidth <= element.clientWidth }
    }))
    expect(items.length).toBeGreaterThan(1)
    expect(items.every(item => item.lines === 1 && item.fits)).toBe(true)
    await page.keyboard.press('Escape')
    await expect(menu).toBeHidden()
  }
})

for (const count of [100, 5000]) for (const view of ['list', 'grid']) test(`collection progress keeps selection and scrolling responsive: ${count} ${view}`, async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`/cards?perf=${count}&shape=group&view=${view}`)
  const box = page.getByRole('checkbox', { name: 'Выбрать карточку Тестовый товар 00000', exact: true })
  await box.check()
  await page.evaluate(() => {
    const fixture = (window as any).__pwPerf
    fixture.progress(0)
    let completed = 0
    ;(window as any).__progressTimer = setInterval(() => fixture.progress(++completed % 90), 75)
  })
  await expect(page.getByRole('complementary', { name: 'Состояние обновления цен' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Обновить все цены', exact: true })).toBeDisabled()
  // Let selection/layout observers settle, then count only origin reads. Row
  // measurement remains enabled and is intentionally excluded from this count.
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
  await page.evaluate(() => {
    const read = Element.prototype.getBoundingClientRect
    ;(window as any).__originReads = 0
    Element.prototype.getBoundingClientRect = function () {
      if (this.hasAttribute('data-virtual-start')) (window as any).__originReads++
      return read.call(this)
    }
  })
  for (let round = 0; round < 3; round++) {
    await page.mouse.move(900, 450)
    await page.mouse.wheel(0, 1600)
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(300)
    await page.evaluate(() => window.scrollTo(0, 0))
    await expect(box).toBeVisible()
  }
  expect(await page.evaluate(() => (window as any).__originReads)).toBe(0)
  // An existing toolbar can change height without selection or catalog changes.
  await page.getByRole('button', { name: 'Добавить в группу', exact: true }).click({ timeout: 2000 })
  await page.getByRole('button', { name: 'Снять выбор', exact: true }).click({ timeout: 2000 })
  await expect(box).not.toBeChecked()
  await box.check({ timeout: 2000 })
  await box.uncheck({ timeout: 2000 })
  await page.getByRole('link', { name: 'Тестовый товар 00000', exact: true }).click({ timeout: 2000 })
  await expect(page.getByRole('heading', { name: 'Тестовый товар 00000', exact: true })).toBeVisible()
  await page.evaluate(() => clearInterval((window as any).__progressTimer))
  expect(errors).toEqual([])
})
