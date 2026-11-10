import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { TrackedCardView, TrackedVariant } from '../../types/domain'
import { VariantPanel } from './VariantPanel'
const imageProps = vi.hoisted(() => vi.fn())
vi.mock('../../components/product/PreparedProductImage', () => ({ PreparedProductImage: (props: unknown) => { imageProps(props); return <span className="product-placeholder" /> } }))
const mutate=vi.hoisted(()=>vi.fn().mockResolvedValue({}))
vi.mock('../../api/queries',()=>({useVariantTracking:()=>({isPending:false,mutateAsync:mutate}),useUpdateCard:()=>({isPending:false,mutateAsync:mutate})}))
afterEach(()=>{cleanup();mutate.mockClear();imageProps.mockClear()})

it('searches a large SKU list and explicitly selects the matching variant as primary',async()=>{
  const card={id:1,primaryVariantId:1} as TrackedCardView
  const variants: TrackedVariant[]=Array.from({length:100},(_,i)=>({id:i+1,trackingEnabled: false, isTracked: false, cardId:1,externalId:`123:${i+1}`,title:'',options:{Размер:String(i+1)},url:null,currentPrice:'100.00',currentAvailability:'in_stock',lastObservedAt:null,updatedAt:null}))
  const user=userEvent.setup()
  render(<VariantPanel card={card} variants={variants} />)
  await user.click(screen.getByRole('textbox',{name:'Поиск варианта'}))
  await user.paste('Размер: 82')
  const table=screen.getByRole('table')
  expect(within(table).getAllByRole('row')).toHaveLength(2)
  await user.click(within(table).getByRole('button',{name:'Сделать главным: Размер: 82'}))
  expect(mutate).toHaveBeenCalledWith({cardId:1,input:{primaryVariantId:82}})
})

it('shows each variant photo with its own parameters and plain labels', () => {
  const card = { id: 1, primaryVariantId: 1 } as TrackedCardView
  const variants: TrackedVariant[] = [1, 2, 3].map((id) => ({ id, trackingEnabled: false, isTracked: false, cardId: 1, externalId: `123:${id}`, title: '',
    options: { Цвет: id === 1 ? 'Чёрный' : 'Белый' }, imageUrl: id < 3 ? `https://img.test/${id}.webp` : null,
    url: null, currentPrice: '100.00', currentAvailability: 'in_stock', lastObservedAt: null, updatedAt: null }))
  const { container } = render(<VariantPanel card={card} variants={variants} />)
  expect(imageProps.mock.calls.map(([props]) => [props.card.id, props.variantId, props.card.imageUrl])).toEqual([[1, 2, 'https://img.test/2.webp'], [1, 3, null], [1, 1, 'https://img.test/1.webp']])
  expect(container.querySelectorAll('.product-placeholder')).toHaveLength(3)
  expect(container.textContent).not.toContain('Код варианта')
  expect(container.textContent).not.toContain('SKU')
})

it('sorts variants by their visible name with natural number ordering and hides identifiers', () => {
  const card = { id: 1, primaryVariantId: 1 } as TrackedCardView
  const variants: TrackedVariant[] = ['10', '2', '1'].map((size, index) => ({ id: index + 1, trackingEnabled: false, isTracked: false, cardId: 1,
    externalId: `987654321:${9000 + index}`, title: '', options: { Размер: size }, url: null,
    currentPrice: null, currentAvailability: null, lastObservedAt: null, updatedAt: null }))
  const { container } = render(<VariantPanel card={card} variants={variants} />)
  expect([...container.querySelectorAll('.variant-name strong')].map((el) => el.textContent)).toEqual(['Размер: 1', 'Размер: 2', 'Размер: 10'])
  expect(container.textContent).not.toMatch(/987654321|9000|9001|9002/)
})


it('locks the primary and supports individual and bulk tracking', async () => {
  const user = userEvent.setup()
  const card = { id: 1, primaryVariantId: 1 } as TrackedCardView
  const variants: TrackedVariant[] = [1,2].map((id) => ({ id, cardId: 1, trackingEnabled: id === 2, isTracked: true,
    externalId: `123:${id}`, title: '', options: { Размер: String(id) }, url: null,
    currentPrice: '100.00', currentAvailability: 'in_stock', lastObservedAt: null, updatedAt: null }))
  render(<VariantPanel card={card} variants={variants} />)
  expect(screen.getByRole('checkbox', { name: 'Отслеживать: Размер: 1' })).toBeDisabled()
  await user.click(screen.getByRole('checkbox', { name: 'Отслеживать: Размер: 2' }))
  expect(mutate).toHaveBeenLastCalledWith({ cardId: 1, enabled: false, variantId: 2 })
  await user.click(screen.getByRole('button', { name: 'Выключить остальные' }))
  expect(mutate).toHaveBeenLastCalledWith({ cardId: 1, enabled: false, variantId: undefined })
})
