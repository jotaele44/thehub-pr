import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { basename, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const fixture = process.env.PRII_SETUP_FIXTURE
const artifactDir = process.env.PRII_VISUAL_DIR
const repoSlug = process.env.PRII_REPO_SLUG || 'producer'

test.skip(!fixture, 'PRII_SETUP_FIXTURE is only set by desktop visual CI')

test('native setup is accessible, responsive, and visually reviewable', async ({
  page,
}, testInfo) => {
  await page.addInitScript(() => {
    window.pywebview = {
      api: {
        snapshot: async () => ({
          workspace: '/Users/example/Library/Application Support/PRII/Workspace',
          can_return: false,
          diagnostics: [
            {
              label: 'Self-contained runtime',
              status: 'pass',
              detail: 'Bundled app — no separate runtime installation.',
            },
            {
              label: 'Workspace',
              status: 'pass',
              detail: 'Writable workspace selected.',
            },
          ],
        }),
      },
    }
  })

  await page.goto(pathToFileURL(resolve(fixture)).href)
  await page.evaluate(() => window.dispatchEvent(new Event('pywebviewready')))

  await expect(page.getByRole('heading', {
    name: /Setup & Diagnostics/,
    level: 1,
  })).toBeVisible()
  await expect(page.getByText(
    'No Terminal, Python, Node.js, or Git installation required.',
  )).toBeVisible()

  const icon = page.locator('.mark')
  await expect(icon).toBeVisible()
  expect(await icon.evaluate((element) => (
    element.tagName !== 'IMG' || element.naturalWidth > 0
  ))).toBe(true)

  const controls = page.locator('button:visible')
  expect(await controls.count()).toBeGreaterThanOrEqual(5)
  for (const control of await controls.all()) {
    const box = await control.boundingBox()
    expect(box).not.toBeNull()
    expect(box.height).toBeGreaterThanOrEqual(44)
  }

  if (artifactDir) {
    mkdirSync(artifactDir, { recursive: true })
    const file = `${repoSlug}-${testInfo.project.name}-${basename(fixture, '.html')}.png`
    await page.screenshot({
      path: resolve(artifactDir, file),
      fullPage: true,
      animations: 'disabled',
    })
  }

  const axe = await new AxeBuilder({ page }).analyze()
  const blocking = axe.violations.filter(
    ({ impact }) => impact === 'critical' || impact === 'serious',
  )
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([])

  await page.keyboard.press('Tab')
  const focused = page.locator(':focus')
  await expect(focused).toBeVisible()
  expect(await focused.evaluate((element) => (
    getComputedStyle(element).outlineStyle
  ))).not.toBe('none')

  expect(await page.evaluate(() => (
    document.documentElement.scrollWidth > document.documentElement.clientWidth
  ))).toBe(false)
})
