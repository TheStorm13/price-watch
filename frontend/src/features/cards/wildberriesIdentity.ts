export function isWildberriesId(value: string) {
  return /^[1-9][0-9]*$/.test(value) && Number.isSafeInteger(Number(value))
}

export function parseWildberriesUrl(value: string) {
  const url = new URL(value)
  const match = /^\/catalog\/([0-9]+)\/detail\.aspx$/.exec(url.pathname)
  const sizes = url.searchParams.getAll('size')
  if (url.protocol !== 'https:' || !['wildberries.ru', 'www.wildberries.ru'].includes(url.host) ||
      url.username || url.password || url.hash || !match || sizes.length !== 1 ||
      !isWildberriesId(match[1]) || !isWildberriesId(sizes[0])) {
    throw new Error('Укажите полную ссылку Wildberries с единственным size выбранного размера')
  }
  return { nmId: match[1], optionId: sizes[0] }
}
