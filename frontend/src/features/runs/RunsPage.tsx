import { RefreshCw } from 'lucide-react'
import { useRuns } from '../../api/queries'
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
  const query = useRuns()
  const runs = query.data ?? []
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
                <td className="run-id">#{run.id}</td>
                <td><span className={`run-status run-status--${statusTone[run.status]}`}><span />{runStatusLabel[run.status]}</span></td>
                <td>{formatDateTime(run.startedAt)}</td>
                <td>{formatDuration(run.startedAt, run.finishedAt)}</td>
                <td>{run.successCount}</td><td>{run.failureCount}</td><td>{run.totalCount}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </div>
    </section>
  )
}
