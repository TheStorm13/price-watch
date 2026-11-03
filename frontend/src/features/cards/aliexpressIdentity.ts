export function parseAliExpressUrl(value: string) {
  const url = new URL(value)
  const match = /^\/item\/([0-9]+)\.html$/.exec(url.pathname)
  const skus = url.searchParams.getAll('sku_id')
  if (url.protocol !== 'https:' || url.host !== 'aliexpress.ru' || url.username || url.password || url.hash || !match || skus.length > 1 || (skus.length === 1 && !/^[0-9]+$/.test(skus[0]))) {
    throw new Error('Укажите полную ссылку aliexpress.ru на товар')
  }
  return { productId: match[1], skuId: skus[0] }
}
