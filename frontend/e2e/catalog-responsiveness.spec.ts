import { expect, test } from '@playwright/test'

test('rapid search, view and reset preserve the latest filter and details return context',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message))
 await page.goto('/cards?perf=1000')
 const search=page.getByRole('textbox',{name:'Поиск по названию или артикулу'})
 await search.fill('Тестовый')
 await search.fill('0000')
 await search.fill('00000')
 await expect(page.getByRole('main')).toContainText('Показано 1 из 1000 товаров')
 await page.getByRole('radio',{name:'Сетка',exact:true}).click()
 await page.getByRole('checkbox',{name:'Только в наличии',exact:true}).check()
 const context=page.url()
 await page.getByRole('link',{name:'Тестовый товар 00000',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Тестовый товар 00000',exact:true})).toBeVisible()
 await page.getByRole('link',{name:/Назад|карточкам/}).click()
 await expect(page).toHaveURL(context)
 await expect(search).toHaveValue('00000')
 await expect(page.getByRole('radio',{name:'Сетка',exact:true})).toBeChecked()
 await page.getByRole('button',{name:'Сбросить',exact:true}).click()
 // A following control must use the reset URL, not resurrect the old search.
 await page.getByRole('checkbox',{name:'Только в наличии',exact:true}).check()
 await expect(search).toHaveValue('')
 await expect(page.getByRole('main')).toContainText('Показано 1000 из 1000 товаров')
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
 await expect(dialog).toContainText('Выбрано карточек: 1000')
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
 await page.getByRole('link',{name:/Назад|карточкам/}).click()
 await expect(page.getByRole('textbox',{name:'Поиск по названию или артикулу'})).toHaveValue('')
 await expect(page.getByRole('main')).toContainText('Показано 1000 из 1000 товаров')
})
