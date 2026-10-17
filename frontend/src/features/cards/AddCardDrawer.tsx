import { useEffect, useRef, useState, type FormEvent } from 'react'
import { X } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { MarketplaceMark } from '../../components/ui/MarketplaceMark'
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

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    window.requestAnimationFrame(() => idInputRef.current?.focus({ preventScroll: true }))
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    document.body.classList.add('has-overlay')
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.classList.remove('has-overlay')
      previous?.focus()
    }
  }, [onClose, open])

  if (!open) return null

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
    <div className="drawer-layer">
      <button className="drawer-backdrop" onClick={onClose} aria-label="Закрыть панель" />
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="add-card-title">
        <form className="drawer__form" onSubmit={submit}>
          <div className="drawer__header">
            <h2 id="add-card-title">Добавить карточку</h2>
            <button className="icon-button" type="button" onClick={onClose} aria-label="Закрыть"><X /></button>
          </div>
          <div className="drawer__body">
            <fieldset className="marketplace-choice">
              <legend>Маркетплейс</legend>
              <label className={`marketplace-option${marketplace === 'ozon' ? ' is-selected' : ''}`}>
                <input type="radio" name="marketplace" value="ozon" checked={marketplace === 'ozon'} onChange={() => { setMarketplace('ozon'); setErrors({}) }} />
                <MarketplaceMark marketplace="ozon" />
              </label>
              <label className={`marketplace-option${marketplace === 'wildberries' ? ' is-selected' : ''}`}>
                <input type="radio" name="marketplace" value="wildberries" checked={marketplace === 'wildberries'} onChange={() => { setMarketplace('wildberries'); setErrors({}) }} />
                <span><MarketplaceMark marketplace="wildberries" /><small>Сбор цен пока недоступен</small></span>
              </label>
              <label className={`marketplace-option${marketplace === 'aliexpress' ? ' is-selected' : ''}`}>
                <input type="radio" name="marketplace" value="aliexpress" checked={marketplace === 'aliexpress'} onChange={() => { setMarketplace('aliexpress'); setErrors({}) }} />
                <span><MarketplaceMark marketplace="aliexpress" /><small>Сбор цен пока недоступен</small></span>
              </label>
              <label className={`marketplace-option${marketplace === 'yandex-market' ? ' is-selected' : ''}`}>
                <input type="radio" name="marketplace" value="yandex-market" checked={marketplace === 'yandex-market'} onChange={() => { setMarketplace('yandex-market'); setErrors({}) }} />
                <span><MarketplaceMark marketplace="yandex-market" /><small>Сбор цен пока недоступен</small></span>
              </label>
            </fieldset>

            <label className="field" htmlFor="external-id">
              <span>ID карточки</span>
              <input
                id="external-id"
                ref={idInputRef}
                value={externalId}
                onChange={(event) => setExternalId(event.target.value)}
                inputMode="numeric"
                placeholder={marketplace === 'ozon' ? '1604900984' : 'Введите ID товара'}
                aria-invalid={Boolean(errors.externalId)}
                aria-describedby={errors.externalId ? 'external-id-error' : 'external-id-hint'}
              />
              <small id={errors.externalId ? 'external-id-error' : 'external-id-hint'} className={errors.externalId ? 'field__error' : ''}>
                {errors.externalId ?? 'Введите числовой ID карточки товара'}
              </small>
            </label>

            <label className="field" htmlFor="card-title">
              <span>Название</span>
              <input id="card-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Например, смартфон Samsung" />
              <small>{marketplace === 'ozon' ? 'Можно оставить пустым — название обновится при сборе' : 'Укажите название: автоматический сбор пока недоступен'}</small>
            </label>

            <label className="field" htmlFor="card-url">
              <span>URL</span>
              <input
                id="card-url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder={marketplace === 'ozon' ? 'https://www.ozon.ru/product/...' : marketplace === 'wildberries' ? 'https://www.wildberries.ru/catalog/...' : marketplace === 'aliexpress' ? 'https://aliexpress.ru/item/...' : 'https://market.yandex.ru/product/...'}
                aria-invalid={Boolean(errors.url)}
                aria-describedby={errors.url ? 'url-error' : 'url-hint'}
              />
              <small id={errors.url ? 'url-error' : 'url-hint'} className={errors.url ? 'field__error' : ''}>
                {errors.url ?? 'Ссылка на карточку товара (необязательно)'}
              </small>
            </label>
            <label className="field" htmlFor="card-tags"><span>Теги</span>
              <input id="card-tags" value={tags} onChange={(event) => setTags(event.target.value)} placeholder="Например, кухня, подарок" aria-invalid={Boolean(errors.tags)} />
              <small className={errors.tags ? 'field__error' : ''}>{errors.tags ?? 'До двух тегов через запятую'}</small>
            </label>
          </div>
          <div className="drawer__footer">
            <Button type="button" onClick={onClose}>Отмена</Button>
            <Button variant="primary" type="submit" disabled={mutation.isPending || !externalId.trim()}>
              {mutation.isPending ? 'Добавление…' : 'Добавить'}
            </Button>
          </div>
        </form>
      </aside>
    </div>
  )
}
