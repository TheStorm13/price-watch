import { useMemo, useState, type ReactNode } from 'react'
import { BarChart3, Globe2, Settings2, Plus, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ActiveCollectionPanel } from '../collection/ActiveCollectionPanel'
import { useCollection } from '../collection/CollectionProvider'
import { SidebarDemoContext } from './SidebarDemoSlot'
import { AddCardDrawer } from '../cards/AddCardDrawer'
import { ImportExportControls } from '../cards/ImportExportControls'

export default function SidebarDemo({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<HTMLDivElement | null>(null)
  const [group, setGroup] = useState<HTMLDivElement | null>(null)
  const [adding, setAdding] = useState(false)
  const [transferStatus, setTransferStatus] = useState<{ message: string; kind: 'success' | 'error' } | null>(null)
  const [dialog, setDialog] = useState<'chrome' | 'settings' | null>(null)
  const [backgroundEnabled, setBackgroundEnabled] = useState(false)
  const { run, isStarting, start, startError } = useCollection()
  const collecting = isStarting || !!run && ['queued', 'running', 'waiting_for_user'].includes(run.status)
  const slots = useMemo(() => ({ filters, group }), [filters, group])

  return (
    <SidebarDemoContext.Provider value={slots}>
      <div className="sidebar-demo">
        <aside className="sidebar-demo__sidebar" aria-label="Боковая панель">
          <div className="brand sidebar-demo__brand"><BarChart3 aria-hidden="true" /><span>Price watch</span></div>
          <div className="sidebar-demo__scroll">
            <div className="sidebar-demo__primary">
              <Button className="justify-start" onClick={() => setAdding(true)}><Plus data-icon="inline-start" />Добавить карточку</Button>
              <Button className="justify-start" variant="outline" disabled={collecting} onClick={() => start()}><RefreshCw data-icon="inline-start" />Обновить все цены</Button>
              {startError ? <Alert variant="destructive"><AlertDescription>{startError}</AlertDescription></Alert> : null}
            </div>
            <div ref={setGroup} className="sidebar-demo__group" />
            <div ref={setFilters} className="sidebar-demo__filters" />
          </div>
          <div className="sidebar-demo__tools">
            <Button className="justify-start" size="sm" variant="ghost" disabled={collecting} onClick={() => setDialog('chrome')}><Globe2 data-icon="inline-start" />Открыть Chrome</Button>
            <ImportExportControls label="Импорт / экспорт" onStatus={(message, kind) => setTransferStatus({ message, kind })} />
            <Button className="justify-start" size="sm" variant="ghost" onClick={() => setDialog('settings')}><Settings2 data-icon="inline-start" />Настройки</Button>
            <span className="sidebar-demo__mode">Демо · тестовые данные</span>
          </div>
          <div className="sidebar-demo__progress"><ActiveCollectionPanel /></div>
        </aside>
        <div className="sidebar-demo__workspace">
          <main className="main-content">
            {transferStatus ? <Alert variant={transferStatus.kind === 'error' ? 'destructive' : 'default'} role={transferStatus.kind === 'error' ? 'alert' : 'status'}><AlertDescription>{transferStatus.message}</AlertDescription></Alert> : null}
            {children}
          </main>
        </div>
        <AddCardDrawer side="left" open={adding} onClose={() => setAdding(false)} />
        <Dialog open={dialog !== null} onOpenChange={(open) => { if (!open) setDialog(null) }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{dialog === 'chrome' ? 'Браузер магазина' : 'Настройки приложения'}</DialogTitle>
              <DialogDescription>{dialog === 'chrome'
                ? 'В приложении здесь открывается Chrome с сохранённой сессией магазина. В демо браузер не запускается.'
                : 'Предпросмотр настроек. Изменения действуют только в этом демо до перезагрузки страницы.'}</DialogDescription>
            </DialogHeader>
            {dialog === 'settings' ? <FieldGroup>
              <Field orientation="horizontal">
                <Checkbox id="demo-background" checked={backgroundEnabled} onCheckedChange={(checked) => setBackgroundEnabled(checked === true)} />
                <FieldLabel htmlFor="demo-background">Запускать после входа в систему</FieldLabel>
              </Field>
              <p>Автоматическое обновление цен — каждые 6 часов, пока приложение работает.</p>
              {backgroundEnabled ? <p>Закрытие окна оставляет сбор работающим в фоне.</p> : null}
              <p className="text-muted-foreground">Полный выход из приложения будет доступен здесь. В демо службы не запускаются.</p>
            </FieldGroup> : null}
            <Button variant="outline" onClick={() => setDialog(null)}>Готово</Button>
          </DialogContent>
        </Dialog>
      </div>
    </SidebarDemoContext.Provider>
  )
}
