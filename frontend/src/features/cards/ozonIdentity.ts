export function parseOzonUrl(value: string): string {
  const url = new URL(value)
  const match = /^\/product\/(?:[^/]*-)?([0-9]+)\/?$/.exec(url.pathname)
  if (!['https://ozon.ru', 'https://www.ozon.ru'].includes(url.origin) || url.username || url.password || url.hash || !match) {
    throw new Error('Используйте полную ссылку https://www.ozon.ru/product/…')
  }
  return match[1]
}
