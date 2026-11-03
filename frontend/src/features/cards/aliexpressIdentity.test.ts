import { expect, it } from 'vitest'
import { parseAliExpressUrl } from './aliexpressIdentity'

it('сохраняет длинные ID строками и требует единственный SKU', () => {
  expect(parseAliExpressUrl('https://aliexpress.ru/item/1005009868651525.html?sku_id=12000061135122688&spmC=foo')).toEqual({ productId: '1005009868651525', skuId: '12000061135122688' })
  for (const value of ['https://ali.click/mtipo1n', 'https://aliexpress.ru/item/1.html?sku_id=2&sku_id=2']) {
    expect(() => parseAliExpressUrl(value)).toThrow()
  }
})

it('принимает товарную ссылку без SKU', () => {
  expect(parseAliExpressUrl('https://aliexpress.ru/item/123.html')).toEqual({ productId: '123', skuId: undefined })
})
