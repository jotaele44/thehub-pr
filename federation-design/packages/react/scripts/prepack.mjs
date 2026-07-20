// prepack: bundle the canonical design-system assets into ./dist so the packed
// tarball is self-contained. The authoritative sources live one level up in
// federation-design/{styles,tokens} (per docs/FEDERATION_DESIGN_SYSTEM_V1.md);
// this copies them in at pack time rather than committing a divergent duplicate.
// Runs automatically on `npm pack` / `npm publish`.
import { copyFileSync, mkdirSync, existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const pkgRoot = join(here, '..')                 // federation-design/packages/react
const designRoot = join(pkgRoot, '..', '..')     // federation-design
const dist = join(pkgRoot, 'dist')

const assets = [
  { from: join(designRoot, 'styles', 'federation.css'), to: join(dist, 'federation.css') },
  { from: join(designRoot, 'tokens', 'federation.tokens.json'), to: join(dist, 'federation.tokens.json') },
]

mkdirSync(dist, { recursive: true })

for (const { from, to } of assets) {
  if (!existsSync(from)) {
    console.error(`[prepack] missing canonical asset: ${from}`)
    process.exit(1)
  }
  copyFileSync(from, to)
  console.log(`[prepack] bundled ${from} -> ${to}`)
}

// Fail loudly if the tokens file is not valid JSON — a corrupt token source
// must not ship in a release tarball.
try {
  JSON.parse(readFileSync(join(dist, 'federation.tokens.json'), 'utf8'))
} catch (err) {
  console.error(`[prepack] federation.tokens.json is not valid JSON: ${err.message}`)
  process.exit(1)
}

console.log('[prepack] design-system assets bundled into ./dist')
