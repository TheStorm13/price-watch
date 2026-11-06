import { useId } from 'react'
import { ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldGroup, FieldLabel, FieldLegend, FieldSet } from '@/components/ui/field'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { marketplaceOptions, readMarketplaces, readSelection } from './catalogModel'

function MultipleChoice({ name, allLabel, options, value, onChange, required = false }: {
  name: string; allLabel: string; options: { value: string; label: string }[]
  value: string[] | null; onChange: (values: string[] | null) => void
  required?: boolean
}) {
  const id = useId()
  const selected = value ?? options.map((option) => option.value)
  const allSelected = options.every((option) => selected.includes(option.value)) && value === null
  const summary = value === null ? allLabel : !selected.length ? 'Без тегов'
    : selected.length === 1 ? options.find((option) => option.value === selected[0])?.label ?? selected[0]
      : `Выбрано: ${selected.length}`
  function toggle(option: string, checked: boolean) {
    const next = checked ? [...new Set([...selected, option])] : selected.filter((entry) => entry !== option)
    if (required && !next.length) return
    onChange(options.every((entry) => next.includes(entry.value)) ? null : next)
  }
  return <Field>
    <FieldLabel id={`${id}-label`}>{name}</FieldLabel>
    <Popover>
      <PopoverTrigger asChild><Button variant="outline" className="w-full justify-between" aria-labelledby={`${id}-label`}>
        <span className="min-w-0 truncate">{summary}</span><ChevronDown data-icon="inline-end" aria-hidden="true" />
      </Button></PopoverTrigger>
      <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] max-h-[min(400px,70dvh)] overflow-y-auto">
        <FieldSet aria-label={name}>
          <Button type="button" size="sm" variant="outline" className="self-start" disabled={!options.length || required && options.length === 1}
            onClick={() => onChange(allSelected ? required ? [selected[0]] : [] : null)}>
            {allSelected ? required ? 'Оставить один' : 'Снять выбор' : 'Выбрать все'}
          </Button>
          <FieldGroup data-slot="checkbox-group">
            {options.map((option, index) => <Field orientation="horizontal" key={option.value} data-disabled={required && selected.length === 1 && selected.includes(option.value) || undefined}>
              <Checkbox id={`${id}-${index}`} checked={selected.includes(option.value)} disabled={required && selected.length === 1 && selected.includes(option.value)}
                title={required && selected.length === 1 && selected.includes(option.value) ? 'Выберите хотя бы один маркетплейс' : undefined}
                onCheckedChange={(checked) => toggle(option.value, checked === true)} />
              <FieldLabel htmlFor={`${id}-${index}`}>{option.label}</FieldLabel>
            </Field>)}
          </FieldGroup>
        </FieldSet>
      </PopoverContent>
    </Popover>
  </Field>
}

export function CatalogFilters({ tags, params, onChange }: {
  tags: string[]; params: URLSearchParams; onChange: (params: URLSearchParams) => void
}) {
  const id = useId()
  const selectedTags = readSelection(params, 'tags')
  const availableTags = [...new Set([...tags, ...(selectedTags ?? [])])].sort((a, b) => a.localeCompare(b, 'ru'))
  function setValues(key: string, values: string[] | null) {
    const next = new URLSearchParams(params)
    next.delete(key)
    if (values !== null) for (const value of values.length ? values : ['']) next.append(key, value)
    onChange(next)
  }

  const sort = params.get('sort')
  const deal = params.get('deals')
  return <FieldGroup className="gap-5">
    <FieldSet className="gap-2">
      <FieldLegend variant="label">Наличие</FieldLegend>
      <Field orientation="horizontal">
        <Checkbox id={`${id}-stock`} checked={params.get('stock') === '1'} onCheckedChange={(checked) => setValues('stock', checked === true ? ['1'] : null)} />
        <FieldLabel htmlFor={`${id}-stock`}>Только в наличии</FieldLabel>
      </Field>
    </FieldSet>
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
    <MultipleChoice name="Маркетплейсы" allLabel="Все маркетплейсы" options={marketplaceOptions} value={readMarketplaces(params)} required onChange={(values) => setValues('markets', values)} />
    <MultipleChoice name="Теги" allLabel="Все теги" options={availableTags.map((tag) => ({ value: tag, label: tag }))} value={selectedTags} onChange={(values) => setValues('tags', values)} />
  </FieldGroup>
}
