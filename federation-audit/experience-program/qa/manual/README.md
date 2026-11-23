# Manual assistive-technology and touch scripts

These scripts cover the controls fixed in RC3 and RC4. A person runs them with
real assistive technology and real devices, which a container cannot do.
Results go back into `rc3/RC3_GATE.json` and `rc4/RC4_GATE.json`. Until then,
`screen_reader` and `touch_devices` stay `BLOCKED`.

| Script | Covers |
|---|---|
| `design-system-controls.md` | RC3 shared controls on the fixture page: rename dialog, menu, item menu, scroll region, responsive label. No application uses the dialog or menus yet, so the fixture page is the only place to test them. |
| `skywatcher.md`, `aguayluz.md`, `moneysweep.md`, `centinelas.md`, `thehub.md` | The controls each RC4 pull request changed, on the pages where the scan found them. |
| `ovnis.md`, `spiderweb.md` | The same for ovnis-pr#204 and spiderweb-pr#473. Both apps have one address, so the scripts name views and tabs, not pages. |
| `mucaro.md` | A baseline: the RC4 scan found nothing to fix in mucaro-ai, so this is the first check by a person, including four workspaces added after the scan. Its set-up differs; see the script. |

## Set-up, once per session

1. Check out the pull request head named at the top of the script and start the
   app with its launcher (`PRII-<APP>.command` on macOS, `.bat` on Windows) or
   `python3 desktop/setup.py && .venv/bin/python desktop/launch.py --browser`.
   The browser opens on `http://127.0.0.1:<port>/`; the scripts give paths
   relative to that.
2. Write the configuration at the top of your results:

   ```text
   Tester:            Date:
   App and commit:    (repo@sha)
   Device / OS:       (e.g. MacBook Air M2, macOS 26.6 | iPhone 15, iOS 26 | Windows 11 PC)
   Browser + version:
   Assistive tech:    (VoiceOver | NVDA 2026.x | Voice Control | TalkBack | none / touch only)
   Theme:             (dark | light)
   ```

3. Run every step in each configuration you have. The minimum useful set:
   - VoiceOver + Safari on macOS;
   - NVDA + Firefox on Windows;
   - VoiceOver + Safari on an iPhone (touch);
   - TalkBack + Chrome on Android (touch), if available.

## Recording

Mark each step **PASS**, **FAIL** or **NOTE**, with what was actually announced
or what happened, word for word where you can. A FAIL needs the URL, the
viewport (or device orientation) and the configuration line.

| Result | Meaning |
|---|---|
| PASS | Behaved as the "Expected" column says. |
| FAIL | Did not. Say what happened instead. |
| NOTE | Worked, but something is worth reporting (verbose, odd order, slow). |
| N/A | That configuration cannot do the step (say why). |

## Common gestures

| Action | VoiceOver macOS | NVDA | VoiceOver iOS | TalkBack |
|---|---|---|---|---|
| Next element | VO+Right | Down arrow (browse mode) | Swipe right | Swipe right |
| Next form control / button | Tab | Tab, or B / F quick keys | Rotor → Form controls | Reading controls → Controls |
| Activate | VO+Space | Enter / Space | Double-tap | Double-tap |
| Read current item | VO+F3 | NVDA+Tab | Two-finger tap stops speech | n/a |

## Where results go

Send the filled-in tables back. Each gate then records them:
- `checks.screen_reader` and `checks.touch_devices` in `rc3/RC3_GATE.json`;
- the new `manual_checks` block in `rc4/RC4_GATE.json`.

Each check is recorded per configuration: `PASS` only for a configuration where
every step passed, `FAIL` where any step failed, and the rest left `BLOCKED`.
