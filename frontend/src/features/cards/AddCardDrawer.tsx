import { restoreFocus } from '@/lib/focus'
import { useRef, useState, type FormEvent } from 'react'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter } from '@/components/ui/sheet'
import { Field, FieldLabel, FieldGroup, FieldDescription, FieldError, FieldSet, FieldLegend } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Button } from '../../components/ui/button'
import { MarketplaceMark } from '../../components/product/MarketplaceMark'
import { useCreateCard } from '../../api/queries'
import type { Marketplace } from '../../types/domain'
import { marketplaceLabel } from '../../utils/format'
import { parseTags } from './tags'

interface Props {
  open: boolean
  onClose: () => void
}

interface Errors {
  externalId?: string
  url?: string
  tags?: string
}

export function AddCardDrawer({ open, onClose }: Props) {
  const [marketplace, setMarketplace] = useState<Marketplace>('ozon')
  const [externalId, setExternalId] = useState('')
  const [title, setTitle] = useState('')
  const [url, setUrl] = useState('')
  const [tags, setTags] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const idInputRef = useRef<HTMLInputElement>(null)
  const mutation = useCreateCard()

  const returnFocusRef = useRef<HTMLElement | null>(null)

  function validate() {
    const next: Errors = {}
    if (!/^\d+$/.test(externalId.trim())) next.externalId = `Введите числовой ID карточки ${marketplaceLabel[marketplace]}`
    if (url.trim()) {
      try {
        const parsed = new URL(url)
        if (!['http:', 'https:'].includes(parsed.protocol)) next.url = 'Используйте абсолютный HTTP(S) URL'
      } catch {
        next.url = 'Введите корректный абсолютный URL'
      }
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!validate()) return
    let parsedTags: string[]
    try { parsedTags = parseTags(tags, 2) } catch (error) {
      setErrors((current) => ({ ...current, tags: (error as Error).message }))
      return
    }
    mutation.mutate(
      { marketplace, externalId: externalId.trim(), title: title.trim() || undefined, url: url.trim() || undefined, tags: parsedTags },
      {
        onSuccess: () => {
          setMarketplace('ozon')
          setExternalId('')
          setTitle('')
          setUrl('')
          setTags('')
          setErrors({})
          onClose()
        },
        onError: (error) => {
          const field = 'field' in error ? String(error.field) : undefined
          if (field === 'externalId') setErrors({ externalId: error.message })
        },
      },
    )
  }

  return (
    <Sheet open={open} onOpenChange={(next) => { if (!next) onClose() }}>
      <SheetContent className="w-[420px] sm:max-w-[420px]" onOpenAutoFocus={(event) => {
        event.preventDefault()
        returnFocusRef.current = document.activeElement as HTMLElement | null
        idInputRef.current?.focus()
      }} onCloseAutoFocus={(event) => { event.preventDefault(); restoreFocus(returnFocusRef.current) }}>
        <form className="flex h-full min-h-0 flex-col" onSubmit={submit}>
          <SheetHeader>
            <SheetTitle>Добавить карточку</SheetTitle>
            <SheetDescription>Добавьте товар для отслеживания цены.</SheetDescription>
          </SheetHeader>
          <FieldGroup className="min-h-0 flex-1 overflow-y-auto px-4 py-2">
            <FieldSet>
              <FieldLegend>Маркетплейс</FieldLegend>
              <RadioGroup value={marketplace} onValueChange={(value) => { setMarketplace(value as Marketplace); setErrors({}) }}>
                {(['ozon', 'wildberries', 'aliexpress', 'yandex-market'] as const).map((value) => (
                  <Field key={value} orientation="horizontal">
                    <RadioGroupItem id={`marketplace-${value}`} value={value} />
                    <FieldLabel htmlFor={`marketplace-${value}`}>
                      <span><MarketplaceMark marketplace={value} />{value !== 'ozon' ? <FieldDescription>Сбор цен пока недоступен</FieldDescription> : null}</span>
                    </FieldLabel>
                  </Field>
                ))}
              </RadioGroup>
            </FieldSet>
            <Field data-invalid={Boolean(errors.externalId)}>
              <FieldLabel htmlFor="external-id">ID карточки</FieldLabel>
              <Input id="external-id" ref={idInputRef} value={externalId} onChange={(event) => setExternalId(event.target.value)} inputMode="numeric"
                placeholder={marketplace === 'ozon' ? '1604900984' : 'Введите ID товара'} aria-invalid={Boolean(errors.externalId)} aria-describedby="external-id-hint" />
              {errors.externalId ? <FieldError id="external-id-hint">{errors.externalId}</FieldError> : <FieldDescription id="external-id-hint">Введите числовой ID карточки товара</FieldDescription>}
            </Field>
            <Field>
              <FieldLabel htmlFor="card-title">Название</FieldLabel>
              <Input id="card-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Например, смартфон Samsung" />
              <FieldDescription>{marketplace === 'ozon' ? 'Можно оставить пустым — название обновится при сборе' : 'Укажите название: автоматический сбор пока недоступен'}</FieldDescription>
            </Field>
            <Field data-invalid={Boolean(errors.url)}>
              <FieldLabel htmlFor="card-url">URL</FieldLabel>
              <Input id="card-url" value={url} onChange={(event) => setUrl(event.target.value)}
                placeholder={marketplace === 'ozon' ? 'https://www.ozon.ru/product/...' : marketplace === 'wildberries' ? 'https://www.wildberries.ru/catalog/...' : marketplace === 'aliexpress' ? 'https://aliexpress.ru/item/...' : 'https://market.yandex.ru/product/...'}
                aria-invalid={Boolean(errors.url)} aria-describedby="url-hint" />
              {errors.url ? <FieldError id="url-hint">{errors.url}</FieldError> : <FieldDescription id="url-hint">Ссылка на карточку товара (необязательно)</FieldDescription>}
            </Field>
            <Field data-invalid={Boolean(errors.tags)}>
              <FieldLabel htmlFor="card-tags">Теги</FieldLabel>
              <Input id="card-tags" value={tags} onChange={(event) => setTags(event.target.value)} placeholder="Например, кухня, подарок" aria-invalid={Boolean(errors.tags)} aria-describedby="tags-hint" />
              {errors.tags ? <FieldError id="tags-hint">{errors.tags}</FieldError> : <FieldDescription id="tags-hint">До двух тегов через запятую</FieldDescription>}
            </Field>
          </FieldGroup>
          <SheetFooter className="flex-row justify-end">
            <Button variant="outline" type="button" onClick={onClose}>Отмена</Button>
            <Button type="submit" disabled={mutation.isPending || !externalId.trim()}>{mutation.isPending ? 'Добавление…' : 'Добавить'}</Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  )
}
