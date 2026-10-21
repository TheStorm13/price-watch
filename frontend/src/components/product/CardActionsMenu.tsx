import { restoreFocus } from '@/lib/focus'
import { Eye, EyeOff, LoaderCircle, MoreVertical, RefreshCw, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { Button } from '../ui/button'
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuSeparator } from '../ui/dropdown-menu'
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from '../ui/alert-dialog'
import { Alert, AlertDescription } from '../ui/alert'

interface CardActionsMenuProps {
  cardTitle: string
  dealsEnabled: boolean
  onToggle: () => Promise<unknown>
  onDelete: () => Promise<unknown>
  onRefresh?: () => void
  refreshDisabled?: boolean
  bordered?: boolean
}

export function CardActionsMenu({ cardTitle, dealsEnabled, onToggle, onDelete, onRefresh, refreshDisabled = false, bordered = false }: CardActionsMenuProps) {
  const [open, setOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  async function toggleTracking() {
    setPending(true)
    setError(null)
    try {
      await onToggle()
      setOpen(false)
    } catch {
      setError('Не удалось изменить состояние')
    } finally {
      setPending(false)
    }
  }

  async function deleteCard() {
    setPending(true)
    setError(null)
    try {
      await onDelete()
      setConfirming(false)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось удалить карточку')
    } finally {
      setPending(false)
    }
  }

  const actionLabel = dealsEnabled ? 'Не учитывать в выгодных предложениях' : 'Учитывать в выгодных предложениях'
  return <div className="card-actions-menu" onClick={(event) => event.stopPropagation()}>
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button ref={triggerRef} variant={bordered ? 'outline' : 'ghost'} size="icon" aria-label={`Действия с карточкой ${cardTitle}`} onClick={() => setError(null)}><MoreVertical /></Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" aria-label={`Действия с карточкой ${cardTitle}`} onCloseAutoFocus={(event) => { if (confirming) event.preventDefault() }}>
        <DropdownMenuGroup>
          {onRefresh ? <DropdownMenuItem disabled={pending || refreshDisabled} onSelect={() => onRefresh()}><RefreshCw />Обновить только эту карточку</DropdownMenuItem> : null}
          <DropdownMenuItem disabled={pending} onSelect={(event) => { event.preventDefault(); void toggleTracking() }}>
            {pending ? <LoaderCircle className="spin" /> : dealsEnabled ? <EyeOff /> : <Eye />}{pending ? 'Сохраняем…' : actionLabel}
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem variant="destructive" disabled={pending} onSelect={() => { setError(null); setConfirming(true) }}><Trash2 />Удалить карточку</DropdownMenuItem>
        </DropdownMenuGroup>
        {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
      </DropdownMenuContent>
    </DropdownMenu>
    <AlertDialog open={confirming} onOpenChange={(next) => { if (!pending) setConfirming(next) }}>
      <AlertDialogContent onCloseAutoFocus={(event) => { event.preventDefault(); restoreFocus(triggerRef.current) }}>
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить карточку?</AlertDialogTitle>
          <AlertDialogDescription>«{cardTitle}» и вся история её цен будут удалены без возможности восстановления.</AlertDialogDescription>
        </AlertDialogHeader>
        {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Отмена</AlertDialogCancel>
          <AlertDialogAction variant="destructive" disabled={pending} onClick={(event) => { event.preventDefault(); void deleteCard() }}>
            {pending ? <LoaderCircle className="spin" data-icon="inline-start" /> : <Trash2 data-icon="inline-start" />}{pending ? 'Удаляем…' : 'Удалить'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
}
