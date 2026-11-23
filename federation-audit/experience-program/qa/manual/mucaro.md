# mucaro-ai: manual script (baseline)

**No RC4 change.** The scan of `4fc7b87d368064707493f9f745062a612e9cfbfe` found
no accessibility violation of any impact in its seven views at seven widths, so
nothing was fixed (`rc4/mucaro_scan.json`). A clean scan is not a screen-reader
pass: this script is the first check by a person. Test the current `main` and
write down its commit.

`main` has changed since the scan. It now has ten workspaces; **GIS, OCR, Code
and Artifacts were added after the scan and were never scanned**. Treat
anything you find there as new, not as a regression.

Read `README.md` in this folder for recording. Set-up differs from the PRII
apps: double-click `Mucaro AI Setup.app` (macOS) or `Mucaro AI.exe` (Windows)
in the checkout. It opens Mucaro in its own native window, not a browser tab.
The first start downloads its runtime and takes a few minutes.

## How Múcaro is laid out

One address. A sidebar named "Primary" holds "New chat", the
workspaces (Chat, Workbench, Sources, GIS, OCR, Code, Memory, Provenance,
Artifacts, Settings), "Background tasks", a "Filter conversations" search and
the "Conversations" list. On a narrow window or phone the sidebar is hidden
behind a menu button.

## Navigation

| # | Step | Expected |
|---|---|---|
| N1 | Move into the sidebar. | Announced as navigation "Primary". |
| N2 | Move through the workspace buttons and activate each one. | Each is announced with its name; the current one as current page; the workspace opens. |
| N3 | Narrow window or phone: move to the menu button. | Announced as "Open navigation", collapsed. |
| N4 | Activate it. | The sidebar opens and the button is announced expanded. Its name stays "Open navigation" while open: note whether that confuses you (a NOTE, not a FAIL). |
| N5 | With the sidebar open, choose a workspace. | The sidebar closes and the workspace opens. Note where focus lands. |
| N6 | With the sidebar open, press Escape, or tap outside it. | It closes. Note whether Escape works and where focus goes. |
| N7 | Touch: tap the menu button and each workspace. | Easy to hit. |

## Chat

| # | Step | Expected |
|---|---|---|
| C1 | Open Chat and move to the message field. | Announced as "Message Mucaro", a multi-line text field. |
| C2 | Type a question and move to the send button. | Announced as "Send message, button" (visible text "Send"). While a turn is running it is "Queue message" and a "Stop the current turn" button appears. |
| C3 | Send it, and follow the answer. | The new message and the answer can be found and read. Note whether the answer is announced when it arrives, or has to be found. |
| C4 | Open the mode button beside the field. | A list named "Execution mode" opens; each mode is announced with its selected state; choosing one closes the list. |
| C5 | Voice Control: say "Click Send". | The message is sent. |
| C6 | Touch: type with the on-screen keyboard and send. | The field and send button stay visible above the keyboard. |

## Other workspaces

| # | Workspace | Step | Expected |
|---|---|---|---|
| W1 | Sources | Move through the list of sources and open one. | Each is announced with a name; opening shows its details. |
| W2 | Provenance | Move through the entries. | Each entry can be reached and read. |
| W3 | Settings | Move through every control and change one setting. | Every control is announced with a name and its value; the change is confirmed. |
| W4 | Background tasks | Open it and close it. | It opens with a heading; closing returns focus to "Background tasks". |
| W5 | GIS, OCR, Code, Artifacts | Open each and move through it. | Every control has a name. These were not scanned: record anything you find. |
| W6 | Conversations | Type in "Filter conversations", then open a conversation from the list. | The list narrows; the open conversation is announced as current. |

## When the app is locked

| # | Step | Expected |
|---|---|---|
| L1 | If Múcaro asks for an access token when it opens (its locked state), move around before entering it. | The sidebar is not reachable while locked (it is marked inert). The token field and its buttons can be reached, are named, and an error is announced if the token is refused. Note what you hear. |
