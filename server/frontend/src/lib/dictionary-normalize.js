// Shared term-normalization utility backed by the DictionaryTerms ledger.
// Resolves a raw/variant term (agency, vendor, person, location, asset,
// acronym, alias) to its canonical normalized_term so that manual pages,
// overlap logic, case/source forms, and agent output stay consistent.
//
// Usage:
//   import { buildDictionaryIndex, normalizeTerm } from "@/lib/dictionary-normalize";
//   const index = buildDictionaryIndex(dictionaryTerms);
//   const canonical = normalizeTerm("PRDOH", { index, category: "Agency", module: "MoneySweep-PR" });

const norm = (s) => String(s ?? "").trim().toLowerCase().replace(/\s+/g, " ");

// Build a fast lookup index from an array of DictionaryTerms records.
// Keys on raw_term + every alias; values carry normalized_term + metadata.
export function buildDictionaryIndex(terms = []) {
  const map = new Map();
  for (const t of terms) {
    if (!t || !t.normalized_term) continue;
    // Deprecated terms still resolve (lineage), but Approved wins on conflict.
    const variants = [t.raw_term, ...(t.aliases || [])].filter(Boolean);
    for (const v of variants) {
      const key = norm(v);
      if (!key) continue;
      const existing = map.get(key);
      if (!existing || (existing.status !== "Approved" && t.status === "Approved")) {
        map.set(key, {
          normalized_term: t.normalized_term,
          category: t.category,
          module: t.module,
          status: t.status,
        });
      }
    }
    // Canonical form maps to itself.
    const canonicalKey = norm(t.normalized_term);
    if (canonicalKey && !map.has(canonicalKey)) {
      map.set(canonicalKey, {
        normalized_term: t.normalized_term,
        category: t.category,
        module: t.module,
        status: t.status,
      });
    }
  }
  return map;
}

// Resolve a raw term to its canonical form. Returns the original term
// (trimmed) when no dictionary match exists — never throws, never invents.
export function normalizeTerm(rawTerm, { index, category, module } = {}) {
  const trimmed = String(rawTerm ?? "").trim();
  if (!trimmed || !index) return trimmed;
  const hit = index.get(norm(trimmed));
  if (!hit) return trimmed;
  // If a category/module is supplied, only honor a match that agrees.
  if (category && hit.category && hit.category !== category) return trimmed;
  if (module && hit.module && hit.module !== module) return trimmed;
  return hit.normalized_term;
}

// Returns true when a raw term resolves to a different canonical form
// (useful for surfacing "normalized from X" hints in the UI).
export function isNormalized(rawTerm, opts) {
  const canonical = normalizeTerm(rawTerm, opts);
  return canonical && norm(canonical) !== norm(rawTerm);
}