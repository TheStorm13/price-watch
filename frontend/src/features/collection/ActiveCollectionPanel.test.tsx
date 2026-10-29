import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ActiveCollectionPanel } from './ActiveCollectionPanel'
import { useCollection } from './CollectionProvider'
import type { CollectionRun } from '../../types/domain'

vi.mock('./CollectionProvider', () => ({ useCollection: vi.fn() }))
vi.mock('../../api/queries', () => ({ useRun: () => ({ data: { errors: [{ cardId: null, message: 'Browser startup failed' }] } }) }))
afterEach(cleanup)
it('offers retry for pending targets despite only a run-level error', () => {
  const run: CollectionRun = { id: 1, status: 'failed', totalCount: 5, successCount: 0, failureCount: 0,
    current: null, challenge: null, startedAt: '2026-10-22', finishedAt: '2026-10-22',
    retryableCount: 5, retryScopeIncomplete: true }
  vi.mocked(useCollection).mockReturnValue({ run, continueRun: vi.fn(), dismiss: vi.fn(), retryErrors: vi.fn(),
    isContinuing: false, continueError: null, isRetrying: false, retryError: null, isStarting: false, startError: null, start: vi.fn(), dealNotice: null, dismissDealNotice: vi.fn() })
  const view = render(<ActiveCollectionPanel />)
  expect(screen.getByRole('button', { name: 'Повторить ошибки и оставшиеся' })).toBeEnabled()
  expect(screen.getByText(/Состав этого запуска известен не полностью/)).toBeVisible()
  vi.mocked(useCollection).mockReturnValue({ ...useCollection(), run: { ...run, retryableCount: 0 } })
  view.rerender(<ActiveCollectionPanel />)
  expect(screen.queryByRole('button', { name: 'Повторить ошибки и оставшиеся' })).not.toBeInTheDocument()
})

it('показывает ручную проверку AliExpress с нейтральным заголовком', () => {
  const run: CollectionRun = { id: 2, status: 'waiting_for_user', totalCount: 2, successCount: 0, failureCount: 0,
    current: null, challenge: { type: 'browser_verification', message: 'AliExpress: пройдите проверку в Chrome' },
    startedAt: '2026-10-26', finishedAt: null, retryableCount: 0, retryScopeIncomplete: false }
  vi.mocked(useCollection).mockReturnValue({ ...useCollection(), run })
  render(<ActiveCollectionPanel />)
  expect(screen.getByText('Требуется проверка в Chrome')).toBeVisible()
  expect(screen.getByText('AliExpress: пройдите проверку в Chrome')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Проверка пройдена' })).toBeEnabled()
})

it('reports actual progress, pending continuation, error and indeterminate preparation', () => {
  const run: CollectionRun = { id: 3, status: 'waiting_for_user', totalCount: 5, successCount: 1, failureCount: 0,
    current: null, challenge: null, startedAt: '2026-10-29', finishedAt: null, retryableCount: 0, retryScopeIncomplete: false }
  vi.mocked(useCollection).mockReturnValue({ ...useCollection(), run, isContinuing: true, continueError: null })
  const view = render(<ActiveCollectionPanel />)
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '20')
  expect(screen.getByRole('button', { name: 'Продолжаем…' })).toBeDisabled()
  vi.mocked(useCollection).mockReturnValue({ ...useCollection(), isContinuing: false, continueError: 'Не удалось продолжить' })
  view.rerender(<ActiveCollectionPanel />)
  expect(screen.getByRole('alert')).toHaveTextContent('Не удалось продолжить')
  expect(screen.getByRole('button', { name: 'Проверка пройдена' })).toBeEnabled()
  vi.mocked(useCollection).mockReturnValue({ ...useCollection(), run: { ...run, totalCount: 0, successCount: 0 } })
  view.rerender(<ActiveCollectionPanel />)
  expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow')
  expect(screen.getByText('Подготовка…')).toBeVisible()
  vi.mocked(useCollection).mockReturnValue({ ...useCollection(), run: { ...run, status: 'completed', successCount: 5 } })
  view.rerender(<ActiveCollectionPanel />)
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
})
