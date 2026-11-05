import { useId } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldGroup, FieldLabel, FieldLegend, FieldSet } from '@/components/ui/field'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { readPreviewSelection } from './previewCatalog'

const marketplaces = [
  { value: 'ozon', label: 'Ozon' }, { value: 'wildberries', label: 'Wildberries' },
  { value: 'aliexpress', label: 'AliExpress' }, { value: 'yandex-market', label: 'Яндекс Маркет' },
]

function MultipleChoice({ name, allLabel, options, value, onChange }: {
  name: string; allLabel: string; options: { value: string; label: string }[]
  value: string[] | null; onChange: (values: string[] | null) => void
}) {
  const id = useId()
  const selected = value ?? options.map((option) => option.value)
  const summary = value === null ? allLabel : !selected.length ? 'Не выбраны'
    : selected.length === 1 ? options.find((option) => option.value === selected[0])?.label ?? selected[0]
      : `Выбрано: ${selected.length}`
  function toggle(option: string, checked: boolean) {
    const next = checked ? [...new Set([...selected, option])] : selected.filter((entry) => entry !== option)
    onChange(options.every((entry) => next.includes(entry.value)) ? null : next)
  }
  return <Field>
    <FieldLabel id={`${id}-label`}>{name}</FieldLabel>
    <Popover>
      <PopoverTrigger asChild><Button variant="outline" className="w-full justify-between" aria-labelledby={`${id}-label`}>
        <span className="min-w-0 truncate">{summary}</span><ChevronDown data-icon="inline-end" aria-hidden="true" />
      </Button></PopoverTrigger>
      <PopoverContent align="start" className="max-h-[min(400px,70dvh)] overflow-y-auto">
        <FieldSet>
          <FieldLegend variant="label">{name}</FieldLegend>
          <FieldGroup data-slot="checkbox-group">
            <Field orientation="horizontal">
              <Checkbox id={`${id}-all`} checked={value === null ? true : selected.length ? 'indeterminate' : false} onCheckedChange={(checked) => onChange(checked === true ? null : [])} />
              <FieldLabel htmlFor={`${id}-all`}>{allLabel}</FieldLabel>
            </Field>
            {options.map((option, index) => <Field orientation="horizontal" key={option.value}>
              <Checkbox id={`${id}-${index}`} checked={selected.includes(option.value)} onCheckedChange={(checked) => toggle(option.value, checked === true)} />
              <FieldLabel htmlFor={`${id}-${index}`}>{option.label}</FieldLabel>
            </Field>)}
          </FieldGroup>
        </FieldSet>
      </PopoverContent>
    </Popover>
  </Field>
}

export function PreviewFilters({ tags }: { tags: string[] }) {
  const [params, setParams] = useSearchParams()
  const id = useId()
  const selectedTags = readPreviewSelection(params, 'tags')
  const availableTags = [...new Set([...tags, ...(selectedTags ?? [])])].sort((a, b) => a.localeCompare(b, 'ru'))
  function setValues(key: string, values: string[] | null) {
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.delete(key)
      if (values !== null) for (const value of values.length ? values : ['']) next.append(key, value)
      return next
    }, { replace: true, flushSync: true })
  }
  const sort = params.get('sort')
  const deal = params.get('deals')
  return <FieldGroup className="gap-5">
    <Field>
      <FieldLabel htmlFor={`${id}-sort`}>Сортировка</FieldLabel>
      <Select value={sort === 'price-asc' || sort === 'price-desc' ? sort : 'default'} onValueChange={(value) => setValues('sort', value === 'default' ? null : [value])}>
        <SelectTrigger id={`${id}-sort`} className="w-full"><SelectValue /></SelectTrigger>
        <SelectContent><SelectGroup>
          <SelectItem value="default">Сначала выгодные</SelectItem>
          <SelectItem value="price-asc">Сначала дешёвые</SelectItem>
          <SelectItem value="price-desc">Сначала дорогие</SelectItem>
        </SelectGroup></SelectContent>
      </Select>
    </Field>
    <MultipleChoice name="Маркетплейсы" allLabel="Все маркетплейсы" options={marketplaces} value={readPreviewSelection(params, 'markets')} onChange={(values) => setValues('markets', values)} />
    <FieldSet className="gap-2">
      <FieldLegend variant="label">Наличие</FieldLegend>
      <Field orientation="horizontal">
        <Checkbox id={`${id}-stock`} checked={params.get('stock') === '1'} onCheckedChange={(checked) => setValues('stock', checked === true ? ['1'] : null)} />
        <FieldLabel htmlFor={`${id}-stock`}>Только в наличии</FieldLabel>
      </Field>
    </FieldSet>
    <MultipleChoice name="Теги" allLabel="Все теги" options={availableTags.map((tag) => ({ value: tag, label: tag }))} value={selectedTags} onChange={(values) => setValues('tags', values)} />
    <Field>
      <FieldLabel htmlFor={`${id}-deals`}>Выгодность</FieldLabel>
      <Select value={deal === 'deals' || deal === 'non_deals' ? deal : 'all'} onValueChange={(value) => setValues('deals', value === 'all' ? null : [value])}>
        <SelectTrigger id={`${id}-deals`} className="w-full"><SelectValue /></SelectTrigger>
        <SelectContent><SelectGroup>
          <SelectItem value="all">Все предложения</SelectItem>
          <SelectItem value="deals">Выгодные</SelectItem>
          <SelectItem value="non_deals">Невыгодные</SelectItem>
        </SelectGroup></SelectContent>
      </Select>
    </Field>
  </FieldGroup>
}
