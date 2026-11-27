import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { basename, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const fixture = process.env.PRII_LAUNCHPAD_FIXTURE
const artifactDir = process.env.PRII_VISUAL_DIR
const repoSlug = process.env.PRII_REPO_SLUG || 'producer'

test.skip(!fixture, 'PRII_LAUNCHPAD_FIXTURE is only set by desktop visual CI')

// A representative two-mode snapshot. The page under test is the producer's
// real rendered Launch Pad; only the bridge that feeds it is stubbed.
const snapshot = {
  app_title: 'Producer',
  tagline: 'What this producer covers',
  summary: 'A short paragraph saying what the app is for.',
  highlights: ['First capability', 'Second capability'],
  status: [
    { label: 'Workspace', value: 'Ready', status: 'pass', detail: '/Users/example/Workspace' },
    { label: 'Records', value: 'Empty', status: 'info', detail: 'No data has been loaded yet.' },
    { label: 'Index', value: 'Stale', status: 'warn', detail: 'Rebuild recommended.' },
  ],
  has_modes: true,
  mode: 'guest',
  guest: { label: 'Guest', description: 'Read-only.' },
  operator: { label: 'Operator', description: 'May change data.' },
  passphrase_set: true,
  start_pages: [
    { route: '/', label: 'Home', description: 'The landing page.' },
    { route: '/map', label: 'Map', description: 'The map view.' },
  ],
  start_route: '/',
  options: [
    { id: 'offline', label: 'Work offline', help: 'Skip live feeds.', kind: 'toggle',
      choices: [], operator_only: false, placeholder: '', default: false, value: false },
    { id: 'level', label: 'Detail level', help: '', kind: 'choice',
      choices: [['info', 'Normal'], ['debug', 'Verbose']], operator_only: false,
      placeholder: '', default: 'info', value: 'info' },
    { id: 'api_key', label: 'Service key', help: 'For live lookups.', kind: 'secret',
      choices: [], operator_only: true, placeholder: '', default: '', value: '' },
  ],
  skip: false,
  first_visit: true,
}

test('launch pad is accessible, responsive, and sends the chosen session', async ({
  page,
}, testInfo) => {
  await page.addInitScript((state) => {
    window.pywebview = {
      api: {
        launchpad_snapshot: async () => state,
        launchpad_launch: async (choices) => {
          window.__launched = choices
          return { ok: true }
        },
        launchpad_set_passphrase: async () => ({ passphrase_set: true }),
        open_setup: () => {},
      },
    }
  }, snapshot)

  await page.goto(pathToFileURL(resolve(fixture)).href)
  await page.evaluate(() => window.dispatchEvent(new Event('pywebviewready')))

  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByText('Launch Pad', { exact: true }).first()).toBeVisible()
  await expect(page.getByText(snapshot.summary)).toBeVisible()
  await expect(page.locator('#rows .row')).toHaveCount(3)

  const icon = page.locator('.mark')
  await expect(icon).toBeVisible()
  expect(await icon.evaluate((element) => (
    element.tagName !== 'IMG' || element.naturalWidth > 0
  ))).toBe(true)

  // A guest cannot touch an operator-only option, and is not asked to unlock.
  await expect(page.getByRole('radio', { name: /Guest/ })).toBeChecked()
  await expect(page.locator('#option-api_key')).toBeDisabled()
  await expect(page.locator('#unlock')).toBeHidden()

  // While an option is locked for a guest, its label and help text must stay
  // readable in both colour schemes; only the disabled control is dimmed.
  for (const colorScheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme })
    const guestAxe = await new AxeBuilder({ page }).analyze()
    const guestBlocking = guestAxe.violations.filter(
      ({ impact }) => impact === 'critical' || impact === 'serious',
    )
    expect(guestBlocking, `${colorScheme}: ${JSON.stringify(guestBlocking, null, 2)}`).toEqual([])
  }
  await page.emulateMedia({ colorScheme: 'light' })

  await page.getByRole('radio', { name: /Operator/ }).check()
  await expect(page.locator('#option-api_key')).toBeEnabled()
  await expect(page.getByLabel('Operator passphrase')).toBeVisible()

  for (const control of await page.locator('button:visible').all()) {
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

  expect(await page.evaluate(() => (
    document.documentElement.scrollWidth > document.documentElement.clientWidth
  ))).toBe(false)

  await page.getByLabel('Starting page').selectOption('/map')
  await page.getByLabel('Work offline').check()
  await page.getByLabel('Operator passphrase').fill('correct horse')
  await page.getByRole('button', { name: 'Launch', exact: true }).click()
  await expect.poll(() => page.evaluate(() => window.__launched)).toEqual({
    mode: 'operator',
    start_route: '/map',
    options: { offline: true, level: 'info', api_key: '' },
    passphrase: 'correct horse',
    skip: false,
  })
})
