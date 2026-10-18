# 008 — Save a new note

Status: implemented
Date: 2026-10-18

Closes #26. Clicking "Add note" on an opportunity without notes opens a
textarea, but its Save and Cancel are not reachable.

## 1. Cause

The notes list is clamped to two notes or four lines (§7). With no notes the
blank note is the only entry, and its textarea alone fills the clamp, so the
`overflow: hidden` list cuts off the footer holding Save and Cancel. The form
and the `POST /opportunities/<pk>/notes/` route were fine.

## 2. Design

- `syncNotes` in `static/js/board.js` skips the clamp while the block holds a
  blank note (`.notes__item--new`) and hides the toggle, so the whole form shows
- Once the note is saved or cancelled the row is re-rendered and enhanced
  afresh, so the clamp applies again
- No template, view or CSS change

## 3. Non-goals

- Saving on blur: a new note keeps an explicit Save, like a new step

## 4. Tests

`tests/jobs/test_new_note_visible.py`: the blank note carries Save and Cancel,
and the script exempts it from the clamp. Checked by hand in a browser:
Save and Cancel visible on an empty and on a noted opportunity.
