import { restoreFocus } from '@/lib/focus'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from '@/components/ui/alert-dialog'
import { NativeSelect } from '@/components/ui/native-select'
import { Field, FieldLabel, FieldDescription, FieldGroup } from '@/components/ui/field'
import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import { queryKeys } from '../../api/queries'
import { Button } from '../../components/ui/button'
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
  const deleteTrigger = useRef<HTMLButtonElement>(null)
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
      <Button variant="outline" disabled={busy} onClick={onCreateGroup}>Создать группу</Button>
      <Button variant="outline" disabled={busy || groups.length === 0} onClick={() => setGroupPickerOpen((value) => !value)}>Добавить в группу</Button>
      <Button variant="outline" disabled={busy} onClick={() => void runMany('enable')}>Учитывать в выгодных</Button>
      <Button variant="outline" disabled={busy} onClick={() => void runMany('disable')}>Не учитывать в выгодных</Button>
      <Button ref={deleteTrigger} variant="destructive" disabled={busy} onClick={() => setConfirmDelete(true)}>Удалить выбранные</Button>
      <Button variant="ghost" disabled={busy} onClick={() => { onClear(); setGroupPickerOpen(false); setMessage(null) }}>Снять выбор</Button>
      {groupPickerOpen ? <div className="bulk-card-actions__group-picker">
        <FieldGroup><Field><FieldLabel htmlFor="field-bulkcardactions-1">Существующая группа</FieldLabel><NativeSelect id="field-bulkcardactions-1" value={groupId} onChange={(event) => setGroupId(event.target.value)}>
          <option value="">Выберите группу</option>
          {groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
        </NativeSelect></Field></FieldGroup>
        {movingCards && targetGroup ? <Alert><AlertDescription>Карточки из других групп перейдут в «{targetGroup.name}». История цен сохранится.</AlertDescription></Alert> : null}
        <Button variant="default" disabled={busy || !groupId} onClick={() => void addToGroup()}>Добавить карточки</Button>
      </div> : null}
    </div> : null}
    {message ? <Alert variant={message.error ? 'destructive' : 'default'} role={message.error ? 'alert' : 'status'}><AlertDescription>{message.text}</AlertDescription></Alert> : null}
    <AlertDialog open={confirmDelete} onOpenChange={(next) => { if (!busy) setConfirmDelete(next) }}>
      <AlertDialogContent onCloseAutoFocus={(event) => { event.preventDefault(); restoreFocus(deleteTrigger.current) }}>
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить выбранные карточки?</AlertDialogTitle>
          <AlertDialogDescription>Будет удалено карточек: {selectedIds.length}. Вся их история цен также будет удалена без возможности восстановления.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>Отмена</AlertDialogCancel>
          <AlertDialogAction variant="destructive" disabled={busy} onClick={(event) => { event.preventDefault(); void runMany('delete') }}>{busy ? 'Удаляем…' : 'Удалить карточки'}</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </>
}
