# thehub-pr: manual script

**Pull request:** [thehub-pr#435](https://github.com/jotaele44/thehub-pr/pull/435).
Test its current head (`28057d8` when this script was written, which includes the
tab bar and phone-width fixes and the satellite pass button fix `cce4832`). Write
down which head you used.

Read `README.md` in this folder first.

## Named select boxes (13)

| # | Page | Step | Expected |
|---|---|---|---|
| F1 | `/` and `/control?tab=tasks` | Tab to each drop-down. | Each is announced with a name that says what it chooses, then its value. |
| F2 | `/control?tab=readiness` (or `/readiness`) | Same. | Same. |
| F3 | `/anomaly-overlap` | Same. | Same. |
| F4 | `/hub` | Same, including the one with a placeholder. | Named; the placeholder is not the only name. |
| F5 | Touch | Open and pick in each. | Usable, and the choice applies. |

## Icon-only buttons

| # | Page | Step | Expected |
|---|---|---|---|
| B1 | `/aguayluz?tab=feed`, `/moneysweep` | Move to the feed refresh button. | "Refresh…, button" (or similar), not just "button". |
| B2 | `/research?tab=assistant` | Move to the send button (disabled while the field is empty), type something, then move to it again. | Named "Send…" in both states, and announced dimmed or unavailable while disabled. |
| B3 | Any page with the memory panel | Open the memory panel, then move to its close button. | "Close memory panel" (or similar). Activating it closes the panel and focus returns to where the panel was opened from. |
| B4 | Footer or header | Move to the GitHub link. | Named "GitHub…", not just "link". |
| B5 | `/tasks` at phone width (below 640 px) | Move to the view toggle buttons. | Each keeps its name (e.g. "List", "Board") even though only an icon is visible. The selected one is announced as pressed or selected. |

## Scroll regions (FederationScrollRegion)

| # | Page | Step | Expected |
|---|---|---|---|
| R1 | `/gis?view=digital-twin` | Tab into the side panel text. | Focusable, named, scrolls with the arrow keys. |
| R2 | `/moneysweep?tab=leaderboards` | Tab into the table. | Focusable, named, scrolls sideways with the arrow keys. |
| R3 | `/crossover` | Tab into the table wrapper (the shared Table component). | Focusable, named, scrolls. |
| R4 | Touch | Swipe inside each region. | It scrolls without the page moving. |

## Tab bar that scrolls sideways (overflow fix)

| # | Page | Step | Expected |
|---|---|---|---|
| T1 | `/ovnis` (any tab) at 768 px, then 390 px, or on a phone | Look at the tab bar. | The page itself does not scroll sideways. The tab bar shows that more tabs exist (a cut-off tab or a fade). NOTE if nothing hints at the hidden tabs. |
| T2 | Same | Tab or arrow through all tabs with the keyboard. | Each hidden tab scrolls into view as it receives focus. The screen reader announces "tab, n of m". |
| T3 | Touch | Swipe the tab bar, then tap the last tab. | It scrolls and the last tab opens. |
| T4 | `/crossover` at 390 px | Use the date inputs. | The date group wraps onto new lines and each date input is announced with its own name (e.g. "Start date", "End date"). |

## Satellite pass buttons (fix is PROVISIONAL)

These buttons appear only when the app has fetched satellite data from
CelesTrak, so you need a working internet connection. During the author's scans
they almost never appeared, and the fix is covered by unit tests only.

| # | Page | Step | Expected |
|---|---|---|---|
| S1 | `/skywatcher?view=sky` | Wait for upcoming passes to list. If none appear, record N/A with the time and network. | Pass buttons are visible ("Show track"). |
| S2 | Same | Move to a pass button. | The name starts with the visible text: "Show track: ISS, pass rising at …". |
| S3 | Voice Control: say "Click Show track". | One pass button activates (or a numbered choice is offered), and the track shows. |
