# Monitor the Situation — bounded UI reference audit

## Certification boundary

- **Purpose:** preserve a bounded external interaction reference for the PRII intelligence workspace. This is not a visual-clone specification and is not evidence about Monitor the Situation's private implementation.
- **Reference URL:** `https://monitor-the-situation.com/`
- **Public-page retrieval:** 2026-08-25T02:03:00Z (session time 2026-08-24 22:03 -04:00).
- **Screenshot origin:** eight operator-supplied screenshots in the implementation session. Screenshot bytes are not committed to this repository; dimensions, byte sizes, and SHA-256 digests are frozen below.
- **Exhaustion claim:** **BOUNDED ONLY.** Eight of eleven tutorial steps are directly observed. Steps 9–11 remain `UNKNOWN` because they were not present in the supplied corpus and were not recoverable from the public/indexed page search used in this session.

## Frozen screenshot manifestations

| Order | Local manifestation | Dimensions | Bytes | SHA-256 |
|---:|---|---:|---:|---|
| 1 | `IMG_4310.jpeg` | 1536×712 | 121438 | `692f3468901438b057c3529bfa6126e26507c3d47e59d2a793926f021d0bbb20` |
| 2 | `IMG_4311.jpeg` | 1536×710 | 96132 | `71f0e35ad0a2ac1523cda42a7cff49993ae0cdce794c571102ce79baab092f0a` |
| 3 | `IMG_4312.jpeg` | 1536×710 | 139367 | `b0379d63fe05cdbba58bb506f7c4dedcb1777f617b7a695f1a2cadab25b26653` |
| 4 | `IMG_4313.jpeg` | 1536×709 | 88451 | `811edee3e24323d60d88e20800acf1581b5f8ce3dc30dbedf5121864320fbbb5` |
| 5 | `IMG_4314.jpeg` | 1536×710 | 91781 | `3be5e112b5173cfd1607bf730701162a1180cd3f886b706d63a604704ed2a007` |
| 6 | `IMG_4315.jpeg` | 1536×710 | 92469 | `d5c80d87ade8972d9c58892640d28fec58c51e08833899d1cded72f096afd794` |
| 7 | `IMG_4316.jpeg` | 1536×710 | 88869 | `385f0dc57a0ce58d888ca1b087ddc0ba3260a17eaed5534ebaae266705d1de4e` |
| 8 | `IMG_4317.jpeg` | 1536×710 | 101349 | `3fc4f74e0d3407e61cbbd0eae6b6a50e29678a2dfddd93fd88f4576025a13a92` |

Different hashes prove byte difference only. No canonical identity claim is made between screenshot manifestations beyond their explicit sequence in the supplied session.

## Observed tutorial denominator

| Step | State | Directly observed interaction class |
|---:|---|---|
| 1 | `FACT` | Event Feed; LIVE/REPORTS presentation and active-event scanning |
| 2 | `FACT` | Event Cards; category, severity, location, time, headline |
| 3 | `FACT` | Event Details; summary, confidence, media/signal evidence inspection |
| 4 | `FACT` | Search; title/summary/location search and `/` keyboard shortcut |
| 5 | `FACT` | Time Range; 6-hour and 24-hour views |
| 6 | `FACT` | Live Status; active/high-severity/freshness/headline status surface |
| 7 | `FACT` | Filters & Live Layers; categories/severity plus contextual overlays |
| 8 | `FACT` | Map Options; event markers, live map layers, style/view modes, Watch Zone, 3D Globe, Monitor Mode |
| 9 | `UNKNOWN` | Not present in supplied screenshots; no indexed public tutorial text recovered |
| 10 | `UNKNOWN` | Not present in supplied screenshots; no indexed public tutorial text recovered |
| 11 | `UNKNOWN` | Not present in supplied screenshots; no indexed public tutorial text recovered |

**Arithmetic:** observed 8 + unknown 3 = declared tutorial denominator 11. Observed coverage is 8/11 = 72.727…%. This is not a claim that 72.727% of the whole product was inspected.

## Public-page corroboration

The public page describes a single live map combining global events, aircraft/ships, weather/infrastructure and supporting evidence; it also states that reports are clustered and that confidence can increase with independent corroboration. The static public page explicitly says JavaScript is required to display the interactive map. These statements corroborate the high-level interaction classes but do not expose source code, hidden tutorial steps, private data contracts, or implementation details.

## Reference-use rules

### Allowed

- feed → selection → map/workspace → inspector interaction grammar;
- search, time-range and category/layer filtering;
- explicit freshness/status surfaces;
- evidence/source inspection adjacent to a selected record;
- responsive three-pane composition when viewport space allows;
- compact status badges when the underlying semantic axis is explicit.

### Not allowed / non-binding

- pixel-for-pixel reproduction;
- copying branding, exact palette, typography, iconography, wording, animation, or onboarding copy;
- importing Monitor's S1–S5 scale as a PRII semantic model;
- treating Monitor event clustering as proof of identity;
- inferring source code, private APIs, algorithms, thresholds or data contracts from screenshots;
- inventing tutorial steps 9–11.

## Open residue

`MONITOR_TUTORIAL_STEPS_9_10_11 = UNKNOWN` remains the only unresolved item inside the declared 11-step tutorial denominator. It is not a blocker for implementing independently justified PRII interaction patterns; it is a blocker for claiming complete Monitor tutorial parity or exhaustion.
