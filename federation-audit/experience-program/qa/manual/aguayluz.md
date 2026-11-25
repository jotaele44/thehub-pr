# aguayluz-pr: manual script

**Pull request:** [aguayluz-pr#420](https://github.com/jotaele44/aguayluz-pr/pull/420).
Test the RC4 "after" commit `c60587e210e813a29318ebe761eb7b9c2f281370` or a later
head of that pull request. Write down which one you used.

**Known set-up problem at `c60587e`:** `python3 desktop/setup.py` fails with
"Cannot install fastapi", because `constraints-desktop.txt` pins
`pydantic-core==2.48.0` and `pydantic==2.13.5` needs `pydantic-core==2.46.5`.
Until that is fixed, set up as the scan did: remove the `pydantic-core` line
from a copy of the constraints file and pass the copy to pip.

Read `README.md` in this folder first.

## Filter select boxes (six named, the scan saw one)

Use `/logs` and `/outages`, and any other page with a filter drop-down.

| # | Step | Expected |
|---|---|---|
| F1 | Tab to each filter drop-down. | Each is announced with a name that says what it filters (e.g. "Severity filter"), then its current value. Not "combobox" alone. |
| F2 | Open it and pick a value. | Options are announced. The chosen value is announced, and the list updates. |
| F3 | Touch: open and pick on a phone. | The native picker or popover is usable and the choice applies. |

## Selected range button

| # | Step | Expected |
|---|---|---|
| G1 | On a page with range buttons (e.g. 24h / 7d / 30d), move across them. | The selected one is announced as "pressed" or "selected"; the others are not. |
| G2 | Activate another range. | It becomes pressed and the previous one is no longer pressed. |

## Scroll regions (44 containers given the helper)

| # | Page | Step | Expected |
|---|---|---|---|
| R1 | `/logs` | Tab into the log list (monospace). | Focusable, named, scrolls with the arrow keys. Timestamps are readable (opacity was removed). |
| R2 | `/water-use` | Tab into the table and the 28 rem list. | Each is focusable, named and scrolls. |
| R3 | `/environmental-exposure` | Tab into the main panel. | Focusable only if it scrolls, named. |
| R4 | `/monitoring` | Tab to the incidents box. | Focusable, named; the "No persistent incidents" text is read. |
| R5 | `/water-disruption` | Tab past the top navigation. | `main` takes focus once if it scrolls, and is not an empty extra stop. |
| R6 | Touch | Swipe inside each region. | It scrolls without the page moving. |

## Dim text (312 uses raised to slate-400)

| # | Step | Expected |
|---|---|---|
| C1 | Low-vision check (no screen reader): on `/water-use` and `/`, read the secondary text at arm's length, in bright light and on a phone. | All secondary text is readable. |
| C2 | Does anything that should look secondary now compete with primary text? | NOTE what and where. This is the judgement the scan cannot make. |

## Not in scope

`link-in-text-block` (3 routes) and `svg-img-alt` (1 route) still fire.
