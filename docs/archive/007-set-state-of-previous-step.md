# 007 — Set the state of the previous step

Status: implemented
Date: 2026-10-10

Closes #22. Moving an opportunity on usually means two things at once: a new
step happens, and the one before it is settled (a "Due" becomes "Done"). Today
that is two edits.

## 1. Goal

- The blank step card has a "Previous step" pulldown of states
- "Previous" is the leftmost card in the track, which is `top_step` (§4.5)
- The pulldown is seeded with that step's current state
- Saving with a different state changes the previous step's state; the same
  state, or none sent, writes nothing

## 2. Non-goals

- Editing any other field of the previous step
- Offering it on an edit, or on an opportunity's first step (nothing to the left)

## 3. Design

- `StepForm` adds a `previous_state` `ModelChoiceField` only for a new,
  un-narrowed form on an opportunity that already has a step. Validation stays
  in the form (AGENTS.md, "Boundaries")
- `save` finds the previous step before saving the new one, so the new step can
  never be mistaken for it, then updates `state` only if the choice differs
- `_step_fields.html` renders the field when present. No view change: the
  existing whole-row or whole-board swap already covers a state change

## 4. Tests

`tests/jobs/test_previous_step_state.py`: field present and seeded, absent on a
first step and on edit, changed state applied, same state and omitted field
leave the step alone.
