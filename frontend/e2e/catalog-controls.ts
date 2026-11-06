import { expect, type Page } from '@playwright/test'

/** Select only the requested values; null selects every available option. */
export async function selectMany(page: Page, name: 'Маркетплейсы' | 'Теги', values: string[] | null) {
  await page.getByRole('button', { name, exact: true }).click()
  const group = page.getByRole('group', { name, exact: true })
  if (values === null) {
    const selectAll = group.getByRole('button', { name: 'Выбрать все', exact: true })
    if (await selectAll.count()) await selectAll.click()
  } else {
    for (const value of values) await group.getByRole('checkbox', { name: value, exact: true }).check()
    for (const checkbox of await group.getByRole('checkbox').all()) {
      const id = await checkbox.getAttribute('id')
      const label = await group.locator(`label[for="${id}"]`).innerText()
      if (!values.includes(label)) await checkbox.uncheck()
    }
  }
  await page.keyboard.press('Escape')
  await expect(group).toHaveCount(0)
}
