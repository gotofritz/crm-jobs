# 003 — Import the historical sheet

Status: proposed
Date: 2026-09-20
Follows: `docs/archive/2026-09-20-2221-05dd166-001-port-gas-to-django.md`

## 1. Goal

A script that reads a CSV export of the old Google Sheet and writes its
rows into the CRM as ordinary opportunities with their steps.

```bash
uv run manage.py import_sheet path/to/export.csv            # the live database
uv run manage.py import_sheet path/to/export.csv --demo     # demo.sqlite3
uv run manage.py import_sheet path/to/export.csv --dry-run  # parse and report, write nothing
```

Plan 001 deferred this deliberately (D4: start fresh). What it did not
defer was the knowledge — §4.9's packing rules and §4.10's field mapping
were written while the sample export was at hand, and they moved here
intact. This plan is the only copy of them now.

## 2. Non-goals

- Two-way sync, or any write back to the sheet
- Reading the Sheets API. CSV is the input, and §7 says what that costs
- Guessing at malformed cells. They are fixed in the sheet and
  re-exported (§5)
- Importing the sheet's colours, fonts or column widths. They were a
  storage format, not a design (§6.3 of plan 001)

## 3. Decisions (locked)

| # | Decision | Choice |
|---|----------|--------|
| I1 | Input | A CSV export. One file, one run |
| I2 | Where rows land | **Live**, not archived. `archived_at` stays `NULL` |
| I3 | Step state | **Inferred from the step's title text**, falling back to `unremarkable` |
| I4 | Database | `--demo` writes to `demo.sqlite3`, otherwise the live database |
| I5 | Bad data | Parse everything, report every problem, write nothing and exit non-zero |
| I6 | Re-running | Safe. Every write is keyed on what identifies the row |

### Notes on I2

Plan 001 §4.10 mapped the sheet's pools onto `archived_at`, on the
assumption the sheet was history. It is not — it is the current job
hunt, so the rows belong on the board where the ordering rules in §4.5
apply to them.

That raises the stakes on I3. For an archived row the state would be
decoration, because archived rows sort by `archived_at` and nothing
else. For a live row the state is what decides where the row sits and
which card in it reads first. A wrong guess is visible.

### Notes on I3

