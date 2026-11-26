# macOS: what is measured, and what is still needed from you

What was measured on your Mac on 2026-11-21 is recorded in
`qa/macos_observations.json`. In short:

- **Startup.** A TheHub launch whose setup marker or built frontend is missing
  reruns the whole setup (pip, then npm) before any window appears: **170.8 s**
  once. After that the setup check takes 0.13–0.20 s, the backend starts in about
  1.7 s, and the app reaches the Dock in about 6 s. centinelas-pr, aguayluz-pr and
  spiderweb-pr have no setup marker on your Mac, so their next launch takes the
  slow path. For centinelas-pr and aguayluz-pr, a fresh setup currently fails on a
  pin conflict (`pydantic-core`).
- **App identity.** The running application is `Python` (`org.python.python`),
  not TheHub (`pr.prii.thehub.launcher`): the bundle hands over to the venv's
  Python. On 2026-11-24 the Dock and menu bar were read on screen with the Mac
  linked to a session, and the two surfaces disagree. The **Dock tile** is
  labelled `PRII-THEHUB` and shows a blue network icon, so the bundle's name and
  icon do reach the Dock. The **menu bar** name and the application menu say
  `Python` (About Python, Quit Python). The 2026-11-21 expectation that the Dock
  would read `Python` was wrong for the tile.
- **Dock menu and Open at Login.** The desktop runtime defines neither. No PRII
  app is a login item. The tile's menu itself has not been seen: right-clicking
  it on 2026-11-24 showed nothing in the session's screenshots.

Steps 2.1 and 2.2 (tile name and icon, menu bar name) are done for TheHub as
above; still open are step 2.2's **Cmd-Tab** entry, step 2.3 and step 2.4 (the
Dock menu and **Open at Login**), and the producer-app repeat. The steps below
close what could not be done remotely. Run them in Terminal.

## 1. Allow the Dock to be read (once, optional)

System Settings → Privacy & Security → Accessibility → add **Terminal** (or the
app that runs the commands) and switch it on. Then this lists the Dock tiles by
name:

```bash
osascript -e 'tell application "System Events" to tell process "Dock" to get name of every UI element of list 1'
```

If you prefer not to grant this, do step 2 by eye instead.

## 2. Dock tile, Dock menu, app switcher (by eye, about 2 minutes)

Quit any running TheHub first (its window → Quit; or `pkill -f "desktop/launch.py"`).

1. In Finder, open `~/Developer/thehub-pr/PRII-THEHUB.app`.
2. When the window appears, record:
   - **Dock tile name** (hover over it): `TheHub` or `Python`?
   - **Dock tile icon**: TheHub's icon or the Python rocket?
   - **Cmd-Tab switcher**: what name and icon?
   - **Menu bar**, the bold app name next to the Apple menu: `TheHub` or `Python`?
3. Right-click the Dock tile and record **every entry in the menu**, in order.
4. Right-click → Options: is **Open at Login** offered? Do **not** tick it. If you
   tick it to test, also check System Settings → General → Login Items: does it
   list `Python` or `TheHub`? Untick afterwards.

Repeat for one producer app, e.g. `~/Developer/centinelas-pr/PRII-CENTINELAS.app`.
Its first launch will try the full setup and may fail on the pin conflict; record
what you see.

## 3. Startup delay you reported

Measure the delay as you experience it, from double-click to a usable window.

1. Quit all PRII apps.
2. Pick the app you saw the delay with.
3. Check whether its next launch takes the slow path:

   ```bash
   ls -la ~/Developer/<repo>/desktop/.setup-complete
   ```

   "No such file" means the next launch reruns setup.
4. Double-click the app and time it with a stopwatch to (a) the Dock tile
   appearing, (b) the Launch Pad, (c) the app content after your Launch Pad
   choice.
5. Double-click it again (second launch) and time the same three points.
6. If (a) or (b) took more than about 15 s, look for the setup log the launcher
   leaves in your temp folder:

   ```bash
   ls -t $TMPDIR/prii-*-setup.* 2>/dev/null | head
   ```

### 3a. MoneySweep and AguaYLuz cold first start

The baseline's 9.4 s first starts of these two were measured on a container's
cold disk and are `UNRESOLVED` in `rc8/RC8_GATE.json` until timed on a real
machine. Only a restart empties the disk cache, so:

1. Restart the Mac. Open nothing else.
2. Check the setup marker as in step 3 above; if it is missing, launch once,
   let setup finish, quit, and restart the Mac again.
3. Double-click `~/Developer/moneysweep-pr/PRII-MONEYSWEEP.app` and time (a)
   and (b) as in step 3. As soon as the Launch Pad shows, press **Launch**
   without changing anything, and time (d): from pressing Launch to the app
   content. Quit it and time a second launch the same way.
4. Restart, and do the same with `~/Developer/aguayluz-pr/PRII-AGUAYLUZ.app`.

The application's backend, and the imports the deferred changes would move,
load only after you press Launch: the Launch Pad appears before them. So the
budget, 3 s for the first start and 1.5 s for later starts, applies to (d),
not to (b). Send one block from section 4 per app, with the (d) line filled
in, and say it was after a restart. If (d) is over budget, the two deferred
start-up changes in `first_start_diagnosis` are worth doing; under it, they
are not.

## 4. What to send back

```text
App (repo, and commit from `git -C ~/Developer/<repo> log -1 --format=%h`):
.setup-complete present before launch: yes / no
Launched right after a Mac restart: yes / no
First launch:  Dock tile ___ s | Launch Pad ___ s | content ___ s
Second launch: Dock tile ___ s | Launch Pad ___ s | content ___ s
Launch pressed → content (d), 3a only: first ___ s | second ___ s
Dock tile name / icon:
Cmd-Tab name / icon:
Menu-bar app name:
Dock menu entries (in order):
Open at Login offered: yes / no; Login Items shows: ___
Anything else:
```

## How the gates record it

- `WS-D D1-D2 Dock menu and app identity` in `rc3/RC3_GATE.json` stays
  `BLOCKED`, with the measured facts attached.
- It can only move to `FAIL` (identity shown as Python, no app Dock menu) or
  `PASS` once a change gives the running process TheHub's identity and a Dock
  menu, and step 2 confirms it on screen.
- The startup figures are measurements of your copy at its local heads, not of
  the RC4 pull request heads.
