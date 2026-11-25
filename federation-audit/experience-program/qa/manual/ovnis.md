# ovnis-pr: manual script

**Pull request:** [ovnis-pr#204](https://github.com/jotaele44/ovnis-pr/pull/204),
merged into `main` as `5ff1ac237c53aa7b37648ea812df8fa44861a70a`. Test the RC4
"after" commit `0d1e12bcb2a3d4e26ab9d3c1d10c2c89fd440948` or a later `main`.
Write down which one you used.

Read `README.md` in this folder first for set-up and recording. Start the app
with `PRII-OVNIS.command` (macOS), `PRII-OVNIS.bat` (Windows) or
`PRII-OVNIS.sh` (Linux).

## How OVNIS is laid out

OVNIS has one address. Its views are not separate pages:

- **860 px and wider:** the map sits beside a tab panel with the tabs Cases,
  Statistics, Candidates and Activity.
- **Narrower than 860 px (and on a phone):** one view at a time, chosen from a
  bottom bar named "OVNIS mobile navigation" with Cases, Map, Statistics,
  Candidates and More. More opens a sheet that holds Activity.

Run each section at both widths if you can. Write the width or device on every
FAIL.

## Scroll regions (7 containers were unreachable by keyboard)

A container that scrolls and holds nothing you can tab to now becomes a tab stop
while it has something to scroll, and only then. It is announced with the name
below and the arrow keys scroll it. A container whose rows are themselves links
or buttons is scrolled by moving through those rows, so it is not an extra stop.

| # | View | Step | Expected |
|---|---|---|---|
| R1 | Activity (narrow) | Open Activity from More, then Tab to the activity content. | Takes focus while it scrolls, is announced as "Activity", and the arrow keys scroll it. |
| R1w | Activity (wide) | Select the Activity tab, then Tab once. | The tab panel takes focus (the tab component makes its panel focusable) and the arrow keys scroll it. Note how it is announced. |
| R2 | Activity | Tab through the filter chips above the list (ALL, NOW, NEXT, QUEUED, BLOCKED, and the sort button); at narrow widths the row scrolls sideways. | Each chip takes focus in turn and the row scrolls to keep it in view. The row itself is not an extra stop, because its chips are buttons. |
| R3 | Candidates | Tab into the candidate list. | Announced as "Candidate list" (while loading, or if the queue cannot be read, the same container is named "Candidates"); the arrow keys scroll it, or moving through its buttons does if the cards have any. |
| R4 | Cases | Tab into the case table. | Announced as "Cases"; you can reach every row and the table scrolls to keep the focused row in view. No empty tab stop before or after the table. |
| R5 | Statistics | Tab into the statistics panel. | Announced as "Statistics"; the arrow keys scroll it. |
| R6 | Any of the above | Make the window wide enough that the container no longer scrolls, then Tab through. | The container is no longer a tab stop. |
| R7 | Touch, any of the above | Swipe inside the container. | It scrolls without the page moving sideways. |

## Muted and dim text (28 contrast failures, dark theme)

The dark theme's muted text was raised from 50% to 58% lightness, and 27 dim
grey labels were made lighter. This is for low-vision readers; use the dark
theme.

| # | Step | Expected |
|---|---|---|
| C1 | In each view, read the secondary text: counts ("… of N cases"), dates, filter labels, empty-state descriptions, the legend under the map. | Readable without leaning in. Note any text that is still hard to read, with the view. |
| C2 | Repeat C1 with the browser zoomed to 200% (or iOS/Android text size at its largest). | Still readable; nothing cut off or overlapping. |
| C3 | macOS "Increase contrast" or Windows contrast theme on, if you use one. | Text stays visible; note anything that disappears. |

## Navigation (no change in RC4; check it as a baseline)

| # | Step | Expected |
|---|---|---|
| N1 | Wide: move to the tab list and switch tabs with the arrow keys. | Each tab is announced with its name and selected state; the panel changes. |
| N2 | Narrow or phone: move to the bottom bar. | Announced as "OVNIS mobile navigation"; each item has its name; the current one is announced as current. |
| N3 | Narrow or phone: activate More, then Activity. | A sheet titled "More" opens and takes focus; choosing Activity shows it; closing the sheet returns focus to More. |
| N4 | Touch: tap each bottom-bar item. | Easy to hit; the right view opens. |

## Known issues: note them, do not fail the script on them

- **Firefox:** after the Map view, the app can fall to its error screen
  (the map fails without WebGL). Recorded in `rc4/RC4_GATE.json`
  `cross_engine`; not fixed yet. If it happens, write NOTE and reload.
- **Safari/WebKit:** the map may report a missing map worker. Same record.

## Not in scope

`link-in-text-block` (links in running text distinguished by colour only) still
fires on five views. Note it if it hinders you, but it is not a regression.
