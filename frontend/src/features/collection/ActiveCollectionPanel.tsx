import { cn } from '@/lib/utils'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { AlertCircle, Check, LoaderCircle, X } from 'lucide-react'
import { Button } from '../../components/ui/button'
import { useRun } from '../../api/queries'
import { useCollection } from './CollectionProvider'

export function ActiveCollectionPanel() {
  const { run, continueRun, isContinuing, continueError, dismiss, retryErrors, isRetrying, retryError } = useCollection()
  const hasErrors = run?.status === 'completed_with_errors' || run?.status === 'failed'
  const details = useRun(hasErrors ? run.id : null, true)
  if (!run) return null

  const waiting = run.status === 'waiting_for_user'
  const complete = ['completed', 'completed_with_errors', 'failed'].includes(run.status)
  const progress = run.totalCount ? Math.round(((run.successCount + run.failureCount) / run.totalCount) * 100) : null
  const title = complete
    ? run.status === 'completed' ? 'Цены обновлены' : 'Обновление завершено с ошибками'
    : 'Обновление цен'

  return (
    <Card asChild className="gap-3 p-4 has-data-[slot=card-footer]:pb-4"><aside className="collection-panel" aria-live="polite" aria-label="Состояние обновления цен">
      <CardHeader className="flex shrink-0 flex-row items-center gap-2 p-0">
        <span className={cn('collection-panel__symbol', hasErrors ? 'is-error' : waiting ? 'is-warning' : complete && 'is-complete')}>
          {waiting || hasErrors ? <AlertCircle /> : complete ? <Check /> : <LoaderCircle className="spin" />}
        </span>
        <CardTitle className="min-w-0 flex-1">{title}</CardTitle>
        {complete ? <Button variant="ghost" size="icon-sm" className="ml-auto" onClick={dismiss} aria-label="Закрыть"><X /></Button> : null}
      </CardHeader>
      <CardContent className="min-h-0 overflow-y-auto px-0">{waiting ? (
        <div className="collection-panel__challenge">
          <div>
            <strong>Требуется проверка в Chrome</strong>
            <p>{run.challenge?.message ?? 'Завершите проверку в открывшемся Chrome, затем продолжите'}</p>
          </div>
          <div className="collection-panel__challenge-actions">
            <Button variant="default" onClick={continueRun} disabled={isContinuing}>{isContinuing ? 'Продолжаем…' : 'Проверка пройдена'}</Button>
          </div>
          {continueError ? <Alert variant="destructive"><AlertDescription>{continueError}</AlertDescription></Alert> : null}
        </div>
      ) : complete ? (
        <div className="collection-panel__result">
          <p>Успешно: {run.successCount} · Ошибок: {run.failureCount}</p>
          {hasErrors ? <>
            {details.data?.diagnosticsStatus === 'limited' ? <p>Сохранены только примеры ошибок; технические подробности сокращены.</p> : null}
            {details.data?.diagnosticsStatus === 'expired' ? <p>Подробности очищены: диагностика хранится только для последнего запуска.</p> : null}
            {details.isLoading ? <p>Загружаем подробности ошибок…</p> : details.isError ? <Button variant="ghost" onClick={() => void details.refetch()}>Не удалось загрузить ошибки. Повторить</Button> : details.data?.errors?.length ? (
              <details className="collection-panel__errors">
                <summary>Показать ошибки</summary>
                <ul>{details.data.errors.map((error, index) => <li key={`${error.cardId}-${index}`}>
                  <strong>{error.externalId ? `${error.marketplace?.toUpperCase()} · ID ${error.externalId}` : 'Ошибка сбора'}</strong>
                  <span>{error.message}</span>
                  {error.traceback ? <details><summary>Технические подробности</summary><pre>{error.traceback}</pre></details> : null}
                </li>)}</ul>
              </details>
            ) : details.data?.diagnosticsStatus === 'expired' ? null : <p>Подробностей об ошибках нет.</p>}
            {run.retryScopeIncomplete ? <p>Состав этого запуска известен не полностью. Повтор затронет только известные карточки.</p> : null}
            {run.retryableCount > 0 ? <Button variant="outline" onClick={retryErrors} disabled={isRetrying}>{isRetrying ? 'Повторяем…' : 'Повторить ошибки и оставшиеся'}</Button> : null}
            {retryError ? <Alert variant="destructive"><AlertDescription>{retryError}</AlertDescription></Alert> : null}
          </> : null}
        </div>
      ) : (
        <p className="collection-panel__current">
          {run.totalCount > 1
            ? 'Обрабатываем до пяти карточек одновременно'
            : run.current ? `${run.current.marketplace.toUpperCase()} · ID ${run.current.externalId}` : 'Подготавливаем запуск'}
        </p>
      )}
      </CardContent><CardFooter className="shrink-0 px-0 pt-3 pb-0"><div className="collection-panel__progress-row">
        <Progress value={progress} aria-label="Прогресс обновления цен" className="flex-1" />
        <span className="shrink-0 whitespace-nowrap">{run.totalCount ? `${run.successCount + run.failureCount} из ${run.totalCount}` : 'Подготовка…'}</span>
      </div>
    </CardFooter></aside></Card>
  )
}
