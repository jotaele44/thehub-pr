# RC3 shared controls (fixture page)

**Code:** thehub-pr#435, `federation-design/packages/react/src/controls/`
(`RenameDialog.jsx`, `Menu.jsx`, `ScrollRegion.jsx`).

**Start:**

```bash
cd federation-design/fixture-lab && npm ci && npm run dev
```

Then open `http://localhost:<vite port>/controls.html?repo=thehub-pr&theme=dark`.
Repeat once with `theme=light`.

## Rename dialog (FederationRenameDialog)

| # | Step | Expected |
|---|---|---|
| D1 | Move to the button that opens the rename dialog and activate it. | The dialog opens. The screen reader announces a dialog with its title, then the text field and its label. The current name is fully selected. |
| D2 | Type a new name. | The typing replaces the selected name. |
| D3 | Tab forward repeatedly. | Focus moves through the field and the dialog's buttons and stays inside the dialog (it wraps; it never reaches the page behind). |
| D4 | Press Escape (touch: the Cancel button; VoiceOver iOS: two-finger scrub "Z"). | The dialog closes, the name is unchanged, and focus returns to the button that opened it. That button is announced again. |
| D5 | Reopen, change the name, press Enter. | The dialog closes, the new name shows, and focus returns to the opener. |
| D6 | Reopen and immediately close it twice in quick succession. | It ends closed and focus is on the opener. It does not reopen or close itself afterwards (an RC3 defect that was fixed). |
| D7 | Touch: with the dialog open, try to swipe to content behind it. | Content behind the dialog cannot be reached while it is open. |

## Menu and item menu (FederationMenu, FederationItemMenu, FederationExportMenu)

| # | Step | Expected |
|---|---|---|
| M1 | Move to a menu button. | Announced as a button with a popup (e.g. "Actions, menu button, collapsed"). |
| M2 | Activate it. | Announced as expanded. Focus moves to the first menu item, announced as a menu item with "1 of n". |
| M3 | Arrow down and up through the items. | Each item is announced, and focus wraps at the ends. |
| M4 | Press Escape. | The menu closes and focus returns to the menu button, announced "collapsed". |
| M5 | Open the menu, then scroll the page with the trackpad or a two-finger swipe. | The menu stays open and follows its button. It does not close on scroll (an RC3 defect that was fixed). |
| M6 | Open the menu and click or tap outside it. | The menu closes. |
| M7 | Item menu on a row: open it from the row's "more" button. | The button's name includes the row it acts on (e.g. "More actions for <item>"). |
| M8 | Export menu with "More (n)": activate "More". | An inline disclosure expands. Announced as expanded, and the extra entries are links. |
| M9 | Touch: tap targets of the menu button and items. | Each target is easy to hit; the brief's minimum is 24 px and 44 px is preferred. Record any you miss. |

## Scroll region and responsive label

| # | Step | Expected |
|---|---|---|
| S1 | Tab to the scrolling dataset grid while its content overflows. | It takes focus and is announced with a name (a region or group name, not just "group"). |
| S2 | With it focused, press the arrow keys or Page Down. | The content scrolls. |
| S3 | Make the window wide enough that it no longer overflows, then Tab. | It is no longer a tab stop. |
| S4 | At 320–390 px width (or on a phone), find the button whose visible text shortens. | Its accessible name still begins with the full label. Voice Control: say "Click <visible text>" and it activates. |
