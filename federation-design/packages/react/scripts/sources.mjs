// The one place that says which files make up this package.
//
// prepack.mjs, verify.mjs and the tests each used to carry their own copy of
// these lists, so a new stylesheet or source directory could ship without
// being bundled, hashed or checked. Add a file here and all three follow.
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
export const pkgRoot = join(here, '..')
export const designRoot = join(pkgRoot, '..', '..')

// Concatenated, in this order, into dist/federation.css (the `./styles.css` export).
export const BUNDLED_STYLES = ['foundation.css', 'primitives.css', 'states.css', 'shell.css']
// Shipped as their own dist files and package exports; never concatenated.
export const SEPARATE_STYLES = ['shadcn-bridge.css']

export const stylePath = (name) => join(designRoot, 'styles', name)
export const readBundledCss = () => BUNDLED_STYLES.map((name) => readFileSync(stylePath(name), 'utf8')).join('\n')

// Every source file that ships in the tarball, for the release manifest.
export function sourceFiles(dir = join(pkgRoot, 'src')) {
  const out = []
  for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) out.push(...sourceFiles(path))
    else if (/\.(jsx?|mjs)$/.test(entry.name)) out.push(path)
  }
  return out
}

const stripComments = (source) => source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1')

// Names a module exports, following `export * from` and `export { a } from`.
// Deliberately small: it understands the export forms this package uses and
// throws on anything else, so an unrecognised form fails verify instead of
// silently hiding an export from the API snapshot check.
export function exportedNames(entry, seen = new Set()) {
  const file = resolve(entry)
  if (seen.has(file)) return new Set()
  seen.add(file)
  if (!existsSync(file)) throw new Error(`export scan: missing module ${file}`)
  const source = stripComments(readFileSync(file, 'utf8'))
  const names = new Set()
  for (const match of source.matchAll(/^export\s+(?:async\s+)?(?:function\*?|const|let|var|class)\s+([A-Za-z_$][\w$]*)/gm)) names.add(match[1])
  for (const match of source.matchAll(/^export\s+\*\s+from\s+['"]([^'"]+)['"]/gm)) {
    for (const name of exportedNames(join(dirname(file), match[1]), seen)) names.add(name)
  }
  for (const match of source.matchAll(/^export\s*\{([^}]*)\}(?:\s*from\s*['"][^'"]+['"])?/gm)) {
    for (const part of match[1].split(',').map((value) => value.trim()).filter(Boolean)) {
      const [, local, alias] = part.match(/^([A-Za-z_$][\w$]*)(?:\s+as\s+([A-Za-z_$][\w$]*))?$/) || []
      if (!local) throw new Error(`export scan: cannot parse "${part}" in ${file}`)
      names.add(alias || local)
    }
  }
  const recognised = /^export\s+(?:(?:async\s+)?(?:function\*?|const|let|var|class)\s|\*\s+from\s|\{)/
  for (const line of source.split('\n')) {
    if (/^export\s/.test(line) && !recognised.test(line)) throw new Error(`export scan: unsupported export form in ${file}: ${line.trim()}`)
  }
  return names
}

export const publicExports = () => exportedNames(join(pkgRoot, 'src', 'index.jsx'))
