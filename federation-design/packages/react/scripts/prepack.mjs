import { copyFileSync, mkdirSync, existsSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { join, relative } from 'node:path'
import { BUNDLED_STYLES, SEPARATE_STYLES, designRoot, pkgRoot, sourceFiles, stylePath } from './sources.mjs'

const dist = join(pkgRoot, 'dist')
const pkg = JSON.parse(readFileSync(join(pkgRoot, 'package.json'), 'utf8'))
const snapshot = JSON.parse(readFileSync(join(pkgRoot, 'api-snapshot.json'), 'utf8'))
const styleSources = BUNDLED_STYLES.map(stylePath)
const separateStyles = SEPARATE_STYLES.map((name) => ({ from: stylePath(name), to: join(dist, name) }))
const assets = [
  { from: join(designRoot, 'tokens', 'federation.tokens.json'), to: join(dist, 'federation.tokens.json') },
  { from: join(designRoot, 'tokens', 'federation.tokens.schema.json'), to: join(dist, 'federation.tokens.schema.json') },
  { from: join(designRoot, 'test-harness', 'test-harness.contract.json'), to: join(dist, 'test-harness.contract.json') },
]

if (snapshot.packageVersion !== pkg.version) {
  console.error('[prepack] API snapshot and package versions differ')
  process.exit(1)
}
rmSync(dist, { recursive: true, force: true })
mkdirSync(dist, { recursive: true })
for (const path of styleSources) {
  if (!existsSync(path)) {
    console.error(`[prepack] missing canonical style source: ${path}`)
    process.exit(1)
  }
}
writeFileSync(join(dist, 'federation.css'), styleSources.map((path) => readFileSync(path, 'utf8').trim()).join('\n\n') + '\n')
for (const { from, to } of [...assets, ...separateStyles]) {
  if (!existsSync(from)) {
    console.error(`[prepack] missing canonical asset: ${from}`)
    process.exit(1)
  }
  copyFileSync(from, to)
}

const sha256 = (path) => createHash('sha256').update(readFileSync(path)).digest('hex')
const sources = [
  join(pkgRoot, 'package.json'), join(pkgRoot, 'api-snapshot.json'), ...sourceFiles(),
  join(designRoot, 'styles', 'federation.css'), ...styleSources, ...separateStyles.map((style) => style.from), ...assets.map((asset) => asset.from),
]
const manifest = {
  schemaVersion: '1.0.0',
  package: pkg.name,
  version: pkg.version,
  expectedTag: `federation-design-v${pkg.version}`,
  tokenVersion: JSON.parse(readFileSync(join(designRoot, 'tokens', 'federation.tokens.json'), 'utf8')).version,
  apiSnapshotSha256: sha256(join(pkgRoot, 'api-snapshot.json')),
  sourceSha256: Object.fromEntries(sources.map((path) => [relative(designRoot, path).replaceAll('\\', '/'), sha256(path)])),
  mutableReferencesAllowed: false,
}
writeFileSync(join(dist, 'release-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`)
console.log(`[prepack] bundled ${styleSources.length} style sources, ${separateStyles.length} separate stylesheets, ${assets.length} canonical assets and deterministic release manifest`)
