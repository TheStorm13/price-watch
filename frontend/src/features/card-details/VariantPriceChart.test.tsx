import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import type { TrackedVariant } from '../../types/domain'
import { VariantPriceChart } from './VariantPriceChart'

afterEach(cleanup)
const variants: TrackedVariant[] = [1, 2].map((id) => ({ id, cardId: 1, externalId: `123:${id}`,
  title: '', options: { Размер: String(id) }, url: null, imageUrl: null, currentPrice: null,
  currentAvailability: null, lastObservedAt: null, updatedAt: null }))

it('shows the primary series by default and switches with the primary key', () => {
  const { rerender } = render(<VariantPriceChart key={1} history={[]} variants={variants} primaryVariantId={1} />)
  expect(screen.getByRole('checkbox', { name: 'Показать на графике: Размер: 1' })).toBeChecked()
  expect(screen.getByRole('checkbox', { name: 'Показать на графике: Размер: 2' })).not.toBeChecked()
  rerender(<VariantPriceChart key={2} history={[]} variants={variants} primaryVariantId={2} />)
  expect(screen.getByRole('checkbox', { name: 'Показать на графике: Размер: 1' })).not.toBeChecked()
  expect(screen.getByRole('checkbox', { name: 'Показать на графике: Размер: 2' })).toBeChecked()
})
