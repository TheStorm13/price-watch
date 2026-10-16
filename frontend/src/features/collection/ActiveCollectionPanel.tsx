import { AlertCircle, Check, LoaderCircle, X } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { useRun } from '../../api/queries'
import { useCollection } from './CollectionProvider'

export function ActiveCollectionPanel() {
  const { run, continueRun, dismiss, retryErrors, isRetrying, retryError } = useCollection()
  const hasErrors = run?.status === 'completed_with_errors' || run?.status === 'failed'
  const details = useRun(hasErrors ? run.id : null, true)
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
        <span className={`collection-panel__symbol ${hasErrors ? 'is-error' : waiting ? 'is-warning' : complete ? 'is-complete' : ''}`}>
          {waiting || hasErrors ? <AlertCircle /> : complete ? <Check /> : <LoaderCircle className="spin" />}
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
            <Button variant="primary" onClick={continueRun}>Проверка пройдена</Button>
          </div>
        </div>
      ) : complete ? (
        <div className="collection-panel__result">
          <p>Успешно: {run.successCount} · Ошибок: {run.failureCount}</p>
          {hasErrors ? <>
            {details.isLoading ? <p>Загружаем подробности ошибок…</p> : details.isError ? <Button variant="ghost" onClick={() => void details.refetch()}>Не удалось загрузить ошибки. Повторить</Button> : details.data?.errors?.length ? (
              <details className="collection-panel__errors">
                <summary>Показать ошибки</summary>
                <ul>{details.data.errors.map((error, index) => <li key={`${error.cardId}-${index}`}>
                  <strong>{error.externalId ? `${error.marketplace?.toUpperCase()} · ID ${error.externalId}` : 'Ошибка сбора'}</strong>
                  <span>{error.message}</span>
                  {error.traceback ? <details><summary>Технические подробности</summary><pre>{error.traceback}</pre></details> : null}
                </li>)}</ul>
              </details>
            ) : <p>Подробностей об ошибках нет.</p>}
            {details.data?.errors?.some((error) => error.cardId !== null) ? <Button onClick={retryErrors} disabled={isRetrying}>{isRetrying ? 'Повторяем…' : 'Повторить ошибки'}</Button> : null}
            {retryError ? <p className="action-error" role="alert">{retryError}</p> : null}
          </> : null}
        </div>
      ) : (
        <p className="collection-panel__current">
          {run.totalCount > 1
            ? 'Обрабатываем до пяти карточек одновременно'
            : run.current ? `${run.current.marketplace.toUpperCase()} · ID ${run.current.externalId}` : 'Подготавливаем запуск'}
        </p>
      )}
      <div className="collection-panel__progress-row">
        <div className="progress"><span style={{ width: `${waiting ? Math.max(progress, 34) : progress}%` }} /></div>
        <span>{run.successCount + run.failureCount} из {run.totalCount}</span>
      </div>
    </aside>
  )
}
