# 008 — Dates default to today

Status: implemented
Date: 2026-10-18

Closes #27. A new opportunity or step starts with an empty date, though it is
almost always today's.

## 1. Goal

- A blank opportunity card and a blank step card open with today's date filled in
- Editing an existing row, or posting a date, is unaffected

## 2. Non-goals

- Notes (dated by the model's `created_at`)
- A model-level default; the model knows nothing about the form

## 3. Design

- `OpportunityForm` and `StepForm` seed `initial["date"]` with
  `timezone.localdate()` when the instance is new. `setdefault`, so a caller's
  own initial wins; a bound form shows what was posted

## 4. Tests

`tests/jobs/test_date_default.py`: both forms seeded, rendered value, edit keeps
the stored date, bound form keeps the posted one.
