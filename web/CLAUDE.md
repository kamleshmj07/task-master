# Web app notes

Loaded when working under `web/`. Project-wide context is in `../CLAUDE.md`.

## Visual design: "Desk lamp", restyled as "First light" (2026-11-25)

Tokens live at the top of `web/src/index.css`. Mockups: the "Task Master –
First light" canvas (https://claude.ai/artifact/DcuuCsDsedKjBc9RX2fhUD);
the user chose the Soft graphite shade over deep ocean and dusk plum.
The brief: upbeat and new, easy on the eyes, nothing gaudy, simple UX.

- Soft graphite room (`--ink #1e1f24`, `--slate #292b32`), warm paper text
  (`--paper #f2ede3`). One lamp: amber `--lamp #f6c25a` marks **only** the
  next step and keyboard focus. Green = done, red = overdue or lost.
- Goal colours (`--goal-sky` … `--goal-aqua`, stored per goal as `color`)
  are the one bold idea: a dot on task facts and filter chips, a badge and
  progress bar on goal cards. Never on a task row's edge (that is the
  red/green status rail), and never green, red or amber. Set them with
  `data-goal-color` and `--goal`; `GoalTag` renders a goal's name and dot.
- Finishing is rewarded: a finished task on Today sits on a green row and
  its tick glows once (off under reduced motion). Routine ticks are large
  round buttons that turn green.
- View tabs are a segmented bar; the selected tab is paper-filled. The
  current nav item is a filled pill.
- Primary buttons are paper-filled with ink text, never amber.
- One family: Atkinson Hyperlegible Next; tabular figures; sentence case.
- Corners by role: dialogs 16px, panels 12px, controls 8px, chips pill.
- Tasks are rows in one panel per group with a status rail (red overdue,
  green every step done); the next step is the large amber line. Steps form a
  numbered trail (real sequence). One motion: the new next step glows once.
- Copy rules: no middle-dot joins, no ALL-CAPS labels, no arrows glued to text.
- Extra information about a field goes behind an ⓘ button (`InfoTip`), never
  as grey text under it. Build fields with `Field` / `FieldGroup` so label
  rows line up in grids.
- Selected states (`aria-pressed`, `.selected`, `aria-current`) need their
  own `:hover` rule: the generic `button:hover` outranks them otherwise.
- Task rows: title with its facts, then the next step as its own block
  ("Next step" label, amber text, amber left edge).
- Done for the shell, Tasks, Today and onboarding. Goals and Routines
  inherit the tokens; a fuller layout pass was deferred (not needed for
  launch).
- Phones (up to 720px): the main nav becomes a bottom tab bar with icons,
  pop-ups become bottom sheets, the notifications panel spans the screen,
  and rows with actions wrap their buttons under the title.

## Code conventions

- Shared helpers go in `data.ts` / `dates.ts`, not component files
  (fast-refresh lint). Tests mock `@/api` with `vi.mock(..., await import(...))`.
