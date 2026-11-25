# moneysweep-pr: manual script

**Pull request:** [moneysweep-pr#719](https://github.com/jotaele44/moneysweep-pr/pull/719).
Test the RC4 "after" commit `6c9a0fe54ff17ca07344f55528bcb036c9e9e706` or a later
head of that pull request. Write down which one you used.

Read `README.md` in this folder first.

## Type filter select (was unnamed)

Use `/?tab=entities` and `/?tab=graph`.

| # | Step | Expected |
|---|---|---|
| F1 | Tab to the type filter on each tab. | Announced with a name that says what it filters, then its value. The two callers may use different wording; note both. |
| F2 | Open it and choose a type. | Options are announced, and the list or graph updates to the choice. |
| F3 | Touch: open and choose on a phone. | Usable, and the choice applies. |

## Scroll regions (16 containers given the helper)

| # | Page | Step | Expected |
|---|---|---|---|
| R1 | `/` and `/?tab=activity` | Tab to the tab strip under the header (it scrolls sideways at narrow widths). | Focusable, named, the arrow keys scroll it. Every tab is reachable. |
| R2 | `/?tab=campaign-finance`, `/?tab=government-changes` | Tab into the main list area. | Focusable, named, scrolls with the arrow keys or Page Down. |
| R3 | Touch | Swipe the tab strip sideways at 390 px. | It scrolls without the page moving, and every tab can be tapped. |
