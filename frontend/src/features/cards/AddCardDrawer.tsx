import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, SelectGroup } from '@/components/ui/select'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { restoreFocus } from '@/lib/focus'
import { useRef, useState, type FormEvent } from 'react'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter } from '@/components/ui/sheet'
import { Field, FieldLabel, FieldGroup, FieldDescription, FieldError, FieldSet, FieldLegend } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Button } from '../../components/ui/button'
import { MarketplaceMark } from '../../components/product/MarketplaceMark'
import { useCreateCard } from '../../api/queries'
import type { Marketplace, TrackedCardView, TrackedVariant } from '../../types/domain'
import { marketplaceLabel } from '../../utils/format'
import { parseTags } from './tags'
import { parseAliExpressUrl } from './aliexpressIdentity'
import { isWildberriesId, parseWildberriesUrl } from './wildberriesIdentity'

export interface CardDrawerProps {
  open: boolean
  onClose: () => void
}

interface Errors {
  externalId?: string
  skuId?: string
  optionId?: string
  url?: string
  tags?: string
}

interface FormValues {
  marketplace: Marketplace
  externalId: string
  primaryVariantId?: number
  title: string | null
  url: string | null
  tags: string[]
}

interface FormProps extends CardDrawerProps {
  card?: TrackedCardView
  variants?: TrackedVariant[]
  isPending: boolean
  onSave: (values: FormValues) => Promise<unknown>
}

export function AddCardDrawer(props: CardDrawerProps) {
  const mutation = useCreateCard()
  return <CardDrawer {...props} isPending={mutation.isPending} onSave={(values) => mutation.mutateAsync({
    marketplace: values.marketplace, externalId: values.externalId,
    title: values.title ?? undefined, url: values.url ?? undefined, tags: values.tags,
  })} />
}

export function CardDrawer({ open, onClose, ...formProps }: FormProps) {
  const returnFocusRef = useRef<HTMLElement | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  return <Sheet open={open} onOpenChange={(next) => { if (!next && !formProps.isPending) onClose() }}>
    <SheetContent ref={contentRef} className="w-[420px] sm:max-w-[420px]" showCloseButton={!formProps.isPending}
      onOpenAutoFocus={(event) => {
        event.preventDefault()
        returnFocusRef.current = document.activeElement as HTMLElement | null
        contentRef.current?.querySelector<HTMLInputElement>('[data-initial-focus]')?.focus()
      }}
      onCloseAutoFocus={(event) => { event.preventDefault(); restoreFocus(returnFocusRef.current) }}>
      <CardForm {...formProps} open={open} onClose={onClose} />
    </SheetContent>
  </Sheet>
}

