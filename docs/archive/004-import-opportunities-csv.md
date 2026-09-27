# 004 — Import opportunities from a CSV file

Status: built, 2026-09-26.
Date: 2026-09-26
Follows: `docs/archive/003-import-the-sheet.md`, built on the same branch

## 1. Goal

A management command that reads a plain CSV file — one opportunity per
row, a header row naming the columns — and adds those opportunities to
the board, exactly as if each had been typed into the "new opportunity"
form.

```bash
uv run manage.py import_opportunities path/to/new.csv            # the live database
uv run manage.py import_opportunities path/to/new.csv --demo     # demo.sqlite3
uv run manage.py import_opportunities path/to/new.csv --dry-run  # validate and report, write nothing
uv run manage.py import_opportunities - < new.csv                # read stdin
uv run manage.py import_opportunities --template > new.csv       # print the header row
```

The use case is a batch of applications sent in one sitting, or a list
copied out of a job board or a spreadsheet, where typing each one into a
card is the slow path.

### How this differs from plan 003

Plan 003's `import_sheet` reads the **old Google Sheet's export**: a
fixed, packed layout (steps as columns, fields packed into cells with
`\n\n`), run once to bring history across. This plan is the everyday
path: a flat, self-describing file anyone can produce by hand or from a
spreadsheet, one row per opportunity, no steps. The two commands share
conventions (§3, I4–I6) and code — the demo alias, `database_for`,
`by_name(…, using=)`, the unseeded-database refusal and the
rollback-based dry run (§6) — but not a parser: the formats have
nothing in common.

## 2. Non-goals

- Importing steps, states or notes history. A row makes an opportunity
  and its first step, as the board does (§5); anything after that is a
  board edit
- Updating opportunities that already exist. A re-run skips them (I5)
- Guessing at bad data. A bad row is reported, not coerced (I4)
- Other formats (XLSX, JSON, TSV). CSV is what every spreadsheet and job
  board can export
- A web upload screen. The CLI is the whole interface; an upload view
  can wrap the same importer later if it is ever wanted
- New dependencies. The stdlib `csv` module and the existing forms do
  the work

## 3. Decisions (to lock on review)

| # | Decision | Proposed choice |
|---|----------|-----------------|
| I1 | Input shape | UTF-8 CSV, comma-delimited, **header row required**; column order free |
| I2 | Validation | Each row goes through **`OpportunityForm`**, the form the board uses. No second set of rules |
| I3 | First step | `Opportunity.add_first_step()`, the domain rule, for every created row |
| I4 | Bad data | Validate every row, report every problem, write nothing, exit non-zero |
| I5 | Re-running | Safe. A row matching an existing `(company, title, date)` is **skipped and reported**, never updated |
| I6 | Unknown columns | A problem, not ignored — a typo'd header must not drop a column silently |
| I7 | Where rows land | Live. `archived_at` stays `NULL` |
| I8 | Database | `--demo` writes to `demo.sqlite3` through 003's alias, otherwise the live database |

### Notes on I1

- A UTF-8 BOM is tolerated (`encoding="utf-8-sig"`): Excel writes one
  when saving "CSV UTF-8", and it would otherwise corrupt the first
  header name.
- Header names are matched after `strip()` and `lower()`, so `Company`
  and ` company ` both work. Values are not lowered — only trimmed, by
  the form, as they are on the board.
- Blank lines are skipped; a row that is blank in every column is too,
  since spreadsheets pad exports with them.
- `-` as the path reads stdin, so the command composes with `curl`,
  `xsv` and friends.

### Notes on I2

`OpportunityForm` already takes every field a row can carry —
`title`, `date`, `job_description` from the model, plus `company`,
`source`, `contact` and the four `company_*` details it resolves in
`save`. Feeding each row to it as form `data` means:

- **Validation is the board's.** Required fields, max lengths, URL
  checks and date parsing are whatever the card enforces, and stay so
  when the card changes. `forms.py` stays the one home for coercion
  (AGENTS.md, "Boundaries").
- **Dates** parse through `DATE_INPUT_FORMATS` for `en-gb`, so both
  `2026-09-26` and `26/09/2026` work — and `09/26/2026` is rejected
  rather than silently read as a US date.
