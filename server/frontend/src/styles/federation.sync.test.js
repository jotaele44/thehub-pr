import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { describe, it, expect } from 'vitest'

// The hub app loads a local copy of the shared federation CSS layer so Vite
// bundles it hermetically from within the app's own tree. The single source of
// truth is federation-design/styles/federation.css (bundled into the
// @pr-federation/react tarball producers consume). This guard fails if the two
// drift — which is exactly the divergence Increment 3b eliminated. If you change
// the design layer, edit the canonical file and re-copy it here.
describe('federation design-system CSS stays in sync with the canonical source', () => {
  const here = dirname(fileURLToPath(import.meta.url))
  const appCopy = resolve(here, 'federation.css')
  const canonical = resolve(here, '../../../../federation-design/styles/federation.css')

  it('local copy is byte-identical to federation-design/styles/federation.css', () => {
    const a = readFileSync(appCopy, 'utf8')
    const b = readFileSync(canonical, 'utf8')
    expect(a).toBe(b)
  })
})
