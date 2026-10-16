import { RefreshCw } from 'lucide-react'
import { invoke } from '@tauri-apps/api/core'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { api, isDesktopMode } from '../../api/client'
import { queryKeys, useRun, useRuns } from '../../api/queries'
import { Button } from '../../components/ui/Button'
import { LoadingRows } from '../../components/ui/LoadingRows'
import { formatDateTime, formatDuration, runStatusLabel } from '../../utils/format'
import type { RunStatus } from '../../types/domain'

const statusTone: Record<RunStatus, string> = {
  queued: 'muted',
  running: 'info',
  waiting_for_user: 'warning',
  completed: 'success',
  completed_with_errors: 'warning',
  failed: 'error',
}

export function RunsPage() {
  const client = useQueryClient()
  const [params, setParams] = useSearchParams()
  const selectedId = Number(params.get('run')) || null
  const detail = useRun(selectedId, true)
  const query = useRuns()
  const runs = query.data ?? []
  const retry = useMutation({
    mutationFn: async (sourceId: number) => {
      if (isDesktopMode) await invoke('prepare_collection')
      return api.retryRun(sourceId)
    },
    onSuccess: (run) => {
      void client.invalidateQueries({ queryKey: queryKeys.runs })
      setParams({ run: String(run.id) })
    },
  })
  const failedCards = detail.data?.errors?.filter((error) => error.cardId !== null) ?? []
  const existingRetry = runs.find((run) => run.retryOfRunId === selectedId)
  return (
    <section className="page runs-page">
      <header className="page-header">
        <div><h1>Запуски</h1><p>История обновлений цен по всем карточкам</p></div>
        <Button icon={<RefreshCw />} onClick={() => query.refetch()}>Обновить</Button>
      </header>
      <div className="table-surface">
        {query.isLoading ? <LoadingRows /> : query.isError ? (
          <div className="state-message"><h2>Не удалось загрузить запуски</h2><Button onClick={() => query.refetch()}>Повторить</Button></div>
        ) : runs.length === 0 ? (
          <div className="state-message"><h2>Запусков пока нет</h2><p>Запустите обновление на экране карточек.</p></div>
        ) : (
          <table className="runs-table">
            <caption className="sr-only">История запусков сбора цен</caption>
            <thead><tr><th>Запуск</th><th>Статус</th><th>Начало</th><th>Длительность</th><th>Успешно</th><th>Ошибки</th><th>Всего</th></tr></thead>
            <tbody>{runs.map((run) => (
              <tr key={run.id}>
                <td className="run-id"><button className="text-link" onClick={() => setParams({ run: String(run.id) })}>#{run.id}</button></td>
                <td><span className={`run-status run-status--${statusTone[run.status]}`}><span />{runStatusLabel[run.status]}</span></td>
                <td>{formatDateTime(run.startedAt)}</td>
                <td>{formatDuration(run.startedAt, run.finishedAt)}</td>
                <td>{run.successCount}</td><td>{run.failureCount}</td><td>{run.totalCount}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </div>
      {selectedId !== null ? (
        <section className="run-details" aria-label={`Подробности запуска ${selectedId}`}>
          <div className="run-details__header"><h2>Запуск #{selectedId}</h2><Button onClick={() => setParams({})}>Закрыть</Button></div>
          {detail.data?.retryOfRunId ? <p className="run-retry-link">Повтор запуска <button className="text-link" onClick={() => setParams({ run: String(detail.data?.retryOfRunId) })}>#{detail.data.retryOfRunId}</button></p> : null}
          {failedCards.length > 0 && detail.data && ['completed_with_errors', 'failed'].includes(detail.data.status) ? <div className="run-retry"><p>Повторить только карточки с ошибками: {failedCards.map((error) => error.externalId ?? `#${error.cardId}`).join(', ')}</p>{existingRetry ? <Button onClick={() => setParams({ run: String(existingRetry.id) })}>Открыть повтор #{existingRetry.id}</Button> : <Button disabled={retry.isPending} onClick={() => retry.mutate(selectedId!)}>Повторить ошибки</Button>}</div> : null}
          {retry.isError ? <p className="action-error" role="alert">{retry.error.message}</p> : null}
          {detail.isLoading ? <p>Загрузка подробностей…</p> : detail.isError ? <p role="alert">Не удалось получить подробности запуска.</p> : detail.data?.errors?.length ? (
            <ul className="run-errors">{detail.data.errors.map((error, index) => (
              <li key={`${error.cardId}-${index}`}>
                <strong>{error.externalId ? `${error.marketplace?.toUpperCase()} · ID ${error.externalId}` : 'Ошибка worker'}</strong>
                <p>{error.message}</p>
                {error.traceback ? <details><summary>Технические подробности</summary><pre>{error.traceback}</pre><Button onClick={() => void navigator.clipboard.writeText(error.traceback)}>Скопировать traceback</Button></details> : null}
              </li>
            ))}</ul>
          ) : <p>Ошибок в этом запуске нет.</p>}
        </section>
      ) : null}
    </section>
  )
}
