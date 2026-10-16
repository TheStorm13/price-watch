import { useEffect, useState, type FormEvent } from 'react'
import { useDeleteGroup, useSaveGroup } from '../../api/queries'
import { Button } from '../../components/ui/Button'
import type { MarketplaceCard, ProductGroup } from '../../types/domain'

interface Props {
  group: ProductGroup | null
  cards: MarketplaceCard[]
  onClose: () => void
}

export function GroupDialog({ group, cards, onClose }: Props) {
  const [name, setName] = useState(group?.name ?? '')
  const [selected, setSelected] = useState<number[]>(group?.cardIds ?? [])
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const save = useSaveGroup()
  const remove = useDeleteGroup()
  const busy = save.isPending || remove.isPending

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      previous?.focus()
    }
  }, [busy, onClose])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) { setError('Укажите название группы'); return }
    setError(null)
    try {
      await save.mutateAsync({ id: group?.id, input: { name: name.trim(), cardIds: selected } })
      onClose()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось сохранить группу')
    }
  }

  async function deleteGroup() {
    if (!group) return
    setError(null)
    try {
      await remove.mutateAsync(group.id)
      onClose()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось удалить группу')
    }
  }

  return <div className="group-dialog-layer" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onClose() }}>
    <section className="group-dialog" role="dialog" aria-modal="true" aria-label={group ? 'Изменить группу' : 'Создать группу'}>
      <form onSubmit={(event) => void submit(event)}>
        <h2>{group ? 'Изменить группу' : 'Новая группа'}</h2>
        <label className="field"><span>Название</span><input autoFocus value={name} maxLength={120} onChange={(event) => setName(event.target.value)} placeholder="Например, бутылка" /></label>
        <p className="group-dialog__hint">Выберите товары для группы. Сбор цен каждого товара продолжится отдельно.</p>
        <div className="group-dialog__cards" role="group" aria-label="Товары группы">
          {cards.map((card) => <label key={card.id} className="group-dialog__card">
            <input type="checkbox" checked={selected.includes(card.id)} onChange={(event) => setSelected((previous) =>
              event.target.checked ? [...previous, card.id] : previous.filter((id) => id !== card.id))} />
            <span><strong>{card.title ?? card.externalId}</strong><small>{card.marketplace} · ID: {card.externalId}</small></span>
          </label>)}
        </div>
        {error ? <p className="action-error" role="alert">{error}</p> : null}
        {confirmDelete ? <p>Товары останутся в общем списке. Удалить группу?</p> : null}
        <div className="group-dialog__actions">
          {group ? <Button type="button" variant="danger" disabled={busy} onClick={() => confirmDelete ? void deleteGroup() : setConfirmDelete(true)}>{confirmDelete ? 'Подтвердить удаление' : 'Удалить группу'}</Button> : null}
          <Button type="button" disabled={busy} onClick={onClose}>Отмена</Button>
          <Button type="submit" variant="primary" disabled={busy}>{busy ? 'Сохраняем…' : 'Сохранить'}</Button>
        </div>
      </form>
    </section>
  </div>
}
