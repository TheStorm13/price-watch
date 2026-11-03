import { describe, expect, it } from 'vitest'
import { isWildberriesId, parseWildberriesUrl } from './wildberriesIdentity'

describe('Wildberries size identity', () => {
  it('parses one exact size without losing string identity', () => {
    expect(parseWildberriesUrl('https://www.wildberries.ru/catalog/179224846/detail.aspx?targetUrl=SN&size=296499716'))
      .toEqual({ nmId: '179224846', optionId: '296499716' })
  })
  it('rejects unsafe and ambiguous input', () => {
    for (const id of ['0', '01', '１', '٢', '-1', '9007199254740992']) expect(isWildberriesId(id)).toBe(false)
    for (const url of [      'https://www.wildberries.ru/catalog/1/detail.aspx?size=2&size=2',
      'https://evil.ru/catalog/1/detail.aspx?size=2']) expect(() => parseWildberriesUrl(url)).toThrow()
  })
})

it('принимает товарную ссылку без SKU', () => {
  expect(parseWildberriesUrl('https://www.wildberries.ru/catalog/123/detail.aspx')).toEqual({ nmId: '123', optionId: undefined })
})
