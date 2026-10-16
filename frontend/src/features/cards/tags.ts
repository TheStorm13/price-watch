export function parseTags(value: string, max?: number): string[] {
  const tags = value.split(',').map((tag) => tag.trim()).filter(Boolean)
  if (tags.some((tag) => tag.length > 40)) throw new Error('Каждый тег должен быть не длиннее 40 символов')
  if (new Set(tags.map((tag) => tag.toLocaleLowerCase())).size !== tags.length) throw new Error('Теги не должны повторяться')
  if (max !== undefined && tags.length > max) throw new Error(`Можно указать не больше ${max} тегов`)
  return tags
}
