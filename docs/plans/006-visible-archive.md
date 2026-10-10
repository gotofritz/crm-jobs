# 006 — A visible archive

Status: in progress
Date: 2026-10-09

Archived rows are reachable only through the admin (plan 001 §6.5). This plan
puts the archive one click from the board and replaces the all-or-nothing
"Archive all N" button with a selection and a bulk action.

## 1. Goal

- The header tally "X live, Y archived" links "Y archived" to `/archive/`
- `/archive/` is the board again, showing archived rows only, newest-archived
  first (`in_archive_order()`); its heading reads "Archive, Y archived, X live"
  and "X live" links back to `/`
- Both pages replace "Archive all N" with one bulk bar:
  - a "Select all / none" toggle button
  - an action pulldown styled like the buttons: `Archive` on the board,
    `Unarchive` on the archive page
  - a small go button next to it
- Every row has a checkbox at the top of its summary card, before the title
- The pulldown and go button are enabled only while at least one box is ticked;
  the toggle ticks every box, or clears them if all are ticked
- Go applies the action to the ticked rows and the page re-renders
- "New opportunity" sits at the far right of the header with a solid fill and
  light text on it, so it stands out; it is not shown on the archive page

## 2. Non-goals

- More actions in the pulldown (delete, change state). One entry for now
- Search or filtering in the archive
- Pagination of the archive

## 3. Design

### Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/archive/` | GET | the board in archive mode |
| `/opportunities/bulk` | POST | `ids` (repeated) and `action` (`archive` / `unarchive`) |

`archive-live` (view, route, button, confirm, tests) is removed: the selection
replaces it, and "select all, archive" is the same thing in two clicks.

The bulk route lives next to `archive-live`'s old place in `urls.py` and is
not an integer, so it cannot collide with the `<int:pk>` routes.

### Views

- `_board_context(mode=...)`: `mode` is `"live"` or `"archive"`. It picks the
  queryset and the template's wording; the counts stay both numbers
- `archive_board` renders `board.html` with `mode="archive"`
- `opportunity_bulk` validates `action` against a whitelist (anything else is
  a 400), applies `.filter(pk__in=ids)` restricted to the right side
  (`live()` for archive, `archived()` for unarchive, so a stale page cannot
  re-stamp an old burst), then answers with a whole-board swap in the mode the
  form names; without htmx it redirects to that page
- Mode travels in a hidden `view` field of the bulk form (`board` / `archive`)
- `_counts.html` renders per mode. After a single-row mutation the mode comes
  from `request.htmx.current_url_abs_path`, since an out-of-band fragment has
  no other way to know which page it is on
- On the archive page the row's Archive control becomes Unarchive and answers
  with `_row_gone`; Cancel returns to `/archive/`

### Templates

- `board.html` header: title, counts, bulk bar, New opportunity. Heading and
  counts per mode
- `_bulk_bar.html` (new partial): the form `id="bulk-form"` with the toggle,
  select, go button and hidden `view`
- `_summary_card.html`: `<input type="checkbox" name="ids" value="{{ pk }}"
  form="bulk-form" data-select>` as the first element. The `form` attribute
  ties it to the header form because forms cannot nest
- `_board.html`: empty message per mode ("Nothing live." / "Nothing archived.")

### Script

`board.js` gains an enhancement and nothing more: it hides nothing and breaks
nothing without it.

- Without it: the toggle is `hidden`, the pulldown and go button are enabled,
  and the POST works as a plain form
- With it: shows the toggle, disables the pulldown and go button until a
  `[data-select]` is ticked, and toggles all/none. Rows swapped in by htmx
  are covered by listening on `document`, not on each box

### Styling

- Everything visual is CSS (`assets/board.css`): `.button--primary` gives the
  solid fill, with text colour chosen for contrast; the header pushes it to
  the far right; the select is styled as `.button`
- Models, views and templates carry only `data-*` identity
- `poe css` rebuilds `static/css/app.css` with `--minify`

## 4. Tests (written first)

- `GET /archive/` lists archived rows only, newest-archived first; heading,
  both links and the empty message
- The board's "Y archived" is a link to `/archive/`; the archive's "X live"
  links to `/`
- `POST /opportunities/bulk`: archives the ticked rows only; unarchives the
  ticked rows only; ignores ids on the wrong side and keeps their timestamp;
  rejects an unknown action; without htmx redirects to the right page; nothing
  deleted
- Markup: a checkbox per row with `form="bulk-form"`, before the title;
  pulldown option is `archive` on the board and `unarchive` on the archive;
  `archive-live` and "Archive all" are gone; New opportunity is absent from
  the archive page
- Layout/script: `board.js` mentions the select hooks; CSS has the primary
  button rule; `poe css` output is committed
- Existing tests that referred to `archive-live` or "Archive all" are
  rewritten, not deleted

## 5. Phases

1. Plan (this file)
2. Archive page and header links (red → green)
3. Bulk route, removing `archive-live`
4. Checkboxes and bulk bar markup
5. Script and CSS, including the New opportunity restyle
6. `docs/initial-context.md`, then `uv run poe qa`

## 6. Open questions

- None blocking. The archive-mode single-row Unarchive swaps the row out
  rather than re-rendering the board; revisit if the ordering feels wrong