- **Picklists** resolve through `by_name`: case-insensitive match,
  first spelling wins, created when new (§6.9 of plan 001).
- **Company details** follow `_resolve_company`'s create-path rule: a
  filled cell sets the detail, a blank one leaves what is stored alone.
  A CSV never clears a company's URL by omission.

Resolution happens in `save`, after the whole file has validated, so a
file that fails on row 40 has not already created 39 companies.

### Notes on I5

"Already exists" means an opportunity whose company name matches
case-insensitively and whose `title` and `date` are equal — the same key
plan 003 uses. Skipping, rather than updating, is deliberate: once a row
is on the board it is edited there, and a stale CSV re-run must not
revert those edits. This differs from `import_sheet`, which
`update_or_create`s on the key: a re-export of the sheet *is* the newer
truth, a stale CSV is not. The report lists each skipped row so a re-run is
visibly a no-op.

Two rows **within one file** with the same key are a problem (I4), not a
skip: the file is contradicting itself.

## 4. The file

```csv
company,title,date,source,contact,job_description,company_url,company_linkedin_url,company_head_office,company_sector
Northwind Analytics,Staff Engineer,2026-09-24,LinkedIn,Maya Richardson,"Pasted ad…",https://northwind.example,,Berlin,SaaS
Contoso,Backend Developer,25/09/2026,Referral,,,,,,
```

| Column | Required | Maps to |
|--------|----------|---------|
| `company` | yes | `Company`, resolved by name |
| `title` | yes | `Opportunity.title` |
| `date` | yes | `Opportunity.date` — when the application went out |
| `source` | no | `Source`, resolved by name |
| `contact` | no | `Opportunity.contact`, resolved by name; also on the first step |
| `job_description` | no | `Opportunity.job_description` |
| `company_url` | no | `Company.url` |
| `company_linkedin_url` | no | `Company.linkedin_url` |
| `company_head_office` | no | `Company.head_office` |
| `company_sector` | no | `Company.sector`, resolved by name |

The column list is one constant, `COLUMNS`, and `--template` prints it.
It is written out rather than derived, so the reader needs no import of
the form and the template has a sensible order; a test pins it, and
`REQUIRED`, to `OpportunityForm`'s fields. So the documented header, the
accepted header and the form cannot drift apart, and a new form field
is a deliberate decision about the CSV too.

`date` is required rather than defaulting to today: the dedupe key
includes it (I5), and a default that changes every day would make a
re-run tomorrow duplicate every row.

A **`note`** column is deliberately not in the first cut: `Note` is not
on `OpportunityForm`, and one note per row is easy to add in a later
phase once the base is in. See §9.

## 5. Contacts

The board resolves a contact with `by_name` — globally, not per company
— and this import does the same, so a contact typed into a CSV and one
typed into a card are the same person. That is a different choice from
plan 003 §5.1, which creates one contact per name *per company* because
it imports years of unreviewed history. Here the rows are new and
written by the user, who already knows whether "Maya Richardson" at two
companies is one recruiter; the board's rule is the right one, and
using it keeps the import a batch of card saves rather than a second
model of identity.

## 6. Modules

| Module | Knows about | Does not know about |
|--------|-------------|---------------------|
| `src/jobs/opportunity_csv.py` | the text, the header, line numbers | the ORM, forms |
| `src/jobs/forms.py` | validation and coercion (`OpportunityForm`, gains `using`) | files |
| `src/jobs/importer.py` | models, transactions, aliases — now for both importers | the file, CSV |
| `src/jobs/management/commands/import_opportunities.py` | arguments, refusals, the report | parsing, rules |

- **`opportunity_csv.py`** is pure: `COLUMNS`, `REQUIRED`, and
  `read(text: str) -> Parsed`, where `Parsed` carries a tuple of `Row`s
  (a line and a `dict[str, str]`) and a tuple of problems (missing required
  header, unknown header, duplicate header, a row with more cells than
  the header). Testable without the `db` fixture. Its problem type names
  a line and a column *header*, not 003's row and column *number*, so it
  is its own small dataclass rather than a stretched `sheet.Problem`.
