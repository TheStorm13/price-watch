import { LoaderCircle, MoreVertical, Pause, Play, Trash2 } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'

interface CardActionsMenuProps {
  cardTitle: string
  isActive: boolean
  onToggle: () => Promise<unknown>
  onDelete: () => Promise<unknown>
  bordered?: boolean
}

export function CardActionsMenu({ cardTitle, isActive, onToggle, onDelete, bordered = false }: CardActionsMenuProps) {
  const [open, setOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const actionRef = useRef<HTMLButtonElement>(null)
  const confirmRef = useRef<HTMLButtonElement>(null)
  const menuId = useId()

  useEffect(() => {
    if (!open) return

    actionRef.current?.focus()
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (confirming) {
        setConfirming(false)
        actionRef.current?.focus()
        return
      }
      setOpen(false)
      triggerRef.current?.focus()
    }
    document.addEventListener('pointerdown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [confirming, open])

  useEffect(() => {
    if (confirming) confirmRef.current?.focus()
  }, [confirming])

  async function toggleTracking() {
    setPending(true)
    setError(null)
    try {
      await onToggle()
      setOpen(false)
      triggerRef.current?.focus()
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
      setOpen(false)
    } catch {
      setConfirming(false)
      setError('Не удалось удалить карточку')
    } finally {
      setPending(false)
    }
  }

  const actionLabel = isActive ? 'Приостановить отслеживание' : 'Возобновить отслеживание'

  return (
    <div className="card-actions-menu" ref={rootRef} onClick={(event) => event.stopPropagation()}>
      <button
        ref={triggerRef}
        className={`icon-button${bordered ? ' icon-button--bordered' : ''}`}
        type="button"
        aria-label={`Действия с карточкой ${cardTitle}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => { setError(null); setOpen((value) => !value) }}
      >
        <MoreVertical />
      </button>
      {open ? (
        <div className="card-actions-menu__popover" id={menuId} role="menu" aria-label={`Действия с карточкой ${cardTitle}`}>
          <button ref={actionRef} type="button" role="menuitem" disabled={pending} onClick={() => void toggleTracking()}>
            {pending ? <LoaderCircle className="spin" /> : isActive ? <Pause /> : <Play />}
            <span>{pending ? 'Сохраняем…' : actionLabel}</span>
          </button>
          <div className="card-actions-menu__separator" />
          <button className="card-actions-menu__danger" type="button" role="menuitem" disabled={pending} onClick={() => setConfirming(true)}>
            <Trash2 />
            <span>Удалить карточку</span>
          </button>
          {error ? <p className="card-actions-menu__error" role="alert">{error}</p> : null}
        </div>
      ) : null}
      {confirming ? (
        <div className="confirm-dialog-layer" onClick={(event) => event.stopPropagation()}>
          <button className="confirm-dialog-backdrop" type="button" aria-label="Отменить удаление" onClick={() => setConfirming(false)} />
          <section className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby={`${menuId}-title`} aria-describedby={`${menuId}-description`}>
            <div className="confirm-dialog__icon"><Trash2 /></div>
            <h2 id={`${menuId}-title`}>Удалить карточку?</h2>
            <p id={`${menuId}-description`}>«{cardTitle}» и вся история её цен будут удалены без возможности восстановления.</p>
            <div className="confirm-dialog__actions">
              <button className="button" type="button" disabled={pending} onClick={() => setConfirming(false)}>Отмена</button>
              <button ref={confirmRef} className="button button--danger" type="button" disabled={pending} onClick={() => void deleteCard()}>
                {pending ? <LoaderCircle className="spin" /> : <Trash2 />}
                {pending ? 'Удаляем…' : 'Удалить'}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  )
}
