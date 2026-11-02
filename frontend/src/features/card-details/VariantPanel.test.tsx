import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { TrackedCardView, TrackedVariant } from '../../types/domain'
import { VariantPanel } from './VariantPanel'
const mutate=vi.hoisted(()=>vi.fn().mockResolvedValue({}))
vi.mock('../../api/queries',()=>({useUpdateCard:()=>({isPending:false,mutateAsync:mutate})}))
afterEach(()=>{cleanup();mutate.mockClear()})

it('searches a large SKU list and explicitly selects the matching variant as primary',async()=>{
  const card={id:1,primaryVariantId:1} as TrackedCardView
  const variants: TrackedVariant[]=Array.from({length:100},(_,i)=>({id:i+1,cardId:1,externalId:`123:${i+1}`,title:'',options:{Размер:String(i+1)},url:null,currentPrice:'100.00',currentAvailability:'in_stock',lastObservedAt:null,updatedAt:null}))
  const user=userEvent.setup()
  render(<VariantPanel card={card} variants={variants} />)
  await user.type(screen.getByRole('textbox',{name:'Поиск варианта'}),'Размер: 82')
  const table=screen.getByRole('table')
  expect(within(table).getAllByRole('row')).toHaveLength(2)
  await user.click(within(table).getByRole('button',{name:'Сделать главным: Размер: 82'}))
  expect(mutate).toHaveBeenCalledWith({cardId:1,input:{primaryVariantId:82}})
})