- **`importer.py`** grows `import_opportunities(rows, *, using,
  dry_run=False) -> Imported` beside 003's `write`: one `OpportunityForm(data=row,
  using=using)` per row, form errors mapped to problems, in-file
  duplicates and existing rows found, and — only if there are no
  problems — every form saved and `add_first_step(using=using)` called,
  in one `transaction.atomic(using=using)`. `Imported` is a frozen
  dataclass (created, skipped, problems) the command prints; created
  and skipped rows are `Entry`s, printed as
  `line N: <title> at <company>, <date>`. If
  `importer.py` reads as two unrelated halves once this lands, split
  it — but not before there is something to split.
- The **command** is thin, as `seed_demo` and `import_sheet` are.

### What is reused from 003, and what has to change

| From 003 | Reused as |
|----------|-----------|
| `DATABASES["demo"]`, `database_for(*, demo=)` | as is, for `--demo` |
| `by_name(model, raw, *, using=)` | as is, via the form |
| `UnseededDatabaseError` and `NoSuchExportError` in `import_sheet.py` | moved to `jobs.management.refusals` so both commands raise the same refusals without one importing the other — not to `jobs.importer`, because a `CommandError` belongs to the command line, not the layer that writes rows |
| `preview` — do it, then roll back | the same pattern for `--dry-run`, so a dry run cannot take a code path the real one does not |

Two things 003 did not need and this does, because it writes through
the form and the domain method rather than the ORM directly:

- **`OpportunityForm` takes `using`** (keyword, default
  `DEFAULT_DB_ALIAS`) and passes it to every `by_name` call and to
  `_resolve_company`'s saves. `save(commit=True)` saves with
  `using=self.using`. The board never passes it, so views are
  unchanged.
- **`Opportunity.add_first_step()`** writes to the opportunity's own
  `_state.db` — the database it was read from or saved to, which is the
  right answer everywhere, so it takes no argument. The `State` lookup
  and the `Step` create both use it.

Without these, `--demo` would validate against the demo database and
quietly resolve companies in the live one — exactly the failure I8
exists to prevent, so a test pins it (Phase 1).

## 7. The command

```
import_opportunities <csv|-> [--dry-run] [--demo] [--template]

  csv          the file to read, or - for stdin
  --dry-run    validate and report, write nothing
  --demo       write to demo.sqlite3 instead of the live database
  --template   print the header row and exit
