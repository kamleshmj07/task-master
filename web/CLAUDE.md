# Web app notes

Loaded when working under `web/`. Project-wide context is in `../CLAUDE.md`.

## Visual design: "Desk lamp" (approved 2026-11-23)

Tokens live at the top of `web/src/index.css`; mockup on the canvas
artifact (artboard "Tasks page – Desk lamp direction").

- Blue-slate room (`--ink #161a24`, `--slate #1f2533`), warm paper text
  (`--paper #ece6d9`). One lamp: amber `--lamp #f2b544` marks **only** the
  next step and keyboard focus. Green = done, red = overdue or lost.
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
