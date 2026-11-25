# spiderweb-pr: manual script

**Pull request:** [spiderweb-pr#473](https://github.com/jotaele44/spiderweb-pr/pull/473),
merged into `main` as `7c65cfeef93e70a07448f4d86a2798894a7acd99`. Test the RC4
"after" commit `b0427630f2e35741c02c5c93770398dfe83e61fc` or a later `main`.
Write down which one you used. The merge also brought `main` changes made after
the scanned commit; if you test `main`, anything outside this script was not
scanned.

Read `README.md` in this folder first for set-up and recording. Start the app
with `PRII-SPIDERWEB.command` (macOS), `PRII-SPIDERWEB.bat` (Windows) or
`PRII-SPIDERWEB.sh` (Linux).

## How Spiderweb is laid out

One address. A tab list named "Workbench modules" switches between Command,
Finance, Spatial, Anomaly, Graph and Query. Around the module are a left rail,
an inspector on the right and a timeline at the bottom. `[` toggles the left
rail and `]` the inspector when you are not typing in a field.

**Below 768 px the left rail, the inspector and the timeline are hidden.** The
timeline sections below need 768 px or wider.

## Timeline event buttons (5 name mismatches)

The event markers on the timeline showed "T3 DEMO-EV-1" but were named "Event
DEMO-EV-1: …", so a voice-control user saying what they saw did not reach them.
They are now named "<tier> <id> event: <label> on <time>", which starts with
the visible text.

| # | Step | Expected |
|---|---|---|
| E1 | Move to the list "Timeline events" and to its first button. | Announced starting with what is shown, for example "T3 DEMO-EV-1 event: … on …, button". |
| E2 | Voice Control (macOS or iOS): say "Click T3 DEMO-EV-1" (use the text you see). | That event is selected. |
| E3 | Activate an event with the keyboard. | It becomes the selection: the inspector shows it and the change is announced or can be found by moving to the inspector. Note what is announced. |
| E4 | Move to the timeline slider and use Left/Right, Shift+Left/Right, Home, End. | The cursor date moves by one day, seven days, to the start, to the end; the date is announced. The event buttons are separate from the slider, not inside it. |

## Recenter PR (1 name mismatch)

| # | Step | Expected |
|---|---|---|
| S1 | Open Spatial and move to the button that shows "Recenter PR". | Announced as "Recenter PR: recenter the map on Puerto Rico, button". |
| S2 | Voice Control: say "Click Recenter PR". | The map recenters on Puerto Rico. |
| S3 | Move to "Show layers" / "Hide layers" and activate it. | The name follows the state; the layer panel opens and closes. |

## Selections the scan opened (no failures found; check them by hand)

| # | Module | Step | Expected |
|---|---|---|---|
| X1 | Finance | Move into the contract table and select a row with the keyboard. | Rows take focus; Enter or Space selects one; the inspector shows it. |
| X2 | Anomaly | Select a cluster card with the keyboard. | It can be reached and selected without a mouse. If not, FAIL and say which card. |
| X3 | Graph | Select a node with the keyboard. | Same as X2. If nodes cannot be reached without a mouse, FAIL. |
| X4 | Query | Move to "RUN QUERY" and activate it. | It runs (stub data in a fresh workspace); while running the button reads "STOP"; the result is announced or can be found next. |
| X5 | Any (top command bar) | Activate the theme button ("Switch to light theme"). | The theme changes and the button is then named "Switch to dark theme". Check the light theme's text is readable. |
| X6 | Any | Press `[` and `]` (not while typing), then use "Toggle left rail" and "Toggle inspector". | The rail and inspector hide and show; focus is not lost into a hidden panel. |
| X7 | Any | Switch modules with the keyboard in "Workbench modules". | Each tab is announced with its name and selected state; the module panel changes. Note whether arrow keys or Tab move between tabs. |

## Phone and touch

| # | Step | Expected |
|---|---|---|
| P1 | On a phone (or below 768 px), go through all six modules. | Each module is usable. The timeline, rail and inspector are not shown at this width. Write NOTE with what a phone user cannot reach; this is a known layout choice, not a FAIL. |
| P2 | Tap the module tabs, "Recenter PR" and "Show layers". | Easy to hit; nothing needs a precise tap. |
| P3 | Pan and pinch the Spatial map. | The map moves; the page does not scroll sideways. |

## Not in scope

`region` and `landmark-unique` (moderate) still fire, unchanged.
