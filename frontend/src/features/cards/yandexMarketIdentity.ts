export function parseYandexMarketUrl(value: string): string {
  const url = new URL(value)
  const match = /^\/card\/[^/]+\/([1-9][0-9]{0,19})\/?$/.exec(url.pathname)
  if (url.protocol !== 'https:' || url.host !== 'market.yandex.ru' || url.hash || url.username || url.password || !match) {
    throw new Error('Используйте полную ссылку market.yandex.ru/card/…/SKU')
  }
  return match[1]
}