```

Order of operations:

1. `--template`: print the header and stop.
2. Read the file (refuse a missing path with a named error). Parse the
   header and rows.
3. Resolve the alias with `database_for`; refuse an unseeded database —
   every created row needs `unremarkable` for its first step.
4. Validate every row through the form; check in-file duplicates;
   look up existing rows.
5. Any problem → print all of them as `line N, <column>: <message>`,
   exit non-zero, write nothing.
6. Otherwise write in one transaction — rolled back under `--dry-run` —
   and print `created N, skipped M (already on the board)` with the
   database named and the skipped rows listed.

## 8. Phases

TDD, per AGENTS.md: failing test, confirm the failure is the expected
one, minimal implementation, refactor green. `uv run poe qa` before the
PR.

### Phase 1 — `using` through the form and the first step — done

`forms.py` and `models.py`, `db` fixture, run against both aliases.

- `OpportunityForm(…, using=)` and `add_first_step()` as in §6.
- Tests: a form saved with `using="demo"` creates its company, source,
  sector and contact in the demo database and nothing in `default`;
  `add_first_step` on a demo opportunity writes its step there; the
  board's existing form tests pass untouched (the default is the old
  behaviour).

Done when: nothing the form or the first step writes can land on a
database other than the one it was asked for.

Found on the way: the seed migration wrote through the default
manager, so `migrate --database demo` seeded the live database again
and left demo.sqlite3 with no states — nothing could be imported into
it, by this command or by `import_sheet --demo`. Nothing had run on a
VPS yet, so the migrations were squashed into `0001_initial` (schema)
and `0002_seed_picklists` (seed, written to the database being
migrated). Tested against the demo test database, and by hand against
a fresh pair of files.

### Phase 2 — The reader — done

`src/jobs/opportunity_csv.py`, pure.

- `COLUMNS` and `REQUIRED`, pinned to `OpportunityForm`; `read()` →
  `Parsed`.
- Tests: header in any order and any case; BOM stripped; blank and
  all-empty rows skipped; missing `company`/`title`/`date` header;
  unknown header reported by name; duplicate header; a row with too
  many cells; quoted cells with commas and newlines (a pasted ad);
  line numbers count physical lines, so a multi-line cell does not
  shift the ones after it.

Done when: every structural problem in a file is reported in one pass.

Two cases the list above missed, settled while building it: a short row
is padded with blanks, because exports trim trailing empty cells; and a
column with an empty header — what a trailing comma makes — is ignored
while it holds nothing, and a problem as soon as it holds something.

### Phase 3 — Validation and writing — done

`import_opportunities` in `src/jobs/importer.py`, `db` fixture.

- Per-row `OpportunityForm`, errors mapped to problems.
- In-file duplicate detection and existing-row lookup (I5).
- Save + `add_first_step()` in one transaction; dry run by rollback.
- Tests: a valid file creates opportunities, companies, sources and a
  first step each, carrying the contact; a bad date, a bad URL and a
  blank title each report their line and column; one bad row writes
  nothing at all, not even the good rows or their companies; a second
  run creates nothing and reports every row as skipped; an in-file
  duplicate is a problem; `FINTECH` finds stored `Fintech`; a blank
  `company_url` leaves a stored URL alone; `26/09/2026` parses and
  `09/26/2026` is refused; the dry run reports the same counts as the
  real run and leaves the database unchanged; `using="demo"` leaves
  `default` untouched; created rows are live and render on the board.

Done when: the example in §4 lands on the board and a re-run is a no-op.

### Phase 4 — The command — done

- Arguments, `-` for stdin, `--template`, `--dry-run`, `--demo`, the
  report, and the refusals (missing file, unseeded database — the
  latter moved from `import_sheet.py`, whose tests must stay green).
- Tests via `call_command`: `--template` prints `COLUMNS`;
  `--dry-run` writes nothing and prints what it would do; `--demo`
  writes to the demo alias only; a problem exits with `CommandError`
  and prints every problem; stdin works; a missing path is named in the
  error.
- A sample file in `tests/jobs/fixtures/opportunities.csv` used by the
  end-to-end test, doubling as a worked example.

Done when: the four commands in §1 behave as described against a real
`db.sqlite3` and `demo.sqlite3`, checked by hand as well as in tests.

Settled while building it: when the header has problems, the rows that
fit are still validated so one run reports both — unless a required
column is missing, when every row would only repeat what the header
already says.

### Phase 5 — Docs — done

- README: one short section with the command and the `--template` tip.
- `docs/initial-context.md`: note the new management command, the
  `opportunity_csv` / `importer` boundary, and that `OpportunityForm`
  now takes `using`.
- Archive this plan per AGENTS.md in the same PR.

## 9. Later, not now

- A `note` column writing one `Note` per row.
- A `state` column for the first step, once there is a reason to import
  rows that are already past "applied".
- An upload form on the board wrapping `importer.import_opportunities`.

## 10. Risks

| Risk | Mitigation |
|------|-----------|
| A US-format date is read as UK | `en-gb` input formats refuse `09/26/2026`; ambiguous ones like `03/04/2026` read as 3 April — documented in the README and printed in `--dry-run` |
| A typo'd header silently drops a column | Unknown headers are a problem (I6) |
| A re-run doubles the board | `(company, title, date)` key; re-run asserted to create nothing |
| A re-run reverts board edits | Existing rows are skipped, never updated (I5) |
| Half a file lands | Validate everything first, write in one transaction (I4) |
| Import and card drift apart | Same `OpportunityForm`; the column list is derived from it and pinned by a test |
| Picklists fork on case | `by_name`, same as the board |
| `--demo` resolves names in the live database | `using` threaded through the form and `add_first_step`, pinned by tests on both aliases (Phase 1) |