A CSV export cannot carry state at all: a step's state was its cell's
background colour, and CSV has no formatting (§4.8 of plan 001). Three
options were on the table — read the colours through the Sheets API,
give every step one state, or infer from the title text. Inference wins
for this dataset because the outcome words really are in the titles (the
sample's newest step is titled `REJECTED`), and because the alternative
that keeps full fidelity costs an authenticated Google script for a
one-off run.

It is a guess, so the import treats it as one:

- The keyword table is small, explicit and ordered, and it lives in one
  place (§6). It is not a fuzzy matcher and it does no stemming.
- Anything unmatched lands in `unremarkable`, which means "nothing
  notable happened" — the honest answer when the title says nothing.
- Every inference is printed, so `--dry-run` shows what the run would
  decide before it decides it. Fixing a wrong guess is then a board
  edit, which the app already does well.

### Notes on I4

The selector is a database alias, not a mutated path: `settings.DATABASES`
grows a `demo` entry beside `default`, and the command resolves the flag
to an alias through one pure function.

`default` already follows `DJANGO_DB_PATH`, which is how `poe demo`
points the whole app at `demo.sqlite3`. Under `poe demo` both aliases
therefore name the same file, which is correct: the demo database is the
demo database however you arrive at it.

## 4. What the sheet looks like

```
        col 1          col 2          col 3        col 4      col 5
row 1                                 STATE DEFS   STATE DEFS STATE DEFS
row 2   metadataHead   metadataBody   step (new)   step       step (old)
row 3   metadataHead   metadataBody   step (new)   step
```

Row 1, columns 3+, define the sheet's states as `"GROUP / NAME"`; the
cell's background colour *was* the state. The export drops the colour
and leaves the text, so the row is recognisable and skipped. A one-row
export like the sample in `clasp/` has no such row, so its absence is
not an error.

Rows 2+ are opportunities, one per row. Columns 3+ are that row's steps,
newest in column 3 and older pushed right. The column index carries no
data beyond that ordering, and ordering re-derives from the dates, so
nothing needs to record it.

### 4.1 Cell packing, precisely

Two formats exist and the importer accepts both: the one the GAS code
writes, and the one the sample export actually contains. This is §4.9 of
plan 001, unchanged.

**Column 1 — opportunity head**

```
code:      company " / " position "\n\n" comments
observed:  company "\n\n" position "\n\n" comments
```

Rule: split on `\n\n`, at most three parts. If the first part contains
`" / "`, split it into company and position and the rest is comments.
Otherwise part 0 is company, part 1 is position, part 2 is comments.
`position` may be several lines — the sample carries a job title plus a
location-and-salary line.

**Column 2 — opportunity body**

```
code:      date "\n\n" source "\n"   contact
observed:  date "\n"   source "\n\n" contact
```

Rule: drop blank lines, then take them in order — date, source, and
whatever remains joined as contact. The separators differ between the
two formats but the line order does not, so ignoring blank lines makes
the difference disappear.

**Columns 3+ — steps**

```
code:      date " __ " time "\n\n" title "\n" contact "\n\n" comments
observed:  date " __ " time "\n"   title "\n" contact "\n\n" comments
```

Rule: first line splits on `" __ "` into date and optional time. The
remainder splits on its first `\n\n` into a head block and comments. In
the head block the first line is the title and the rest is contact.

Canonical form to normalise to, which doubles as the cleanup checklist:

```
col 1    company
         <blank>
         position, one or more lines
         <blank>
         comments, free text

col 2    date
         source
         <blank>
         contact

col 3+   date " __ " time
         title
         contact
         <blank>
         comments, free text
```

A trailing block is simply absent when empty — a step with no comments
ends after the contact line, with no trailing blank line. That absence
is what makes the shape unambiguous.

### 4.2 Malformed cells are cleaned at source

The sample contains one:

```
2025-07-11 __ 10:05
Scheduling interview
                        <- this blank line should not be here
Maya Richardson
```

The blank line makes the cell parse as an empty contact and a comment of
`"Maya Richardson"`, which is wrong — it is the contact, and the step has
no comments. Bad data, not a third format.

The dataset is small enough to fix by hand, so the importer does not try
to infer intent. It parses to the rules above, reports anything that does
not fit, and stops. Fix the sheet, re-export, re-run. A heuristic —
matching against contacts already seen on the same opportunity — would
recover this particular case, and is deliberately not used: it would also
silently mangle a step whose comment happens to name a person.

What the importer reports rather than resolves:

- a step whose contact is empty while its comments are a single short
  line
- a cell whose first line is not a date
- any cell yielding more blocks than the shape allows
- a row with no company, no position, or no date

## 5. Mapping to the model

This is §4.10 of plan 001, corrected for what actually shipped. Two
fields moved after that table was written: the opportunity's prose split
into `job_description` plus `Note` rows, and states gained readable
names over stable slugs.

| Sheet | Model |
|-------|-------|
| row | one `Opportunity`, `archived_at` left `NULL` (I2) |
| col 1 → company | `Company`, resolved by name, case-insensitively, created when new |
| col 1 → position | `Opportunity.title`, free text |
| col 1 → comments | `Opportunity.job_description` — it is the pasted job ad, 1870 characters in the sample |
| col 2 → date | `Opportunity.date` |
| col 2 → source | `Source`, resolved by name |
| col 2 → contact | `Opportunity.contact`, one `Contact` per name per company (§5.1) |
| col N≥3 | one `Step`, `opportunity` FK |
| step date | `Step.date` |
| step time | `Step.time`, `NULL` when absent or `":"` |
| step title | `Step.title` |
| step contact | `Step.contacts`, split on `", "` |
| step comments | `Step.comments` |
| cell background colour | `Step.state`, inferred from the title (I3) |
| column index | nothing; ordering re-derives from `date` |
| sheet (a pool) | nothing. `archived_at` stays `NULL` |

Nothing writes a `Note`. The sheet has one prose field per opportunity
and it holds the advert, so inventing notes from it would mean deciding
where an ad stops and a remark starts, which the sheet never recorded.
Notes start empty and get written in the app.

Picklist resolution — company, source, sector — follows the rule the
forms already use: match `name__iexact`, create when there is no match,
and let the first spelling entered win, so a later `FINTECH` finds the
stored `Fintech` rather than forking a second row.

### 5.1 Contact identity is the hard part

The sheet has names, not people. `"Maya Richardson"` under two companies
is either one recruiter who moved or two different people, and nothing in
the export says which. `Contact.name` is deliberately not unique, so a
naive `get_or_create` on name would merge strangers.

The importer creates one `Contact` per distinct name **per company**, and
lists the cross-company collisions at the end for a human to merge in the
admin. That is the same "is this the same person?" question the contact
autosuggest (#10) will ask, arriving earlier, and it is a review step
rather than a guess.

Per-company identity needs somewhere to live, and the schema already has
it: `Employment`, which is why plan 001 §6.7 built it. So the import also
writes one `Employment` per (contact, company) pair, both bounds `NULL` —
start unknown, still there. This is an addition to §4.10's table, and it
costs one row per pair.

## 6. Inferring a step's state

One ordered table, matched case-insensitively against the step title,
first hit wins. Longer, more specific phrases sit above shorter ones so
`offer accepted` cannot be swallowed by `offer`.

| Looks for | Lands in |
|-----------|----------|
| the exact name of a seeded state (`Ghosted`, `Bad Feeling`, …) | that state |
| `offer accepted`, `accepted` | `accepted` |
| `offer` | `success` |
| `rejected`, `declined`, `unsuccessful`, `no thanks` | `fail` |
| `withdrew`, `withdrawn` | `fail` |
| `ghosted`, `no reply`, `no response` | `ghosted` |
| `blacklist` | `blacklist` |
| anything else | `unremarkable` |

Deliberately absent: anything for `due`, `tentative`, `overdue` or
`error`. Those mean something is scheduled or something is wrong *now*,
which is a fact about the present, and no title text from a past step can
establish it. A row that needs one gets it by being edited on the board.

The table is data in one module-level constant, so adding a phrase is a
one-line change with a test beside it.

## 7. The command

`src/jobs/management/commands/import_sheet.py`, thin: argument parsing,
one transaction, and the report. The work sits in `src/jobs/sheet.py`,
which is pure — it turns text into dataclasses and knows nothing about
the ORM, so the whole parser is testable without the `db` fixture.

```
import_sheet <csv> [--demo] [--dry-run]

  csv          the exported file
  --demo       write to demo.sqlite3 instead of the live database
  --dry-run    parse, infer, report, write nothing
```

Order of operations:

1. Read the file. Skip row 1 if it is a state-definition row.
2. Parse every row and every cell, collecting problems as it goes rather
   than stopping at the first.
3. If there are problems, print them with row and column numbers and
   exit non-zero. Nothing is written — not even the rows that parsed
   (I5).
4. Otherwise, in one transaction, write companies, contacts,
   employments, sources, opportunities and steps.
5. Print what was written, what state each step was inferred into, and
   the cross-company name collisions to review.

`--dry-run` stops after step 3 and prints step 5's inference report from
what it parsed.

Re-running is safe because every write is keyed on what identifies the
row: an opportunity by `(company, title, date)`, a step by
`(opportunity, date, time, title)`, the picklists by name. A re-run after
a fixed export updates rather than duplicates.

The command refuses a database with no seeded states rather than failing
on a foreign key halfway through — that is what `--demo` against a
demo.sqlite3 nobody has built yet looks like, and the fix is `poe demo`.

## 8. Phases

TDD, per AGENTS.md: failing test, confirm the failure is the expected
one, minimal implementation, refactor green. `poe qa` before the PR.

### Phase 1 — The parser

`src/jobs/sheet.py`, pure, no ORM import.

- Dataclasses for a parsed row and a parsed step.
- `parse_head`, `parse_body`, `parse_step`, each against both formats in
  §4.1.
- A problem type carrying row, column and reason, collected not raised.
- `is_state_header` for row 1.
- Tests: both formats for all three cell shapes; a step with no comments;
  a step with two contacts; `":"` as an empty time; the malformed cell in
  §4.2 reported rather than guessed at; a cell whose first line is not a
  date; the sample export in `clasp/` parsed end to end, with its dates
  coming out strictly descending.

Done when: the sample parses to the fields §4.1 says it holds, and the
one malformed cell is reported.

### Phase 2 — State inference

Still pure, still in `sheet.py`.

- The table from §6, and a function from a title to a slug.
- Tests: `REJECTED` from the sample lands in `fail`; `offer accepted`
  beats `offer`; a seeded state's own name matches; an interview title
  falls through to `unremarkable`; matching ignores case; every slug the
  table names is one the seed migration creates, asserted against the
  database so a renamed state cannot leave the table pointing at nothing.

Done when: the sample's five steps each land somewhere defensible.

### Phase 3 — The demo database alias

- `DATABASES["demo"]` in settings, sharing the `default` entry's SQLite
  options, pathed by `DJANGO_DEMO_DB_PATH` with `demo.sqlite3` as the
  default.
- One pure `database_for(*, demo: bool) -> str`.
- Tests: the alias exists and carries the same `OPTIONS` as `default`;
  the two point at different files under normal settings; the flag maps
  to the right alias.

Done when: nothing can write to the live database while `--demo` is set.

### Phase 4 — The writer and the command

- Writing, in one transaction, keyed for re-runs.
- One `Contact` per name per company, plus the `Employment` row, plus the
  collision list.
- The command, its flags, its report, and its refusal on an unseeded
  database.
- Tests: the sample export imported end to end, checked opportunity by
  step; a second run changes no counts; `--dry-run` writes nothing; a
  file with one bad cell writes nothing at all, not even its good rows;
  the same name under two companies makes two contacts and one reported
  collision; the same name under one company makes one contact; an
  imported row is live, not archived; the board renders it.

Done when: the sample export lands on the board and a second run is a
no-op.

## 9. Risks

| Risk | Mitigation |
|------|-----------|
| Inferred states are wrong | Every inference is printed, `--dry-run` shows them before writing, and a wrong one is a board edit |
| The real export has a format the sample did not show | I5: it is reported with a row and column, and nothing is written |
| A run into the live database was meant for the demo one | `--demo` is explicit, the report names the file it wrote to, and `--dry-run` costs nothing |
| Contacts merged or split wrongly | Per-company identity, and the collisions are listed for review rather than resolved |
| An import doubles the board | Every write is keyed; a re-run is asserted to change no counts |

## 10. Done when

- `uv run manage.py import_sheet clasp/'Crm-clasp-2 - Sheet2.csv'` writes
  one opportunity with five steps, and the board renders it.
- Running it twice changes nothing.
- `--demo` writes to `demo.sqlite3` and the live database is untouched.
- A file with a malformed cell writes nothing and says which cell.
- `poe qa` is green.
