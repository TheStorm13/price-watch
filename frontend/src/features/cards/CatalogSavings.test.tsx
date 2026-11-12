import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it } from 'vitest'
import { CatalogSavings } from './CatalogSavings'
import type { PurchaseAssessment } from '../../types/domain'
afterEach(cleanup)
const assessment: PurchaseAssessment = { evaluatedAt: '2026-11-12T00:00:00Z', historyStartedAt: '2026-10-01T00:00:00Z',
  historyEligible: true, isMatch: true, matches: ['small_range', 'target_price', 'historical_savings_share'],
  currentPrice: '850', minimumPrice: '800', maximumPrice: '1000', averagePrice: '1000', targetPrice: '900',
  smallRangeTolerance: '200', historicalSavingsShare: '70', threshold: '860' }
it('opens all reasons with the keyboard and Escape closes without inventing savings', async () => {
  const user = userEvent.setup()
  render(<CatalogSavings savings={null} average="1000" minimum="800" assessment={assessment} observedAt="2026-11-11T00:00:00Z" />)
  expect(screen.getByText('Нет выгоды')).toBeVisible()
  await user.tab(); await user.keyboard('{Enter}')
  expect(screen.getByText('Подходит по вашим условиям')).toBeVisible()
  expect(screen.getByText(/не больше вашего порога/)).toHaveTextContent('200')
  expect(screen.getByText(/вашей целевой цены/)).toHaveTextContent('900')
  expect(screen.getByText(/Ваш порог цены/)).toHaveTextContent('860')
  expect(screen.getByText(/Последнее наблюдение/)).toBeVisible()
  await user.keyboard('{Escape}')
  expect(screen.queryByText('Подходит по вашим условиям')).not.toBeInTheDocument()
})
it('does not turn a factual saving into a star without a personal match', () => {
  render(<CatalogSavings savings="150" average="1000" minimum="800" assessment={{ ...assessment, isMatch: false, matches: [] }} />)
  expect(screen.getByText('150 ₽')).toBeVisible()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})
