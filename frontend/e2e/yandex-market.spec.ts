import { expect, test } from '@playwright/test'

test('Маркет запускает начальный сбор после добавления SKU', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/cards')
  await page.getByRole('button', { name: 'Добавить карточку', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Добавить карточку' })
  await dialog.getByRole('radio', { name: 'Яндекс Маркет', exact: true }).check()
  await dialog.getByLabel('ID карточки', { exact: true }).fill('5355099814')
  await dialog.getByLabel('Название', { exact: true }).fill('Брюки Маркет')
  await dialog.getByLabel('URL', { exact: true }).fill('https://market.yandex.ru/card/tovar/5355099814')
  await dialog.getByRole('button', { name: 'Добавить', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('row').filter({ hasText: 'Брюки Маркет' })).toBeVisible()
  const runs = await page.evaluate(async () => {
    const path = '/src/api/mockApi.ts'
    const { mockApi } = await import(/* @vite-ignore */ path)
    return mockApi.listRuns()
  })
  expect(runs[0].totalCount).toBe(1)
  expect(runs[0].current.marketplace).toBe('yandex-market')
  await page.getByRole('link', { name: 'Брюки Маркет', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Обновить эту карточку', exact: true })).toBeVisible()
  await expect(page.getByText('Сбор цен пока недоступен: коннектор не подключён')).toHaveCount(0)
  expect(errors).toEqual([])
})
