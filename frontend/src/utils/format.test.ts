import { describe, expect, it } from 'vitest'
import { availabilityLabel, formatPrice } from './format'

describe('formatPrice', () => {
  it('не превращает отсутствие цены в ноль', () => {
    expect(formatPrice(null)).toBe('—')
  })

  it('форматирует целую цену без копеек', () => {
    expect(formatPrice(72990)).toMatch(/72\s990\s₽/)
  })
})

describe('availabilityLabel', () => {
  it('содержит пользовательские подписи', () => {
    expect(availabilityLabel.in_stock).toBe('В наличии')
    expect(availabilityLabel.out_of_stock).toBe('Нет в наличии')
  })
})
