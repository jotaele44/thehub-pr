# skywatcher-pr: manual script

**Pull request:** [skywatcher-pr#375](https://github.com/jotaele44/skywatcher-pr/pull/375).
Test the RC4 "after" commit `13015707067dfff519c5daaaf40785d5f84fb167` or a later
head of that pull request. Write down which one you used.

Read `README.md` in this folder first for set-up and recording.

## Mobile navigation toggle (was unnamed on all 22 routes)

Use `/` and `/aircraft` at phone width (or on a phone).

| # | Step | Expected |
|---|---|---|
| N1 | Move to the menu button in the top bar. | Announced as a button with a name like "Open navigation", collapsed. Not just "button". |
| N2 | Activate it. | The navigation opens, the button is announced expanded, and its name changes to "Close navigation" (or similar). |
| N3 | Activate it again. | The navigation closes, the button is announced collapsed, and focus stays on the button. |
| N4 | Touch: tap the button with a thumb. | Easy to hit (44 px target). |

## Scroll regions (10 were unreachable by keyboard)

| # | Page | Step | Expected |
|---|---|---|---|
| R1 | `/` | Tab to the status strip under the top bar (it scrolls sideways at narrow widths). | It takes focus, is announced with a name, and the arrow keys scroll it. |
| R2 | `/airports` | Tab into the table container. | Same as R1: focusable, named, scrolls with the arrow keys. |
| R3 | `/export` | Tab to each command line (`python scripts/...`). | Each takes focus and scrolls sideways with the arrow keys. VoiceOver/NVDA can read the full command. |
| R4 | `/space-track` | Tab to the long list (max height 420 px). | Focusable, named, scrolls. |
| R5 | `/routes` | Tab to the bordered list. | Focusable, named, scrolls. |
| R6 | `/calibration` | Tab once from the top bar. | The main content area takes focus only if it scrolls. It is not an extra empty tab stop. |
| R7 | Touch, any of the above | Swipe inside the region. | It scrolls without the page moving sideways. |

## Sky Target Finder rows (7 name mismatches)

Use `/space-track/sky`.

| # | Step | Expected |
|---|---|---|
| T1 | Move to a row button, e.g. "Jupiter". | Announced as "Jupiter, button", followed (after a pause, or on request) by its detail line as the description. The name is not a long combined string. |
| T2 | Voice Control (macOS or iOS): say "Click Jupiter". | That row activates. |
| T3 | Activate a row. | The same thing happens as with a mouse click. |
| T4 | Touch: tap a row. | Rows are 4 px taller than before; check that taps still land on the intended row. |

## Not in scope

`link-in-text-block` (links in running text distinguished by colour only) still
fires on two routes. Note it if it hinders you, but it is not a regression.
