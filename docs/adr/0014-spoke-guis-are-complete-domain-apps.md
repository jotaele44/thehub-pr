# ADR 0014 — Spoke GUIs are complete domain apps on one shared shell

- **Status:** Proposed
- **Date:** 2026-11-15
- **Deciders:** PRII federation maintainers
- **Scope:** all seven PRII federation repositories
- **Supersedes in part:** [ADR 0001](0001-federated-engines-single-hub.md), the sentences that demote producer dashboards to diagnostic-only
- **Implements:** ADR 0001 Phase 3 ("extract the shared skeleton the producers already clone: a shared UI kit")

## Context

ADR 0001 made the Hub app the single product surface and demoted the six producer frontends to "development and diagnostic tools". Two things have happened since that the ADR did not anticipate.

1. **The parity gate says the opposite.** Every producer except `spiderweb-pr` runs `scripts/check_gui_parity.py` on each pull request. Its rule is that a human-facing capability is not complete until it is usable through *that repository's own* GUI, with an end-to-end test. A surface held to that bar is not diagnostic-only. The two rules cannot both be true, and the one that is enforced in CI is the one that reflects how the repositories are actually built.
2. **The duplication ADR 0001 named was never removed, and it diverged.** The parity checker exists in five variants, its workflow and Playwright config in four or five each, and four repositories carry their own imported token layer (`src/zip-design/`). A shared package, `@pr-federation/react`, exists and is consumed by five producers, but at three different stale versions and for almost nothing beyond empty states. Each new page in each repository re-decides layout, navigation, tokens and how to register the capability.

The cost is not that the producers have GUIs. It is that every GUI change re-opens decisions that should have been made once.

## Decision

**A producer GUI is a complete, supported application for its own domain. All seven GUIs are built from one federation template and one set of rules, owned by the Hub, so that adding a page in any repository is a fixed procedure.**

1. **Roles.** The Hub app remains the only place cross-producer views live (correlation, crossover, the federation graph); that part of ADR 0001 is unchanged. Each producer GUI is the complete GUI for its own domain and must satisfy the parity gate in full.
2. **One shell.** The app shell (navigation, header, inspector, status bar, mobile navigation) is provided by `@pr-federation/react`. A repository supplies a navigation registry and page components; it does not fork the shell.
3. **One token source.** The `--fd-*` tokens in `federation-design/` are the only colour, spacing and layout source. shadcn variables are aliases onto them. A repository's brand accent comes from its `data-repo` attribute. Per-repository token layers are retired when that repository adopts the template.
4. **One rule set, rendered.** The parity checker, its tests and the procedure document are rendered into each repository from `federation-templates/gui/` and guarded by the existing template-drift gate, exactly like the docs-sync rule (ADR 0010).
5. **Repo-specific expansion is declarative.** A repository extends its capability manifest with append-only fragments in `.federation/gui-capabilities.extensions/`. A fragment cannot change discovery, policy, the baseline or a base entry.
6. **`spiderweb-pr` joins the rules, not the code template.** It adopts the manifest, the checker, fragments and the `--fd-*` tokens, and keeps its TypeScript stack and workbench layout.

The rules themselves are in [`docs/FEDERATION_GUI_STANDARD.md`](../FEDERATION_GUI_STANDARD.md). This ADR records why; that document is what a contributor follows.

## Alternatives considered

- **Hold producers to ADR 0001 as written (diagnostic-only shells).** Rejected: it requires relaxing the parity gate and re-scoping pages that already exist and are tested, in exchange for moving every domain workflow into a Hub app that is already three to nine times the size of any producer frontend.
- **Start the GUIs again from a new template.** Rejected: six of seven frontends already share one stack (React, Vite, Tailwind with shadcn, react-query, vitest, Playwright), a versioned token package and a working render-and-drift mechanism. The gap is consolidation and enforcement, not a missing foundation.
- **Convert `spiderweb-pr` to the common stack.** Rejected for now: high regression risk to the Cesium and MapLibre workbench for no gain in the rules, which are stack-independent.

## Consequences

- "Diagnostic-only surface (ADR 0001, Phase 2)" banners in producer READMEs become untrue and are removed as each repository adopts the template.
- The shell must exist before producers can adopt it. It is delivered in `@pr-federation/react` separately from the rules, and the Hub migrates onto it first so that the reference implementation actually uses it.
- Adoption is one repository at a time. A repository receives the rendered files only when it is added to the relevant target set in `federation-templates/targets.yaml`; until then its own copies stand.
- The Hub takes on ownership of the checker's behaviour for every repository. A checker change is now a federation change and must be measured against every producer before it merges.

## Verification

1. `python3 tools/render_federation_templates.py --repo thehub-pr --check --repo-root .` passes with the Hub's checker, test and procedure document rendered from the templates.
2. The canonical checker, run read-only against each producer checkout, reports no new gaps relative to that producer's committed baseline.
3. After a producer adopts: its `template-drift` and `gui-capability-parity` gates pass, its GUI imports no colour that is not a `--fd-*` token or an alias of one, and its navigation is declared in a registry file listed under `discovery.navigation_files`.
