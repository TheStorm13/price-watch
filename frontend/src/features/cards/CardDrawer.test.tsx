import { useState } from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { TrackedCardView, TrackedVariant } from '../../types/domain'
import { CardDrawer } from './AddCardDrawer'

const card: TrackedCardView = { id:1, marketplace:'wildberries',externalId:'123',primaryVariantId:10,title:'Товар',url:'https://www.wildberries.ru/catalog/123/detail.aspx?size=100',tags:['кухня'],imageUrl:null,dealsEnabled:true,currentPrice:null,currentAvailability:null,lastObservedAt:null,createdAt:'2026-11-01',updatedAt:'2026-11-01' }
const variants: TrackedVariant[] = [{ id:10,cardId:1,externalId:'123:100',title:'Размер M',options:{Размер:'M'},url:card.url,currentPrice:null,currentAvailability:null,lastObservedAt:null,updatedAt:null }]
afterEach(cleanup)

it('edits the exact primary Ozon SKU while keeping the seed article fixed', async () => {
  const save = vi.fn().mockResolvedValue({})
  const user = userEvent.setup()
  const ozon = { ...card, marketplace: 'ozon' as const, externalId: '100', url: 'https://www.ozon.ru/product/200/' }
  const members = [{ ...variants[0], externalId: '200', url: ozon.url, options: { Цвет: 'Чёрный', Размер: '42' } }]
  render(<CardDrawer open onClose={vi.fn()} card={ozon} variants={members} isPending={false} onSave={save} />)
  expect(screen.getByLabelText('ID карточки')).toHaveValue('100')
  await user.click(screen.getByRole('button', { name: 'Сохранить' }))
  expect(save).toHaveBeenCalledWith(expect.objectContaining({ externalId: '100', url: ozon.url, primaryVariantId: 10 }))
})

it('prefills product fields, locks the article and marketplace, and submits cleared fields', async () => {
  const save = vi.fn().mockResolvedValue({})
  const close = vi.fn()
  const user = userEvent.setup()
  render(<CardDrawer open onClose={close} card={card} variants={variants} isPending={false} onSave={save} />)
  expect(screen.getByLabelText('Артикул WB')).toHaveValue('123')
  expect(screen.getByLabelText('Артикул WB')).toHaveAttribute('readonly')
  expect(screen.getByRole('radio', {name:/Wildberries/})).toBeDisabled()
  expect(screen.queryByLabelText('Код размера WB')).toBeNull()
  await user.clear(screen.getByLabelText('Название'))
  await user.clear(screen.getByLabelText('URL'))
  await user.clear(screen.getByLabelText('Теги'))
  await user.click(screen.getByRole('button', { name:'Сохранить' }))
  expect(save).toHaveBeenCalledWith(expect.objectContaining({ title:null,url:null,tags:[],primaryVariantId:10 }))
  expect(close).toHaveBeenCalledOnce()
})

it('keeps the draft after a server error and retries without losing input', async () => {
  const save=vi.fn().mockRejectedValueOnce(new Error('Сервис недоступен')).mockResolvedValueOnce({})
  const user=userEvent.setup()
  render(<CardDrawer open onClose={vi.fn()} card={card} variants={variants} isPending={false} onSave={save} />)
  await user.clear(screen.getByLabelText('Название'))
  await user.type(screen.getByLabelText('Название'),'Новое имя')
  await user.click(screen.getByRole('button',{name:'Сохранить'}))
  expect(screen.getByRole('alert')).toHaveTextContent('Сервис недоступен')
  expect(screen.getByLabelText('Название')).toHaveValue('Новое имя')
  await user.click(screen.getByRole('button',{name:'Сохранить'}))
  expect(save).toHaveBeenCalledTimes(2)
})

it('rejects another product URL without changing its article', async () => {
  const save=vi.fn()
  const user=userEvent.setup()
  render(<CardDrawer open onClose={vi.fn()} card={card} variants={variants} isPending={false} onSave={save} />)
  await user.clear(screen.getByLabelText('URL'))
  await user.type(screen.getByLabelText('URL'),'https://www.wildberries.ru/catalog/999/detail.aspx?size=200')
  await user.click(screen.getByRole('button',{name:'Сохранить'}))
  expect(screen.getByText('Ссылка не соответствует артикулу и размеру WB')).toBeVisible()
  expect(screen.getByLabelText('Артикул WB')).toHaveValue('123')
  expect(save).not.toHaveBeenCalled()
})

it('discards a canceled draft and restores focus to the edit action', async () => {
  function Harness() {
    const [open,setOpen]=useState(false)
    return <><button onClick={()=>setOpen(true)}>Изменить</button><CardDrawer open={open} onClose={()=>setOpen(false)} card={card} variants={variants} isPending={false} onSave={vi.fn()} /></>
  }
  const user=userEvent.setup()
  render(<Harness />)
  await user.click(screen.getByRole('button',{name:'Изменить'}))
  await user.clear(screen.getByLabelText('Название'))
  await user.type(screen.getByLabelText('Название'),'Отменённое имя')
  await user.click(screen.getByRole('button',{name:'Отмена'}))
  await waitFor(()=>expect(screen.getByRole('button',{name:'Изменить'})).toHaveFocus())
  await user.click(screen.getByRole('button',{name:'Изменить'}))
  expect(screen.getByLabelText('Название')).toHaveValue('Товар')
})

it('selects a known SKU as primary together with its exact URL', async () => {
  const save=vi.fn().mockResolvedValue({})
  const user=userEvent.setup()
  const second={...variants[0],id:20,externalId:'123:200',url:'https://www.wildberries.ru/catalog/123/detail.aspx?size=200',options:{Размер:'L'}}
  render(<CardDrawer open onClose={vi.fn()} card={card} variants={[variants[0],second]} isPending={false} onSave={save} />)
  screen.getByRole('combobox',{name:'Главный вариант'}).focus()
  await user.keyboard('{Enter}')
  await user.keyboard('{Home}{Enter}')
  expect(screen.getByLabelText('URL')).toHaveValue(second.url)
  await user.click(screen.getByRole('button',{name:'Сохранить'}))
  expect(save).toHaveBeenCalledWith(expect.objectContaining({primaryVariantId:20,url:second.url}))
})

it('does not send duplicate submissions while a save is outstanding', async () => {
  let finish!: () => void
  const save=vi.fn(()=>new Promise<void>((resolve)=>{finish=resolve}))
  const close=vi.fn()
  const user=userEvent.setup()
  render(<CardDrawer open onClose={close} card={card} variants={variants} isPending={false} onSave={save} />)
  await user.dblClick(screen.getByRole('button',{name:'Сохранить'}))
  expect(save).toHaveBeenCalledOnce()
  finish()
  await waitFor(()=>expect(close).toHaveBeenCalledOnce())
})