function CardForm({ card, variants = [], onClose, onSave, isPending }: FormProps) {
  const initialVariant = variants.find((v) => v.id === card?.primaryVariantId)
  const [primaryVariantId, setPrimaryVariantId] = useState(initialVariant?.id)
  const [marketplace, setMarketplace] = useState<Marketplace>(card?.marketplace ?? 'ozon')
  const [externalId, setExternalId] = useState(card?.externalId.split(':')[0] ?? '')
  const [skuId, setSkuId] = useState(card?.marketplace === 'aliexpress' ? initialVariant?.externalId.split(':')[1] ?? '' : '')
  const [optionId, setOptionId] = useState(card?.marketplace === 'wildberries' ? initialVariant?.externalId.split(':')[1] ?? '' : '')
  const [title, setTitle] = useState(card?.title ?? '')
  const [url, setUrl] = useState(card?.url ?? '')
  const [tags, setTags] = useState((card?.tags ?? []).join(', '))
  const [errors, setErrors] = useState<Errors>({})
  const submitting = useRef(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  function validate() {
    const next: Errors = {}
    if (!/^\d+$/.test(externalId.trim())) next.externalId = `Введите числовой ID карточки ${marketplaceLabel[marketplace]}`
    if (!card && marketplace === 'aliexpress' && !/^[0-9]+$/.test(skuId.trim())) next.skuId = 'Введите числовой SKU выбранного варианта'
    if (marketplace === 'wildberries') {
      if (!isWildberriesId(externalId.trim())) next.externalId = 'Введите положительный артикул WB в безопасном диапазоне'
      if (!card && !isWildberriesId(optionId.trim())) next.optionId = 'Введите код выбранного размера WB'
    }
    if (url.trim()) {
      try {
        const parsed = new URL(url)
        if (!['http:', 'https:'].includes(parsed.protocol)) next.url = 'Используйте абсолютный HTTP(S) URL'
        if (marketplace === 'wildberries') {
          const ref = parseWildberriesUrl(url.trim())
          if (ref.nmId !== externalId.trim() || ref.optionId !== optionId.trim()) next.url = 'Ссылка не соответствует артикулу и размеру WB'
        }
        if (marketplace === 'aliexpress') {
          const ref = parseAliExpressUrl(url.trim())
          if (ref.productId !== externalId.trim() || ref.skuId !== skuId.trim()) next.url = 'Ссылка не соответствует ID товара и SKU'
        }
      } catch {
        next.url = 'Введите корректный абсолютный URL'
      }
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (submitting.current || isPending || !validate()) return
    let parsedTags: string[]
    try { parsedTags = parseTags(tags, 2) } catch (error) {
      setErrors((current) => ({ ...current, tags: (error as Error).message }))
      return
    }
    setSaveError(null)
    submitting.current = true
    try {
      const variantId = marketplace === 'aliexpress' ? skuId.trim() : marketplace === 'wildberries' ? optionId.trim() : undefined
      await onSave({
        marketplace, externalId: variantId ? `${externalId.trim()}:${variantId}` : externalId.trim(),
        primaryVariantId, title: title.trim() || null, url: url.trim() || null, tags: parsedTags,
      })
      onClose()
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Не удалось сохранить карточку'
      const field = error && typeof error === 'object' && 'field' in error ? String(error.field) : undefined
      if (field && ['externalId', 'skuId', 'optionId', 'url', 'tags'].includes(field)) {
        setErrors((current) => ({ ...current, [field]: message }))
      }
      setSaveError(message)
    } finally {
      submitting.current = false
    }
  }

  return (
        <form className="flex h-full min-h-0 flex-col" onSubmit={(event) => void submit(event)}>
          <SheetHeader>
            <SheetTitle>{card ? 'Изменить карточку' : 'Добавить карточку'}</SheetTitle>
            <SheetDescription>{card ? 'Измените поля карточки. Маркетплейс и артикул изменить нельзя.' : 'Добавьте товар для отслеживания цены.'}</SheetDescription>
          </SheetHeader>
          <FieldGroup className="min-h-0 flex-1 overflow-y-auto px-4 py-2" inert={isPending}>
            <FieldSet>
              <FieldLegend>Маркетплейс</FieldLegend>
              <RadioGroup disabled={Boolean(card) || isPending} value={marketplace} onValueChange={(value) => { setMarketplace(value as Marketplace); setErrors({}) }}>
                {(['ozon', 'wildberries', 'aliexpress', 'yandex-market'] as const).map((value) => (
                  <Field key={value} orientation="horizontal">
                    <RadioGroupItem id={`marketplace-${value}`} value={value} />
                    <FieldLabel htmlFor={`marketplace-${value}`}>
                      <span><MarketplaceMark marketplace={value} />{!['ozon', 'aliexpress', 'wildberries'].includes(value) ? <FieldDescription>Сбор цен пока недоступен</FieldDescription> : null}</span>
                    </FieldLabel>
                  </Field>
                ))}
              </RadioGroup>
            </FieldSet>
            <Field data-invalid={Boolean(errors.externalId)}>
              <FieldLabel htmlFor="external-id">{marketplace === 'aliexpress' ? 'ID товара' : marketplace === 'wildberries' ? 'Артикул WB' : 'ID карточки'}</FieldLabel>
              <Input id="external-id" readOnly={Boolean(card)} data-initial-focus={card ? undefined : true} value={externalId} onChange={(event) => setExternalId(event.target.value)} inputMode="numeric"
                placeholder={marketplace === 'ozon' ? '1604900984' : 'Введите ID товара'} aria-invalid={Boolean(errors.externalId)} aria-describedby="external-id-hint" />
              {errors.externalId ? <FieldError id="external-id-hint">{errors.externalId}</FieldError> : <FieldDescription id="external-id-hint">Введите числовой ID карточки товара</FieldDescription>}
            </Field>
            {!card && marketplace === 'aliexpress' ? <Field data-invalid={Boolean(errors.skuId)}>
              <FieldLabel htmlFor="sku-id">SKU варианта</FieldLabel>
              <Input id="sku-id" value={skuId} onChange={(event) => setSkuId(event.target.value)} inputMode="numeric" aria-invalid={Boolean(errors.skuId)} aria-describedby="sku-id-hint" />
              {errors.skuId ? <FieldError id="sku-id-hint">{errors.skuId}</FieldError> : <FieldDescription id="sku-id-hint">SKU выбранного варианта из параметра sku_id в ссылке</FieldDescription>}
            </Field> : null}
            {!card && marketplace === 'wildberries' ? <Field data-invalid={Boolean(errors.optionId)}>
              <FieldLabel htmlFor="option-id">Код размера WB</FieldLabel>
              <Input id="option-id" value={optionId} onChange={(event) => setOptionId(event.target.value)} inputMode="numeric" aria-invalid={Boolean(errors.optionId)} aria-describedby="option-id-hint" />
              {errors.optionId ? <FieldError id="option-id-hint">{errors.optionId}</FieldError> : <FieldDescription id="option-id-hint">Вставьте ссылку с параметром size выбранного размера или укажите его код. Каждый размер отслеживается отдельно.</FieldDescription>}
            </Field> : null}
            {card && variants.length > 1 ? <Field>
              <FieldLabel htmlFor="primary-variant">Главный вариант</FieldLabel>
              <Select value={String(primaryVariantId)} onValueChange={(value) => {
                const selected = variants.find((v) => v.id === Number(value))
                if (!selected) return
                setPrimaryVariantId(selected.id)
                setSkuId(selected.externalId.split(':')[1] ?? '')
                setOptionId(selected.externalId.split(':')[1] ?? '')
                setUrl(selected.url ?? '')
                setErrors({})
              }}>
                <SelectTrigger id="primary-variant"><SelectValue /></SelectTrigger>
                <SelectContent><SelectGroup>{variants.map((v) => <SelectItem key={v.id} value={String(v.id)}>{Object.values(v.options).join(' · ') || v.title || v.externalId}</SelectItem>)}</SelectGroup></SelectContent>
              </Select>
              <FieldDescription>Его цена и наличие отображаются в каталоге.</FieldDescription>
            </Field> : null}
            <Field>
              <FieldLabel htmlFor="card-title">Название</FieldLabel>
              <Input id="card-title" data-initial-focus={card ? true : undefined} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Например, смартфон Samsung" />
              <FieldDescription>{['ozon', 'aliexpress', 'wildberries'].includes(marketplace) ? 'Можно оставить пустым — название обновится при сборе' : 'Укажите название: автоматический сбор пока недоступен'}</FieldDescription>
            </Field>
            <Field data-invalid={Boolean(errors.url)}>
              <FieldLabel htmlFor="card-url">URL</FieldLabel>
              <Input id="card-url" value={url} onChange={(event) => {
                const value = event.target.value
                setUrl(value)
                if (marketplace === 'wildberries') {
                  try {
                    const ref = parseWildberriesUrl(value.trim())
                    if (!card) setExternalId(ref.nmId)
                    if (!card) setOptionId(ref.optionId)
                    setErrors({})
                  } catch { /* Validate incomplete links on submit. */ }
                }
                if (marketplace === 'aliexpress') {
                  try {
                    const ref = parseAliExpressUrl(value.trim())
                    if (!card) setExternalId(ref.productId)
                    if (!card) setSkuId(ref.skuId)
                    setErrors({})
                  } catch { /* Validate incomplete links on submit. */ }
                }
              }}
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
          {saveError ? <Alert variant="destructive" className="mx-4"><AlertDescription>{saveError}</AlertDescription></Alert> : null}
          <SheetFooter className="flex-row justify-end">
            <Button variant="outline" type="button" disabled={isPending} onClick={onClose}>Отмена</Button>
            <Button type="submit" disabled={isPending || !externalId.trim() || (!card && marketplace === 'aliexpress' && !skuId.trim()) || (!card && marketplace === 'wildberries' && !optionId.trim())}>{isPending ? (card ? 'Сохранение…' : 'Добавление…') : (card ? 'Сохранить' : 'Добавить')}</Button>
          </SheetFooter>
        </form>
  )
}
