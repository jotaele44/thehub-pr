# centinelas-pr: manual script

**Pull request:** [centinelas-pr#198](https://github.com/jotaele44/centinelas-pr/pull/198).
Test the RC4 "after" commit `d96863d1e8ae0df32874a1519acd86f50b25e173` or a later
head of that pull request. Write down which one you used.

**Known set-up problem at `d96863d` and on current `main`:**
`python3 desktop/setup.py` fails with "Cannot install fastapi", because
`constraints-desktop.txt` pins `pydantic-core==2.48.0` and `pydantic==2.13.5`
needs `pydantic-core==2.46.5`. Until that is fixed, set up as the scan did:
remove the `pydantic-core` line from a copy of the constraints file and pass the
copy to pip.

Read `README.md` in this folder first.

## Brand link and language toggle (name and visible text disagreed)

These appear in the top bar on every page; use `/`.

| # | Step | Expected |
|---|---|---|
| L1 | Move to the brand link. | Its name starts with the visible brand text (e.g. "Centinelas…"), then "link". |
| L2 | Voice Control: say "Click Centinelas". | The link activates and goes to `/`. |
| L3 | Move to the language toggle. | Its name starts with the code it shows (e.g. "ES, change language" or "ES — Cambiar idioma"). |
| L4 | Voice Control: say "Click ES". | The language changes. The toggle now shows the other code and its name follows. |
| L5 | Repeat L1–L4 after switching to the other language. | The names are in the new language and still start with the visible text. |

## Phase pills (contrast, per theme)

The scan checked the **dark theme only**. The light-theme result was reasoned
from the colour shades and has never been measured.

| # | Step | Expected |
|---|---|---|
| P1 | Dark theme: find the phase pills (the page where phases are listed, e.g. `/`). | Readable. |
| P2 | Switch to the light theme. Read each pill colour. | Readable. If you can, check each pill with a contrast checker (e.g. Colour Contrast Analyser); 4.5:1 or more for small text is expected. Record the ratios. |
| P3 | Screen reader on a pill. | The phase name is read; colour is not the only carrier of meaning. |

## Not from this change

Undersized controls on `/handoff` rose from 2732 to 2788 page-load occurrences
between the scans. NOTE any tap target there you find hard to hit.
