import { restoreFocus } from '@/lib/focus'
import { useRef, useState, type FormEvent } from 'react'
import { useDeleteGroup, useSaveGroup } from '../../api/queries'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { AlertDialog, AlertDialogContent, AlertDialogTitle, AlertDialogDescription, AlertDialogHeader, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from '@/components/ui/alert-dialog'
import { Field, FieldLabel, FieldGroup, FieldDescription, FieldSet, FieldLegend } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription } from '@/components/ui/empty'
import { Button } from '../../components/ui/button'
import type { TrackedCardView, ProductGroup } from '../../types/domain'
import { parseTags } from './tags'

interface Props {
  group: ProductGroup | null
  cards: TrackedCardView[]
  initialCardIds?: number[]
  onSaved?: (cardIds: number[]) => void
  onClose: () => void
}

const collator = new Intl.Collator('ru', { numeric: true, sensitivity: 'base' })

export function GroupDialog({ group, cards, initialCardIds = [], onSaved, onClose }: Props) {
  const [name, setName] = useState(group?.name ?? '')
  const [tags, setTags] = useState((group?.tags ?? []).join(', '))
  const [selected, setSelected] = useState<number[]>(group?.cardIds ?? initialCardIds)
  const [search, setSearch] = useState('')
  const [direction, setDirection] = useState<'asc' | 'desc'>('asc')
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const save = useSaveGroup()
  const remove = useDeleteGroup()
  const busy = save.isPending || remove.isPending
  const filteredCards = cards.filter((card) => `${card.title ?? ''} ${card.externalId}`.toLowerCase().includes(search.trim().toLowerCase()))
    .toSorted((left, right) => {
      const order = collator.compare(left.title ?? left.externalId, right.title ?? right.externalId)
      return (direction === 'asc' ? order : -order) || left.id - right.id
    })
  const movingCards = cards.some((card) => selected.includes(card.id) && card.groupId != null && card.groupId !== group?.id)

  const deleteTriggerRef = useRef<HTMLButtonElement>(null)
  const returnFocusRef = useRef(document.activeElement as HTMLElement | null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) { setError('Укажите название группы'); return }
    let parsedTags: string[]
    try { parsedTags = parseTags(tags) } catch (caught) { setError((caught as Error).message); return }
    setError(null)
    try {
      await save.mutateAsync({ id: group?.id, input: { name: name.trim(), cardIds: selected, tags: parsedTags } })
      onSaved?.(selected)
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

  return <Dialog open onOpenChange={(next) => { if (!next && !busy) onClose() }}>
    <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[620px]" onCloseAutoFocus={(event) => { event.preventDefault(); restoreFocus(returnFocusRef.current) }}
      onEscapeKeyDown={(event) => { if (busy) event.preventDefault() }} onInteractOutside={(event) => { if (busy) event.preventDefault() }}>
      <form className="flex flex-col gap-5" onSubmit={(event) => void submit(event)}>
        <DialogHeader>
          <DialogTitle>{group ? 'Изменить группу' : 'Создать группу'}</DialogTitle>
          <DialogDescription>Выберите товары для группы. Сбор цен каждого товара продолжится отдельно.</DialogDescription>
        </DialogHeader>
        <FieldGroup>
          <Field><FieldLabel htmlFor="group-name">Название</FieldLabel><Input id="group-name" autoFocus value={name} maxLength={120} onChange={(event) => setName(event.target.value)} placeholder="Например, бутылка" /></Field>
          <Field><FieldLabel htmlFor="group-tags">Теги группы</FieldLabel><Input id="group-tags" value={tags} onChange={(event) => setTags(event.target.value)} placeholder="Например, кухня, посуда" /><FieldDescription>Разделяйте теги запятыми</FieldDescription></Field>
          <div className="flex gap-3">
            <Field><FieldLabel htmlFor="group-search">Поиск карточек</FieldLabel><Input id="group-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Название или ID" /></Field>
            <Field>
              <FieldLabel htmlFor="group-sort">Сортировка карточек</FieldLabel>
              <Select value={direction} onValueChange={(value) => setDirection(value as 'asc' | 'desc')}>
                <SelectTrigger id="group-sort" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="asc">По названию: А–Я</SelectItem>
                    <SelectItem value="desc">По названию: Я–А</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
          </div>
          <p role="status">Выбрано карточек: {selected.length}</p>
          {movingCards ? <Alert><AlertDescription>Выбранные карточки из других групп перейдут в эту группу. Их история цен сохранится.</AlertDescription></Alert> : null}
          <FieldSet className="max-h-[260px] overflow-y-auto">
            <FieldLegend className="sr-only">Товары группы</FieldLegend>
            <FieldGroup>
              {filteredCards.map((card) => <Field key={card.id} orientation="horizontal" className="group-dialog__card">
                <Checkbox id={`group-card-${card.id}`} checked={selected.includes(card.id)} onCheckedChange={(checked) => setSelected((previous) => checked === true ? [...previous, card.id] : previous.filter((id) => id !== card.id))} />
                <FieldLabel htmlFor={`group-card-${card.id}`}><span><strong>{card.title ?? card.externalId}</strong><FieldDescription>{card.marketplace} · ID: {card.externalId}</FieldDescription></span></FieldLabel>
              </Field>)}
            </FieldGroup>
            {filteredCards.length === 0 ? <Empty><EmptyHeader><EmptyTitle>Карточки не найдены</EmptyTitle><EmptyDescription>Измените или очистите запрос.</EmptyDescription></EmptyHeader></Empty> : null}
          </FieldSet>
        </FieldGroup>
        {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
        <DialogFooter>
          {group ? <Button ref={deleteTriggerRef} type="button" variant="destructive" disabled={busy} onClick={() => setConfirmDelete(true)}>Удалить группу</Button> : null}
          <Button type="button" variant="outline" disabled={busy} onClick={onClose}>Отмена</Button>
          <Button type="submit" disabled={busy}>{busy ? 'Сохраняем…' : 'Сохранить'}</Button>
        </DialogFooter>
      </form>
      <AlertDialog open={confirmDelete} onOpenChange={(next) => { if (!busy) setConfirmDelete(next) }}>
        <AlertDialogContent onCloseAutoFocus={(event) => { event.preventDefault(); restoreFocus(deleteTriggerRef.current) }}>
          <AlertDialogHeader><AlertDialogTitle>Удалить группу?</AlertDialogTitle><AlertDialogDescription>Товары останутся в общем списке. Их история цен сохранится.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Отмена</AlertDialogCancel>
            <AlertDialogAction variant="destructive" disabled={busy} onClick={(event) => { event.preventDefault(); void deleteGroup() }}>Подтвердить удаление</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </DialogContent>
  </Dialog>
}
