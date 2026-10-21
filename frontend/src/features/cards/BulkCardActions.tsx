import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import { queryKeys } from '../../api/queries'
import { Button } from '../../components/ui/Button'
import type { MarketplaceCard, ProductGroup } from '../../types/domain'

interface Props {
  selectedIds: number[]
  cards: MarketplaceCard[]
  groups: ProductGroup[]
  onCreateGroup: () => void
  onProcessed: (ids: number[]) => void
  onClear: () => void
}

async function settleCardOperations(ids: number[], operation: (id: number) => Promise<unknown>) {
  const results = await Promise.allSettled(ids.map(operation))
  return {
    succeeded: ids.filter((_id, index) => results[index].status === 'fulfilled'),
    failed: ids.filter((_id, index) => results[index].status === 'rejected'),
  }
}

export function BulkCardActions({ selectedIds, cards, groups, onCreateGroup, onProcessed, onClear }: Props) {
  const queryClient = useQueryClient()
  const [groupPickerOpen, setGroupPickerOpen] = useState(false)
  const [groupId, setGroupId] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null)
  const selectedCards = cards.filter((card) => selectedIds.includes(card.id))
  const targetGroup = groups.find((group) => group.id === Number(groupId))
  const movingCards = selectedCards.some((card) => card.groupId != null && card.groupId !== targetGroup?.id)

  async function refreshQueries() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.cards }),
      queryClient.invalidateQueries({ queryKey: queryKeys.groups }),
      queryClient.invalidateQueries({ queryKey: queryKeys.deals }),
    ])
  }

  async function addToGroup() {
    if (!groupId || busy) return
    setBusy(true)
    setMessage(null)
    try {
      const current = (await api.listGroups()).find((group) => group.id === Number(groupId))
      if (!current) throw new Error('Группа больше не существует')
      await api.updateGroup(current.id, {
        name: current.name,
        tags: current.tags ?? [],
        cardIds: [...new Set([...current.cardIds, ...selectedIds])],
      })
      onProcessed(selectedIds)
      setGroupPickerOpen(false)
      await refreshQueries()
      setMessage({ text: `В группу «${current.name}» добавлено карточек: ${selectedIds.length}`, error: false })
    } catch (reason) {
      setMessage({ text: reason instanceof Error ? reason.message : 'Не удалось добавить карточки в группу', error: true })
    } finally {
      setBusy(false)
    }
  }

  async function runMany(action: 'enable' | 'disable' | 'delete') {
    if (busy || selectedIds.length === 0) return
    const ids = [...selectedIds]
    setBusy(true)
    setMessage(null)
    try {
      const { succeeded, failed } = await settleCardOperations(ids, (id) => action === 'delete'
        ? api.deleteCard(id)
        : api.updateCard(id, { dealsEnabled: action === 'enable' }))
      if (action === 'delete') {
        for (const id of succeeded) queryClient.removeQueries({ queryKey: queryKeys.card(id) })
      }
      onProcessed(succeeded)
      setGroupPickerOpen(false)
      setConfirmDelete(false)
      await refreshQueries()
      const label = action === 'delete' ? 'Удалено' : action === 'enable' ? 'Включено' : 'Исключено'
      const failedNames = failed.map((id) => cards.find((card) => card.id === id)?.title ?? `ID ${id}`)
      setMessage({
        text: failed.length
          ? `${label}: ${succeeded.length}. Не удалось обработать: ${failedNames.join(', ')}. Повторите действие для оставшихся выбранных карточек.`
          : `${label} карточек: ${succeeded.length}`,
        error: failed.length > 0,
      })
    } catch (reason) {
      setMessage({ text: reason instanceof Error ? reason.message : 'Не удалось обновить список карточек', error: true })
    } finally {
      setBusy(false)
    }
  }

  return <>
    {selectedIds.length > 0 ? <div className="bulk-card-actions" role="group" aria-label="Действия с выбранными карточками">
      <strong>Выбрано карточек: {selectedIds.length}</strong>
      <Button disabled={busy} onClick={onCreateGroup}>Создать группу</Button>
      <Button disabled={busy || groups.length === 0} onClick={() => setGroupPickerOpen((value) => !value)}>Добавить в группу</Button>
      <Button disabled={busy} onClick={() => void runMany('enable')}>Учитывать в выгодных</Button>
      <Button disabled={busy} onClick={() => void runMany('disable')}>Не учитывать в выгодных</Button>
      <Button variant="danger" disabled={busy} onClick={() => setConfirmDelete(true)}>Удалить выбранные</Button>
      <Button variant="ghost" disabled={busy} onClick={() => { onClear(); setGroupPickerOpen(false); setMessage(null) }}>Снять выбор</Button>
      {groupPickerOpen ? <div className="bulk-card-actions__group-picker">
        <label className="field"><span>Существующая группа</span><select value={groupId} onChange={(event) => setGroupId(event.target.value)}>
          <option value="">Выберите группу</option>
          {groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
        </select></label>
        {movingCards && targetGroup ? <p>Карточки из других групп перейдут в «{targetGroup.name}». История цен сохранится.</p> : null}
        <Button variant="primary" disabled={busy || !groupId} onClick={() => void addToGroup()}>Добавить карточки</Button>
      </div> : null}
    </div> : null}
    {message ? <p className={message.error ? 'action-error' : 'transfer-page-status transfer-page-status--success'} role={message.error ? 'alert' : 'status'}>{message.text}</p> : null}
    {confirmDelete ? <div className="confirm-dialog-layer">
      <section className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="bulk-delete-title" aria-describedby="bulk-delete-description"
        onKeyDown={(event) => { if (event.key === 'Escape' && !busy) setConfirmDelete(false) }}>
        <h2 id="bulk-delete-title">Удалить выбранные карточки?</h2>
        <p id="bulk-delete-description">Будет удалено карточек: {selectedIds.length}. Вся их история цен также будет удалена без возможности восстановления.</p>
        <div className="confirm-dialog__actions">
          <Button autoFocus disabled={busy} onClick={() => setConfirmDelete(false)}>Отмена</Button>
          <Button variant="danger" disabled={busy} onClick={() => void runMany('delete')}>{busy ? 'Удаляем…' : 'Удалить карточки'}</Button>
        </div>
      </section>
    </div> : null}
  </>
}
