# 005 — Import and export as TSV

Status: outline
Date: 2026-09-29
Replaces: the one-off sheet import of `docs/archive/003-import-the-sheet.md`
and `docs/archive/004-import-opportunities-csv.md`, both removed once the
legacy data was in

An outline, not yet a plan: the goals, the shape, and the questions to settle
before the first test is written. Nothing here carries over the old sheet's
packed-cell format, which existed only because the app used to be a sheet.

## 1. Goal

- **Export** the board to TSV: a backup a human can read, a file to open in
  LibreOffice, something to grep
- **Import** TSV: add opportunities written somewhere else, and restore an
  export into an empty database
- **Round trip**: exporting, importing into an empty database and exporting
  again gives the same files

## 2. Non-goals

- A replacement for the SQLite backup in plan 002. That one is the backup; an
  export is a portable copy of the data, not of the database
- Syncing, merging two boards, or resolving conflicting edits
- Importing any other app's format
- Upload or download in the browser in the first cut (§8, Q6)
- Round-tripping `created_at` and `updated_at` exactly (§8, Q5)

## 3. Why TSV

- Free text is full of commas; tabs are rare in it
- LibreOffice, Google Sheets and Excel all open a `.tsv` with no import dialog
- `cut -f`, `awk -F'\t'` and `column -t` read it directly
- The `csv` module writes and reads it with `dialect="excel-tab"`, so no
  dependency

## 4. Shape of the files

**Recommendation: one TSV per kind of row, in one directory**, each with a
header row naming its columns:

| File | One row per | Key columns |
|------|-------------|-------------|
| `opportunities.tsv` | opportunity | `company`, `title`, `date` |
| `steps.tsv` | step | the opportunity's key, then `date`, `time`, `title` |
| `notes.tsv` | note | the opportunity's key, then `created_at` |
| `companies.tsv` | company | `name` |
| `contacts.tsv` | contact at a company | `company`, `name` |

- Rows point at each other by **natural key** (what identifies a row on the
  board), never by database id. An id means nothing in another database, and
  natural keys can be read and typed by hand
- Picklists (`source`, `sector`, `state`) are written by name, and `state` by
  slug. Sources and sectors are created on import as the board creates them;
  an unknown state slug is a problem, not a new state
- Several contacts on a step go in one cell, comma-separated, as the board
  writes them
- Alternative: one wide file, one row per opportunity, with steps and notes
  squeezed into cells. Easier to skim, but it brings back the packed-cell
  parsing this plan exists to be rid of

## 5. Encoding and escaping

- UTF-8 on export, with no BOM. On import, a BOM is dropped and a file that is
  not UTF-8 is read as cp1252 and said so, which the sheet import showed a
  LibreOffice re-save needs
- Text with a tab, newline or quote is quoted the `excel-tab` way, so a
  job description keeps its paragraphs and a note keeps its `- ` bullets
  (`jobs.markup`). Spreadsheets read that; a strict IANA-TSV reader would not
  (§8, Q2)
- Dates are ISO `YYYY-MM-DD`, times `HH:MM`, empty for none

## 6. Behaviour

- **Commands**: `manage.py export_tsv <dir>` and
  `manage.py import_tsv <dir> [--demo] [--dry-run]`. Export reads the live
  database unless `--demo` is given
- **All or nothing**: import validates everything first, reports every
  problem with file, line and column, and writes nothing if there is one
- **Validation through the board's forms** (`OpportunityForm`, `StepForm`), so
  an import accepts exactly what a card would. `using=` and
  `add_first_step`'s own-database write are already in place for `--demo`
- **Existing rows are skipped, never updated** (as plan 004 did), so a stale
  file cannot undo an edit made on the board since. The report lists what was
  created and what was skipped
- **`--dry-run`** does the real import inside a transaction and rolls it back,
  so the preview cannot differ from the run
- **Archived opportunities** are exported with `archived_at`, and imported as
  archived

## 7. Module split

Following the boundaries in `docs/initial-context.md`:

| Module | Knows about | Does not know about |
|--------|-------------|---------------------|
| `src/jobs/tsv.py` | columns, reading and writing rows, line numbers | the ORM |
| `src/jobs/transfer.py` | models, forms, natural keys, the transaction | files, TSV |
| `management/commands/{export,import}_tsv.py` | arguments, refusals, the report | either of the above's rules |

## 8. Open questions

1. **One directory or one file?** A directory is the recommendation. A zip of
   it is one file to move around; a single wide TSV is simpler but lossy (§4)
2. **Quoting or escaping?** `excel-tab` quoting (recommended, spreadsheets
   first) or backslash escapes `\t` `\n` `\\` (tools first, but a spreadsheet
   shows the backslashes)
3. **Skip or update existing rows?** Skip is recommended; an `--update` flag
   could follow if restoring over a live board turns out to be needed
4. **Contacts' other companies.** `Employment` holds a contact's history across
   companies. Export every stint, or only the one each opportunity uses?
5. **Timestamps.** `created_at` orders notes, so notes need theirs. Do
   opportunities and steps need `created_at` and `updated_at` at all?
6. **The browser.** A download link on the board for export, and later an
   upload form for import, or commands only?

## 9. Phases

1. Settle §8
2. `tsv.py`: write and read one file, with tests for quoting, BOM, cp1252 and
   line numbers
3. Export, with a golden-file test against the demo board
4. Import, create-only, through the forms, with `--dry-run` and `--demo`
5. The round-trip test: demo board → export → import into an empty database →
   export, and compare
6. Update `docs/initial-context.md` and the README, and archive this plan
