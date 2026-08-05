import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const route = process.env.FEDERATION_ROUTE || '/'

test('primary route is accessible and visually stable', async ({ page }) => {
  await page.goto(route)
  await expect(page.locator('body')).toBeVisible()

  const results = await new AxeBuilder({ page }).analyze()
  const blocking = results.violations.filter(({ impact }) => impact === 'critical' || impact === 'serious')
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([])

  await expect(page).toHaveScreenshot('primary-route.png', { fullPage: true })
})

test('keyboard focus remains visible', async ({ page }) => {
  await page.goto(route)
  await page.keyboard.press('Tab')
  const focused = page.locator(':focus')
  await expect(focused).toBeVisible()
  const outlineStyle = await focused.evaluate((element) => getComputedStyle(element).outlineStyle)
  expect(outlineStyle).not.toBe('none')
})

test('page has no horizontal overflow', async ({ page }) => {
  await page.goto(route)
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(overflow).toBe(false)
})
