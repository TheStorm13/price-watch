import { expect, test } from '@playwright/test'

for (const dpr of [1, 1.25, 1.5, 2, 3]) {
  test.describe(`catalog thumbnails DPR ${dpr}`, () => {
    test.use({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: dpr })
    test('prepared images in ordinary/nested rows, prepared grid and detail images', async ({ page }) => {
      const errors: string[] = []
      page.on('pageerror', (error) => errors.push(error.message))
      await page.goto('/cards')
      await expect(page.locator('.cards-table__product').first()).toBeVisible()
      // Exercise the existing mock API in the actual catalog, without a demo route.
      await page.evaluate(async () => {
        // @ts-expect-error Vite source imports are resolved by the browser.
        const { mockApi } = await import('/src/api/mockApi.ts')
        // @ts-expect-error Vite source import.
        const { queryClient } = await import('/src/app/providers.tsx')
        const document = await mockApi.exportCards()
        const original = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="2400"><rect width="1800" height="2400" fill="white"/><rect x="200" y="300" width="1400" height="1800" fill="slategray"/></svg>')}`
        for (const card of document.cards) for (const variant of card.variants) variant.imageUrl = original
        await mockApi.importCards(document)
        await mockApi.createGroup({ name: 'Фото в группе', cardIds: [1, 2] })
        await queryClient.invalidateQueries()
      })
      const photos = page.locator('.cards-table__product img')
      await expect.poll(() => photos.count()).toBe(5)
      for (const photo of await photos.all()) {
        await expect(photo).toHaveAttribute('src', /^blob:/)
        await expect.poll(() => photo.evaluate((image: HTMLImageElement) => [image.naturalWidth, image.naturalHeight])).toEqual([Math.round(68 * dpr), Math.round(68 * dpr)])
        expect(await photo.evaluate((image) => [image.getBoundingClientRect().width, image.getBoundingClientRect().height])).toEqual([68, 68])
        expect(await photo.evaluate((image) => [image.parentElement!.getBoundingClientRect().width, image.parentElement!.getBoundingClientRect().height])).toEqual([68, 68])
      }
      await expect(page.locator('.cards-table__nested img')).toHaveCount(2)
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1440)
      await page.screenshot({ path: `/tmp/price-watch-catalog-thumbnails-dpr${dpr}.png` })
      await page.locator('.cards-table__product .card-identity__link').first().click()
      const detail = page.locator('.detail-header__image img')
      await expect(detail).toHaveAttribute('src', /^blob:/)
      await expect.poll(() => detail.evaluate((image: HTMLImageElement) => image.naturalHeight)).toBe(Math.round(158 * dpr))
      await page.goBack()
      await page.getByRole('radio', { name: 'Сетка' }).click()
      await expect(page.locator('.cards-grid__item img').first()).toHaveAttribute('src', /^blob:/)
      expect(errors).toEqual([])
    })
  })
}
