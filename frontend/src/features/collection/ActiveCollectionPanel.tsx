import { AlertCircle, Check, LoaderCircle, X } from 'lucide-react'
import { isDesktopMode } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Link } from 'react-router-dom'
import { useCollection } from './CollectionProvider'

export function ActiveCollectionPanel() {
  const { run, continueRun, dismiss, openBrowser } = useCollection()
  if (!run) return null

  const waiting = run.status === 'waiting_for_user'
  const complete = ['completed', 'completed_with_errors', 'failed'].includes(run.status)
  const progress = run.totalCount ? Math.round(((run.successCount + run.failureCount) / run.totalCount) * 100) : 0
  const title = complete
    ? run.status === 'completed' ? 'Цены обновлены' : 'Обновление завершено с ошибками'
    : 'Обновление цен'

  return (
    <aside className="collection-panel" aria-live="polite" aria-label="Состояние обновления цен">
      <div className="collection-panel__header">
        <span className={`collection-panel__symbol ${waiting ? 'is-warning' : complete ? 'is-complete' : ''}`}>
          {waiting ? <AlertCircle /> : complete ? <Check /> : <LoaderCircle className="spin" />}
        </span>
        <strong>{title}</strong>
        {complete ? <button className="icon-button" onClick={dismiss} aria-label="Закрыть"><X /></button> : null}
      </div>
      {waiting ? (
        <div className="collection-panel__challenge">
          <div>
            <strong>Требуется проверка Ozon</strong>
            <p>{run.challenge?.message ?? 'Завершите проверку в открывшемся Chrome, затем продолжите'}</p>
          </div>
          <div className="collection-panel__challenge-actions">
            {!isDesktopMode ? <Button onClick={openBrowser}>Открыть Chromium</Button> : null}
            <Button variant="primary" onClick={continueRun}>Проверка пройдена</Button>
          </div>
        </div>
      ) : complete ? (
        <p className="collection-panel__result">Успешно: {run.successCount} · Ошибок: {run.failureCount} {run.status !== 'completed' ? <Link className="text-link" to={`/runs?run=${run.id}`}>Показать ошибки</Link> : null}</p>
      ) : (
        <p className="collection-panel__current">
          {run.current ? `${run.current.marketplace.toUpperCase()} · ID ${run.current.externalId}` : 'Подготавливаем запуск'}
        </p>
      )}
      <div className="collection-panel__progress-row">
        <div className="progress"><span style={{ width: `${waiting ? Math.max(progress, 34) : progress}%` }} /></div>
        <span>{run.successCount + run.failureCount} из {run.totalCount}</span>
      </div>
    </aside>
  )
}
