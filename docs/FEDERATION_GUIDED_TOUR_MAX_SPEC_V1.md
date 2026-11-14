# Federation Guided Tour MAX — Specification Candidate v1.0

Status: AUDIT_ONLY; NOT CERTIFIED. Scope: 9 Floot projects; 8 matched GitHub repositories, Regenesys GitHub mapping OPEN. Comprehensive verification deferred until after implementation and integration.

## Baseline and invariant
- Never mutate main or mark a project PASS based on component presence.
- Canonical contract uses unique step/target IDs; no heading fallback accepted as exact binding.
- Maintain Spanish and English explanations, route/permission constraints, progress persistence, safe interaction and non-destructive behavior.
- Offline/local execution where supported; no implicit analytics or sensitive DOM capture.
- Require exact SHAs, regression, accessibility, mobile rendering and rollback rehearsal before certification.

## Requirements contract: 150 proposed requirements, 15 domains x 10
CORE: canonical engine; adapter contract; tour manifests; stable IDs; deterministic order; start/pause/resume/restart; back/next/skip/finish; version migration; idempotent transitions; single active tour.
TARGET: unique data-tour-target; exact binding; existence; visibility; enabled state; lazy readiness; collapsed panels; tabs/modals; duplicate rejection; missing target behavior.
VISUAL: moving spotlight; floating callout; collision avoidance; viewport edges; sticky headers; scroll-to-target; resize/scroll tracking; zoom/orientation; stacking; reduced motion.
INTERACT: safe click-through; read-only mode; optional guided action; completion condition; form protection; destructive exclusion; event propagation; timeout; cleanup; no implicit mutation.
NAV: cross-route navigation; route readiness; deep links; browser history; auth redirects; permissions; unavailable routes; module continuity; unsaved-work guard; URL isolation.
PERSIST: per-user storage; project isolation; reload resume; interruptions; completion; skips; version-aware restore; reset tour only; corruption recovery; optional device sync.
ADAPT: first run; contextual mini-tours; roles; beginner/advanced; new-feature prompts; searchable help; task journeys; tour depth; delta tours; nonintrusive replay.
LOCAL: Spanish; English; locale persistence; translation fallback; target descriptions; keyboard; screen reader; focus; contrast/text scaling; RTL-ready architecture.
MOBILE: iPhone; Android; tablet; safe areas; virtual keyboard; touch size; background restoration; offline tour; connectivity transition; low-memory recovery.
CUSTOM: visual editor; reorder; selector; content editor; preview; schema validation; permissions; drafts/published; module visibility; app customization.
FED: nine-project matrix; engine version; adapter compatibility; design tokens; route registry; flags; module identity; cross-project handoff; consumer inventory; migrations.
SEC: least privilege; no unauthorized actions; no evidence mutations; no credentials; no sensitive DOM logging; minimal analytics; consent; provenance; role enforcement; fail closed.
PERF: init budget; observer budget; no uncontrolled polling; limit reflow; cleanup; leak prevention; graceful degradation; deterministic error; budget enforcement; compatibility boundaries.
QA: engine unit; bindings; routes; auth; persistence; accessibility; desktop visual; mobile/tablet; adversarial; exact SHA E2E.
RELEASE: traceability; per-project manifests; source hashes; TERMINAL_READY; platform smoke tests; migration/rollback; rollback rehearsal; independent review; staged safeguards; skill promotion only on PASS.

## Repository coverage snapshot (2026-10-21)
- jotaele44/thehub-pr — no GuidedQuickTour.* in main inventory
- jotaele44/mucaro-ai — no GuidedQuickTour.* in main inventory
- jotaele44/spiderweb-pr — no GuidedQuickTour.* in main inventory
- jotaele44/skywatcher-pr — no GuidedQuickTour.* in main inventory
- jotaele44/ovnis-pr — no GuidedQuickTour.* in main inventory
- jotaele44/aguayluz-pr — no GuidedQuickTour.* in main inventory
- jotaele44/moneysweep-pr — no GuidedQuickTour.* in main inventory
- jotaele44/Corillo-Finder — GuidedQuickTour.tsx, CSS and quickTourState.spec.tsx present in main inventory
- Regenesys Music — GitHub repository mapping OPEN.

## Release sequence
RC0 preserve → RC1 adjudicate source requirements and target manifests → RC2 engine/spotlight → RC3 navigation/state → RC4 accessibility/localization/authoring → RC5 mobile/offline/security → RC6 consumer integration/docs → RC7 final independent verification → RC8 rollback/certify/deploy on PASS → RC9 monitor/promote skill only on PASS.

## States
OPEN, BLOCKED, PROVISIONAL, FAIL, PASS, NOT_APPLICABLE (with independently reviewed justification). Fixed initial proposal denominator 150; expand for discovered requirements, never silently shrink.
