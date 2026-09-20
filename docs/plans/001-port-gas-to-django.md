# 001 — Port CRM from Google Apps Script to a self-hosted Django app

Status: proposed
Date: 2026-09-17
Supersedes: the Google Apps Script app in `clasp/`

## 1. Goal

Replace the spreadsheet-backed Google Apps Script CRM with a small
Django app that:

- runs locally with one command, no Google account involved
- stores data in SQLite
- is reachable from any browser over HTTPS at a domain I own
- keeps the horizontal "summary card + steps pushed rightwards" layout
- deploys from GitHub on push to `main`

## 2. Non-goals

- Multi-user, roles, or sharing
- Any sync back to Google Sheets
- Spreadsheet-like editing (cell selection, formulas, drag-fill)
- Native mobile app; responsive web is enough
- Migrating existing sheet data — see decision D4

## 3. Decisions (locked)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Language / framework | Python 3.14 + Django 6.x + HTMX |
| D2 | Store | SQLite, file outside the repo directory |
| D3 | Remote access | Public domain, Caddy reverse proxy, TLS via Let's Encrypt |
| D4 | Data | Start fresh. Old sheet stays as a read-only archive |
| D5 | Auth gate | Caddy `basic_auth`. No auth code in Django |
| D6 | Deploy | GitHub Actions, SSH to VPS, `git pull` + migrate + restart |

### Notes on D1

Python 3.14 rules out the Django 5.2 LTS line, which tops out at 3.13,
so this is Django 6.x. The cost is that 6.0 is not an LTS release:
security fixes run about a year rather than three, and staying current
means a major upgrade sooner. For a single-user app that gets touched
regularly, that is a fine trade — the alternative is pinning Python
back to 3.13 to sit on the LTS.

Confirm both version floors against the Django release notes when
scaffolding in phase 0 rather than trusting this table.

### Notes on D5

`basic_auth` is one shared credential over TLS with no logout and no
audit trail. Acceptable for a single-user job tracker, and it is the
only option that costs zero application code. The gate is one layer in
front of the app, so swapping it later for a Django login view or
oauth2-proxy touches no application code. Revisit if a second person
ever needs access.

### Notes on D2

The SQLite file is the only copy of the data once the sheet is retired.
Backups (§10) are not optional and must be working before the sheet is
abandoned.

## 4. What the GAS app does today

Read from `clasp/`. Recording it here because the source is compiled
TypeScript output and is hard to read.

### 4.1 Sheet layout

```
        col 1          col 2          col 3        col 4      col 5
row 1                                 STATE DEFS   STATE DEFS STATE DEFS
row 2   metadataHead   metadataBody   step (new)   step       step (old)
row 3   metadataHead   metadataBody   step (new)   step
```

- Row 1, columns 3+ define the available states. Cell text is
  `"GROUP / NAME"`; the cell's background and font colours *are* the
  state's colours.
- Rows 2+ are opportunities, one per row.
- Column 1 (`metadataHead`, yellow) holds company, position, comments.
- Column 2 (`metadataBody`, yellow) holds date, source, contact.
- Columns 3+ hold steps, newest in column 3, older pushed right.
- A step's state is encoded as its cell's background colour, matched
  back to a state by hex string.

### 4.2 Field packing

Each cell holds several fields concatenated into one rich-text string,
separated by literal separators, with per-field text styles:

| Cell | Fields (separator after each) |
|------|-------------------------------|
| metadataHead | `company` ` / `, `position` `\n\n`, `comments` |
| metadataBody | `date` `\n\n`, `source` `\n`, `contact` |
| step | `date` ` __ `, `time` `\n\n`, `title` `\n`, `contact` `\n\n`, `comments` |

`StateToSheetBridge` builds a regexp from those separators to parse the
string back into fields. `Field` handles defaults and emptiness.

**This whole layer disappears in the port.** Fields become columns.
`Field`, `StateToSheetBridge`, `App`, and the colour-matching in
`StatesManager` have no equivalent in the target. The parsing regexp is
the single largest source of fragility in the current app.

### 4.3 Defaults

| Thing | Default |
|-------|---------|
| company | `????` |
| position | `[TBC]` |
| opportunity date | today |
| source | `LinkedIn` |
| contact (opportunity and step) | `(Contact unknown)` |
| step title | `Applied via site` |
| step state | `UNREMARKABLE` |
| timezone | `Europe/Berlin` |

### 4.4 Behaviour worth keeping

- Creating an opportunity also creates its first step automatically,
  using the opportunity's date and contact and the default step title.
- New steps are prepended (`steps.unshift`), so a new one arrives at the
  left, next to the summary. That is insertion order, not display order:
  `sortSteps` then decides where it actually sits, and §4.5 is what says
  how. The layout to preserve is the direction — the leftmost card is the
  one to read first — not "newest leftmost", which §4.5 overrules
  whenever two steps are in different groups.
- Comments are editable on their own, through a separate dialog, for
  both opportunities and steps.

### 4.5 Ordering rules — port these exactly

Group ranking: `ATTENTION` 3, `DUE` 2, `COMPLETE` 1, anything else -1.

**Steps within an opportunity** (`Opportunity.sortSteps`):

1. By group rank, descending.
2. Tie: by `date` + `time` ascending — *except* when the state's group
   is `COMPLETE`, where it is descending.

Group rank is first and the date only breaks a tie, so a track is not in
date order and is not meant to be. A `TENTATIVE` step on the 17th sits
left of a `BAD_FEELING` one on the 20th because `DUE` outranks
`COMPLETE`: the leftmost card is the one that still wants something, not
the one that happened last. **Decision: keep it.** The alternative reads
as a diary, and what the row is for is knowing what to do next.

**Opportunities within the pool** (`Pool.sortOpportunities`), keyed on
each opportunity's *first* (newest) step:

1. Opportunities with no steps sort first.
2. By group rank, descending.
3. Tie: by the state's position in the header row, ascending.
4. Tie: by `date` + `time` ascending — again inverted for `COMPLETE`.

### 4.6 Bugs in the current app — do not port

- `handleCreateOpportunity` and `handleCreateStep` test `if (data.id)`.
  Index `0` is falsy, so editing the *first* opportunity, or the first
  step of an opportunity, silently creates a duplicate instead of
  updating. Using real primary keys removes the class of bug.
- `dieUnlessSelection` calls leftover debug functions `a()` and `b()`,
  which pop up message boxes.
- A step's state is stored only as a cell colour. Changing the
  spreadsheet theme rewrites the data.
- `Pool.updateUI` deletes and re-inserts every row on every change.

### 4.7 Pools are a spreadsheet workaround

`Pool` maps to one sheet. The workflow it supported: one sheet is the
live one, another is the current archive, older archives sit behind
them. On landing a job, everything live gets archived; before the next
search, the archive is itself archived and a fresh one started.

The only reason for the generations is that long sheets are unwieldy.
That is a property of spreadsheets, not of the work. A table with an
index does not get slower or harder to read because old rows are in it.

So `Pool` does not become a model. The whole concept collapses to one
nullable timestamp on `Opportunity` (§6.5), and the generations
disappear entirely — `archived_at` already orders archived
opportunities by when they were put away, which is what the
generations were approximating.

### 4.8 What the sample export shows

`clasp/Crm-clasp-2 - Sheet2.csv` is one exported opportunity row. Three
things came out of checking it against the code above.

**Steps really are newest-first.** Left to right: 2025-07-21, 07-18,
07-15, 07-11, 07-08. Confirms §4.4 and the layout in §7.

**The stored text does not match the parser.** Rebuilding the regexps
from §4.2 and running them over the row: all three cell types fail to
match. `metadataHead` expects a literal `" / "` between company and
position that is nowhere in the cell; `metadataBody` and the step cells
have single newlines where the code expects doubled ones. A failed
match means `loadTextDataFromSheet` returns early and every field keeps
its default, so such a row would read back as `????` / `[TBC]`.

Either the sheet drifted from the code, or these cells were typed and
pasted by hand rather than entered through the form — the job
description in the sample is clearly pasted from a job ad. The cause
does not much matter. What it shows is that the packed-string format is
not actually load-bearing, which is the §4.2 fragility argument turning
up in real data.

**A CSV export cannot carry state at all.** A step's state is its
cell's background colour (§4.1), and CSV has no formatting, so the
export drops it entirely. Nothing in the sample says whether any step
is `DUE`, `GHOSTED` or `ACCEPTED`. Recovering that would need the
Sheets API to read cell backgrounds.

This is the §6.3 argument made concrete: data encoded as presentation
survives only inside the tool that drew it. It also confirms D4 — a
"start fresh" decision made for convenience turns out to be the only
cheap option, since a CSV-based import would silently produce rows with
default fields and no states.

No decision changes. Two details for the port, though:

- The opportunity `comments` field holds the whole job ad — 1870
  characters in this one sample. The summary card has to cope with
  that (§7).
- The sheet's `position` carries more than a job title: `"Staff Software
  Engineer - Distributed AI\nBased in Edinburgh, remote. £125k"`.
  Location and salary are in there by convention. It maps to
  `Opportunity.title` and stays free text (§6.8); splitting out the
  extra fields is noted in §13.

### 4.9 Cell packing, precisely

Reference for the later import (§13). Not built now. Written while the
sample export is at hand, because this is the knowledge that rots.

Two formats exist and an importer has to accept both: the one the GAS
code writes, and the one the sample actually contains (§4.8).

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
remainder splits on its first `\n\n` into a head block and comments.
In the head block the first line is the title and the rest is contact.

**Malformed cells are cleaned at source, not guessed at.** The sample
contains one:

```
2025-07-11 __ 10:05
Scheduling interview
                        <- this blank line should not be here
Maya Richardson
```

The blank line makes the cell parse as an empty contact and a comment
of `"Maya Richardson"`, which is wrong — it is the contact, and the
step has no comments. This is bad data rather than a second format.

The dataset is small enough to fix by hand, so the importer does not
try to infer intent. It parses to the rules above, reports anything
that does not fit, and stops. Fix the sheet, re-export, re-run. A
heuristic — matching against contacts already seen on the same
opportunity — would recover this particular case, and is deliberately
not used: it would also silently mangle a step whose comment happens to
name a person.

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

What the importer should report rather than resolve: a step whose
contact is empty while its comments are a single short line, a cell
whose first line is not a date, and any cell yielding more blocks than
the shape allows.

### 4.10 Mapping to the new model

| Sheet | New model |
|-------|-----------|
| row | one `Opportunity` |
| col 1 → company | `Company`, by name (§6.9); url, LinkedIn, head office and sector left blank — the sheet has none of them |
| col 1 → position | `Opportunity.title`, free text (§6.8) |
| col 1 → comments | `Opportunity.comments` |
| col 2 → date | `Opportunity.date` |
| col 2 → source | `Source`, by `get_or_create` on name |
| col 2 → contact | `Contact`, by name — see below |
| col N≥3 | one `Step`, `opportunity` FK |
| step date | `Step.date` |
| step time | `Step.time`, `NULL` when absent or `":"` |
| step title | `Step.title` |
| step contact | `Step.contacts`, split on `", "` |
| step comments | `Step.comments` |
| cell background colour | `Step.state` — **not in a CSV export** |
| column index | nothing; ordering re-derives from `date` |
| sheet (a `Pool`) | `archived_at`, set on import |

Two of those need saying out loud.

**Column index carries no data.** It encodes only "newest leftmost",
and the sample's dates descend strictly left to right, so ordering is
fully recoverable from `date` alone. `Step` needs no position field.

**Contact identity is the import's hard part.** The sheet has names,
not people. `"Maya Richardson"` appearing under two companies is either
one recruiter who moved or two different people, and nothing in the
export says which. Since `Contact.name` is deliberately not unique
(§6.7), a naive `get_or_create` on name would merge strangers.

The import should create one `Contact` per distinct name *per company*,
and list the cross-company name collisions for a human to merge
afterwards. That is the same "is it the same person?" question the
autosuggest in §13 asks, arriving earlier, and it is a review step
rather than a guess.

**State does not survive a CSV export** (§4.8). Three ways to deal with
that, to be chosen when the import is actually built:

- Read cell backgrounds through the Sheets API instead of CSV. Full
  fidelity, costs a one-off authenticated script.
- Import from CSV and give every imported step one state, accepting the
  loss. These rows are archived and only reachable by search, so the
  loss may not matter.
- Infer from the title text — the sample's newest step is titled
  `REJECTED`, and outcome words do appear there. Fuzzy; at best a
  fallback for the newest step of each row.

The unpacking rules above were checked against the sample export. Every
field extracted correctly and dates came out strictly descending, with
the one malformed cell above needing a fix in the sheet first. One row
is not a corpus, so treat the rules as validated in shape rather than
proven exhaustively.

## 5. Target architecture

```
browser ── HTTPS ──▶ Caddy (TLS + basic_auth) ──▶ gunicorn ──▶ Django
   :443                    127.0.0.1:8000                       │
                                                                ▼
                                            /var/lib/crm-jobs/db.sqlite3
```

- One VPS, two systemd units (`caddy`, `crm-jobs`).
- Django serves its own static files through WhiteNoise, so Caddy needs
  no static-file configuration.
- HTMX vendored as a static file, not loaded from a CDN. No npm, no JS
  build step. One hand-written script beside it, `static/js/board.js`,
  for what CSS cannot do on its own — it is the file the browser runs,
  and everything in it is an enhancement.
- Tailwind via the standalone CLI binary, which needs no Node.

Repo layout:

```
crm-jobs/
  pyproject.toml          uv-managed
  Taskfile.yml            task qa, task dev, task test
  manage.py
  config/                 settings, urls, wsgi
  jobs/                   the one app: models, views, templates
  static/                 htmx.min.js, board.js, compiled tailwind css
  deploy/                 Caddyfile, crm-jobs.service, backup timer
  .github/workflows/      ci.yml, deploy.yml
  clasp/                  kept read-only as reference until phase 7
```

### Deviation from AGENTS.md worth recording

AGENTS.md names `pydantic` for models. Django's ORM models fill that
role here; adding pydantic on top would duplicate validation for no
gain. Pydantic stays available for anything outside the ORM, such as
parsing config. Record this in `docs/initial-context.md` in phase 1.

## 6. Data model

The sheet flattened everything into text because a cell holds text.
That is not a reason to keep it flat. Company, contact and source are
real entities that recur across opportunities, so they get tables.

```python
class Sector(models.Model):
    name = models.CharField(max_length=100, unique=True)  # see §6.10


class Company(models.Model):
    name = models.CharField(max_length=200, unique=True)
    url = models.URLField(blank=True, default="")
    linkedin_url = models.URLField(blank=True, default="")
    head_office = models.CharField(max_length=200, blank=True, default="")
    sector = models.ForeignKey(
        Sector, null=True, blank=True, related_name="companies", on_delete=models.SET_NULL
    )


class Contact(models.Model):
    name = models.CharField(max_length=200)  # deliberately not unique
    notes = models.TextField(blank=True, default="")


class Employment(models.Model):
    """Who was where, when. One row per stint."""

    contact = models.ForeignKey(Contact, related_name="employments", on_delete=models.CASCADE)
    company = models.ForeignKey(Company, related_name="employments", on_delete=models.CASCADE)
    started_on = models.DateField(null=True, blank=True)  # NULL = unknown
    ended_on = models.DateField(null=True, blank=True)  # NULL = still there


class Source(models.Model):
    name = models.CharField(max_length=100, unique=True)  # LinkedIn, Wellfound


class Group(models.TextChoices):
    ATTENTION = "ATTENTION"
    DUE = "DUE"
    COMPLETE = "COMPLETE"


GROUP_RANK = {Group.ATTENTION: 3, Group.DUE: 2, Group.COMPLETE: 1}


class State(models.Model):
    slug = models.SlugField(unique=True)  # "bad-feeling" — CSS hook
    name = models.CharField(max_length=50)  # "BAD_FEELING" — display
    group = models.CharField(max_length=20, choices=Group)
    sort_order = models.PositiveIntegerField()  # tie-break, §4.5 rule 3


class Opportunity(models.Model):
    company = models.ForeignKey(Company, related_name="opportunities", on_delete=models.PROTECT)
    title = models.CharField(max_length=200)  # free text, see §6.8
    date = models.DateField()
    source = models.ForeignKey(Source, null=True, blank=True, on_delete=models.SET_NULL)
    contact = models.ForeignKey(
        Contact, null=True, blank=True, related_name="opportunities", on_delete=models.SET_NULL
    )
    comments = models.TextField(blank=True, default="")
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Step(models.Model):
    opportunity = models.ForeignKey(Opportunity, related_name="steps", on_delete=models.CASCADE)
    state = models.ForeignKey(State, on_delete=models.PROTECT)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    title = models.CharField(max_length=200, default="Applied via site")
    contacts = models.ManyToManyField(Contact, blank=True, related_name="steps")
    comments = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
```

- `time` is nullable because the GAS app treats `":"` as empty.
- `group` is a `TextChoices` field, not a separate table. Promote it
  only if groups need their own attributes.
- **No colour anywhere in the model.** See §6.3.
- `archived_at` is the whole of what `Pool` used to be. See §6.5.
- `slug` exists so presentation has a stable key. Renaming the display
  `name` from `BAD_FEELING` to `Bad feeling` must not repaint the board.
- `sort_order` replaces the sheet's column position. It is domain, not
  layout: it is the third tie-break in §4.5.
- `GROUP_RANK` lives next to the enum, not in the database. It is a
  business rule, and a rule that has never changed.

Every `Company` field but the name is optional. A company is usually
created mid-flow while entering an opportunity, when all that is known
is its name; the rest gets filled in later or never. Requiring any of
it would turn adding an opportunity into a research task.

`head_office` stays free text for the reason `title` does (§6.8): the
values vary in shape — `"Edinburgh"`, `"Edinburgh, UK"`, `"Remote"` —
and nothing in the app filters on it yet. If it ever needs filtering it
becomes a `Location` foreign key, which is a migration, not a redesign.

Deletion rules are deliberate. `Company` is `PROTECT`, because deleting
a company should not silently take its opportunities with it. `source`
and `contact` are `SET_NULL`, because losing who referred you does not
invalidate the application. `Step.opportunity` stays `CASCADE`: a step
has no meaning without its opportunity.

### 6.1 Seed states

Taken from the live sheet header row, in column order. `sort_order` is
that order and drives the tie-break in §4.5.

| sort_order | group | name | slug |
|---|---|---|---|
| 1 | ATTENTION | Error | `error` |
| 2 | ATTENTION | Overdue | `overdue` |
| 3 | DUE | Due | `due` |
| 4 | DUE | Tentative | `tentative` |
| 5 | COMPLETE | Accepted | `accepted` |
| 6 | COMPLETE | Success | `success` |
| 7 | COMPLETE | Bad Feeling | `bad-feeling` |
| 8 | COMPLETE | Going Well | `going-well` |
| 9 | COMPLETE | *(empty)* | `unremarkable` |
| 10 | COMPLETE | Ghosted | `ghosted` |
| 11 | COMPLETE | Fail | `fail` |
| 12 | COMPLETE | Blacklist | `blacklist` |

The sheet wrote these as `BAD_FEELING` and `GOING_WELL`, because in a
header row they were column labels rather than anything anyone read.
`slug` is the key — what the code looks up, what the stylesheet hooks
on — so `name` is free to be the words printed on a card. Migration
`0003` makes that change; the slugs, and everything keyed on them, are
untouched.

`UNREMARKABLE` has no name at all. It is where a new opportunity lands
(§6.6) and it means nothing notable happened, so there is nothing worth
printing: its card carries the step and no label. Empty in the data
rather than hidden in the template, because what a state is called is
the state's business and the template only prints what it is handed
(§6.3).

No colours here. The sheet's hex values were a storage format, not a
design; the palette is chosen fresh in CSS (§6.3).

Only three groups occur, matching `GROUPS_RANKED` in the GAS source
exactly: `ATTENTION` 3, `DUE` 2, `COMPLETE` 1.

### 6.2 What the groups actually mean

`COMPLETE` is a misnomer inherited from the sheet. It holds
`GOING_WELL`, `BAD_FEELING` and `UNREMARKABLE`, which are ongoing, not
finished. The real meaning of the three groups is:

| group | meaning |
|-------|---------|
| ATTENTION | something is wrong, act now |
| DUE | something is scheduled |
| COMPLETE | nothing is pending |

That also explains the date inversion in §4.5: for `ATTENTION` and
`DUE`, oldest first, because the most overdue thing is the most urgent.
For `COMPLETE`, newest first, because with nothing pending the only
useful order is most-recently-touched.

Keep the group names as they are — they match the existing mental
model and the seeded data. Record the meaning here rather than
renaming.

`StatesManager.sortByGroup` carries a `TODO: calculate this by position
in header row`. With `sort_order` stored, group rank is derivable from
the first `sort_order` at which each group appears. Not worth doing: three
groups, explicit ranking is clearer.

### 6.3 Where colour lives, and why not in the model

The GAS app stored a step's state as its cell's background colour
because in a spreadsheet the cell *is* the storage. There is no such
constraint here, and carrying it over would put presentation inside the
domain: the model would know hex values, the admin would let you edit
them, and a designer changing the palette would be writing a migration.

Split it by what each layer legitimately knows:

| Layer | Knows |
|-------|-------|
| Model | that a step has a state, that a state belongs to a group, and that groups rank |
| Template | the state's `slug` and `group`, emitted as data attributes |
| CSS | what those slugs and groups look like |

The model never names a colour. The stylesheet never encodes a rule.

Template emits identity, not appearance:

```html
<article class="card card--step"
         data-state="{{ step.state.slug }}"
         data-group="{{ step.state.group|lower }}">
```

One stylesheet owns the palette:

```css
/* jobs/static/jobs/states.css
   the only file in the project that knows what a state looks like */

.card--step { background: var(--state-bg); color: var(--state-fg); }

/* group fallback: a new state with no rule of its own still renders */
[data-group="attention"] { --state-bg: #b3261e; --state-fg: #ffffff; }
[data-group="due"]       { --state-bg: #ffd54f; --state-fg: #1a1a1a; }
[data-group="complete"]  { --state-bg: #f5f5f5; --state-fg: #1a1a1a; }

/* per-state, later in the cascade so it wins */
[data-state="error"]        { --state-bg: #b3261e; --state-fg: #ffffff; }
[data-state="overdue"]      { --state-bg: #e8710a; --state-fg: #1a1a1a; }
[data-state="due"]          { --state-bg: #ffd54f; --state-fg: #1a1a1a; }
[data-state="tentative"]    { --state-bg: #fff3cd; --state-fg: #1a1a1a; }
[data-state="accepted"]     { --state-bg: #1b5e20; --state-fg: #ffffff; }
[data-state="success"]      { --state-bg: #a5d6a7; --state-fg: #1a1a1a; }
[data-state="going-well"]   { --state-bg: #c8e6c9; --state-fg: #1a1a1a; }
[data-state="unremarkable"] { --state-bg: #f5f5f5; --state-fg: #1a1a1a; }
[data-state="bad-feeling"]  { --state-bg: #e28fae; --state-fg: #1a1a1a; }
[data-state="ghosted"]      { --state-bg: #e0e0e0; --state-fg: #424242;
                              border-style: dashed; }
[data-state="fail"]         { --state-bg: #d7ccc8; --state-fg: #4e342e; }
[data-state="blacklist"]    { --state-bg: #37474f; --state-fg: #ffffff; }
```

Two things fall out of this that the GAS version could not do:

- Adding a state is a data change. It renders in its group's colours
  immediately, with no CSS written, and no broken card.
- Dark mode is a media query, not a second set of columns. Not built
  now; the hook is there if wanted.

### 6.4 The palette

Fixed. It is not expected to change, and nothing in the app reads it at
runtime, so it needs no admin screen and no table.

Shape: `ATTENTION` is loud, because it means act now. `DUE` is warm and
mid-weight. `COMPLETE` is quiet — eight of the twelve states live there,
and a board of eight saturated blocks is unreadable. Within `COMPLETE`,
lightness carries the outcome: dark green for `ACCEPTED`, pale green
through neutral grey to brown-grey for `FAIL`, near-black for
`BLACKLIST`.

Every pair below was checked against WCAG AA for body text (4.5:1):

| state | bg | fg | ratio |
|-------|----|----|------:|
| ERROR | `#b3261e` | `#ffffff` | 6.54 |
| OVERDUE | `#e8710a` | `#1a1a1a` | 5.63 |
| DUE | `#ffd54f` | `#1a1a1a` | 12.33 |
| TENTATIVE | `#fff3cd` | `#1a1a1a` | 15.71 |
| ACCEPTED | `#1b5e20` | `#ffffff` | 7.87 |
| SUCCESS | `#a5d6a7` | `#1a1a1a` | 10.59 |
| GOING_WELL | `#c8e6c9` | `#1a1a1a` | 12.94 |
| UNREMARKABLE | `#f5f5f5` | `#1a1a1a` | 15.96 |
| BAD_FEELING | `#e28fae` | `#1a1a1a` | 7.27 |
| GHOSTED | `#e0e0e0` | `#424242` | 7.61 |
| FAIL | `#d7ccc8` | `#4e342e` | 7.20 |
| BLACKLIST | `#37474f` | `#ffffff` | 9.65 |

Worst case 5.63:1, against a 4.5:1 requirement.

Two deliberate choices in there:

- `BAD_FEELING` is darker than a pastel pink would be. At equal
  lightness, pink and green are the classic red-green collision, and
  `SUCCESS` sitting next to `BAD_FEELING` looking identical is the one
  confusion that actually matters. Darkening it separates them by
  lightness as well as hue.
- `GHOSTED` gets a dashed border. Some pairs in `COMPLETE` are close in
  lightness and colour alone will not always separate them — the state
  name is printed on every card, so colour is never the only channel,
  and `GHOSTED` gets a second visual one because it is the state you
  scan for.

The sticky summary card is deliberately outside this scheme: neutral
white with a hard right border, so it reads as a different kind of
object rather than another state.

Colour is the obvious case; the same split applies to the rest:

| Concern | Lives in | Never in |
|---------|----------|----------|
| Field values, relationships | `jobs/models.py` | views, templates |
| Sort rules (§4.5) | `jobs/ordering.py`, pure functions | views, templates, DB ordering hacks |
| Validation, coercion | `jobs/forms.py` | views, models' `save()` |
| Fetch and render | `jobs/views.py` | business rules |
| Markup, data attributes | templates | branching on business rules |
| Every colour, size, spacing | CSS | models, views, templates |

Phase 2 keeps the sort key a pure function precisely so it can be
tested without a database and cannot drift into a view.

### 6.5 Archiving

An opportunity is live while `archived_at` is `NULL`, archived once it
is set. That is the whole mechanism.

```python
class OpportunityQuerySet(models.QuerySet):
    def live(self):
        return self.filter(archived_at__isnull=True)

    def archived(self):
        return self.exclude(archived_at__isnull=True)
```

Explicit querysets, not a default manager that hides archived rows. A
manager that silently filters is convenient for a week and then bites
in the admin, in a data migration, and in search — the one place that
must see everything.

Three actions, matching how the app is used in bursts:

| Action | Effect |
|--------|--------|
| Archive one | `archived_at = now()` |
| Unarchive one | `archived_at = None` |
| Archive everything live | the "I got a job" action, at the end of a burst |

Nothing is deleted, so all three are reversible and none needs a scary
confirmation — though bulk archive touches every live row at once, so
it gets one anyway, with the count in it.

Two consequences worth stating:

- The board (§7) shows live opportunities only. Archived ones are not
  reachable from it beyond a count, by design: not seeing them is the
  point of archiving.
- Until search exists, the Django admin is how archived opportunities
  get looked at. It is already registered in phase 1, so this costs
  nothing.

The ordering rules in §4.5 apply to the live board. Archived
opportunities sort by `archived_at` descending — "which burst was this"
is the only question worth asking of them, and urgency ranking is
meaningless once nothing is pending.

### 6.6 Why a new opportunity is UNREMARKABLE

`DEFAULT_STEP_STATE` is `UNREMARKABLE`, in group `COMPLETE`, the
lowest-ranked group. That looks like an accident — new things sinking
to the bottom — but reading the full sort says otherwise.

`UNREMARKABLE` is `sort_order` 9 of 12, so a new opportunity lands here:

```
ATTENTION   ERROR, OVERDUE              act now
DUE         DUE, TENTATIVE              scheduled
COMPLETE    ACCEPTED, SUCCESS,          nothing pending,
            BAD_FEELING, GOING_WELL,    best outcome first
            UNREMARKABLE   ← new one, newest first within the state
            GHOSTED, FAIL, BLACKLIST
```

Mid-pile, above everything dead. And it is the semantically right
group: you applied, the ball is in their court, nothing is pending on
you — which is what `COMPLETE` means (§6.2). The `sort_order` ranking
inside the group reads as "how alive is this", with `ACCEPTED` on top
because an offer matters most even when nothing is due.

**Decision: keep it. The sort is not changed.**

The original worry — new opportunities getting buried — was a symptom
of the sheet having no archive, so the dead tail grew without limit.
The board now shows live opportunities only (§6.5), so that tail is
short and a new row lands near the top of it.

What is left of the worry is "I added something and it moved" — a
presentation problem, answered in presentation: after a create, the new
row is highlighted and scrolled to (§7). Floating new rows to the top
of the board instead would mean new-but-unremarkable outranking
`GOING_WELL`, and a board whose position no longer tracks how alive
something is.

If it turns out to grate in real use, the clean fix is a distinct
`APPLIED` state at a higher `sort_order` — a data change — not a
special case inside the sort function.

### 6.7 Contacts, companies and time

`Contact.name` is **not unique**, and that is the point. Two people can
share a name, and the app cannot tell them apart from a string. Making
the column unique would quietly merge them the first time it happened.

Employment is its own table because a contact moves. A recruiter who
was at one company last year is at another now, and both facts stay
true — the old opportunity should keep pointing at the person, not at
a name frozen in place.

**Open-ended stints are `NULL`, not a far-future date.** `NULL` on
`ended_on` means "still there or not known to have left", which is
exactly the truth. A sentinel like `9999-12-31` reads as a fact that
was never established, and every query then has to know the magic
value. `NULL` on `started_on` means the same for the other end.

Asking who was at a company on a given day:

```python
class EmploymentQuerySet(models.QuerySet):
    def on(self, day):
        return self.filter(
            Q(started_on__isnull=True) | Q(started_on__lte=day),
            Q(ended_on__isnull=True) | Q(ended_on__gte=day),
        )
```

Overlapping stints are allowed. Advising, contracting and gardening
leave are all real, and a uniqueness constraint forbidding overlap
would eventually be wrong. What is worth constraining is exact
duplicates: `unique_together` on `(contact, company, started_on)`.

`Step.contacts` is many-to-many because a step often involves several
people — the sample has a technical interview with two. The step points
at people, not at employments: for display you want the name, and
"who is at this company now" is a separate question the `Employment`
table already answers.

### 6.8 Why `position` stays free text

You listed `position` alongside company, contact and source as a
foreign key. Company, contact and source earn their tables — each value
recurs across opportunities, and each has attributes of its own.
A job title does not. `"Staff Software Engineer - Distributed AI"` is
used once and never again, so a `Position` table would hold one row per
opportunity, add a join to every query, and add a create-a-position
step to every form, in exchange for nothing.

So it stays a `CharField`, renamed `title` to stop it reading like a
foreign key. The sample also shows it carrying location and salary by
convention (§4.8), which is another reason not to treat it as a clean
key.

The useful version of that idea is a coarse classification — `Backend
Engineer`, `Staff Engineer`, `Engineering Manager` — which is
low-cardinality, recurs, and is worth filtering by. That is a different
column from the advertised title, and it is listed in §13 rather than
built now.

Override this if you disagree: it is one field and a migration.

### 6.9 Entering data without a management UI

Normalising usually drags in company and contact admin screens. It does
not have to here. The forms keep a plain text input backed by a
`<datalist>` of existing names, and the view does `get_or_create` on
save. Typing a new company creates it; typing an existing one reuses
it. No second screen, no lookup step, and the "minimum of fuss" goal
survives the normalised model.

Free creation invites near-duplicates — `Fintech`, `FinTech` and
`fintech` as three rows. Resolve on the way in rather than cleaning up
later:

```python
def by_name(model, raw):
    name = " ".join(raw.split())  # collapse stray whitespace
    return model.objects.filter(name__iexact=name).first() or model.objects.create(name=name)
```

First spelling entered wins; later variants match it. On SQLite
`iexact` is ASCII-only, which is fine for these names and worth knowing
before someone relies on it for accented ones.

The Django admin registered in phase 1 covers what that cannot catch —
merging `Meta` and `Facebook`, or fixing a typo that was saved first
and is now the canonical spelling.

### 6.10 Extensible enums are tables

`Sector`, `Source` and `State` are all the same shape: a small
controlled vocabulary that has to grow without a deploy. Django's
`TextChoices` cannot do that — adding a sector would mean editing an
enum, writing a migration and shipping. So all three are tables.

`Group` stays a `TextChoices` by contrast, because it is not a
vocabulary. It is three fixed buckets with a ranking rule attached
(§6.2), and adding a fourth would mean deciding where it ranks — a code
change either way.

The test is whether a new value needs a decision in code. A new sector
does not. A new group does.

Note what this does *not* pull back in: `State` is a table because the
vocabulary is data, while its colours stay in CSS (§6.3). Being
extensible at runtime and being presentation-free are separate
questions, and the answer differs per field.

Starter sectors, to be extended by typing:

```
AI / ML · Consultancy / agency · Developer tools · E-commerce ·
Education · Energy · Fintech · Gaming · Government / public sector ·
Healthtech · Logistics · Media / publishing · Non-profit · Retail ·
SaaS · Telecoms · Travel · Other
```

## 7. UI

One page, `GET /`. One row per live opportunity (§6.5), with an
archived count in the header and nothing else about the archive.

```
---------------------------------------------------
| SUMMARY | | STEP 3 | STEP 2 | STEP 1 |          |
|         | |<------- scrolls ------------------->|
---------------------------------------------------
   ^ fixed        ^ most pressing first (§4.5), oldest right within a group
```

A row is two blocks, not one scroller with a pinned first child. The
summary holds its place because it is the row's other block; the steps
sit in a block of their own, and that block is what scrolls. Making the
row itself the scroller runs the scrollbar under the summary card as
well, which is the tell that the two are not separate.

```css
.opportunity        { display: flex; gap: .5rem; }
.card--summary      { flex: 0 0 18rem; }
.opportunity__steps { display: flex; align-items: center; flex: 1 1 0;
                      min-width: 0; gap: .5rem; }
.opportunity__track { display: flex; flex: 1 1 0; min-width: 0; gap: .5rem;
                      overflow-x: auto; scrollbar-width: none; }
.card--step         { flex: 0 0 16rem; }
```

`min-width: 0` is load-bearing: a flex item defaults to `min-width: auto`,
so without it the steps block sizes itself to its steps and pushes the
row wide instead of scrolling.

The summary card collapses `comments` to a few lines behind a native
`<details>`, because it holds the pasted job ad — 1870 characters in
the sample export (§4.8) — and an 18rem card cannot show that inline.
No JavaScript needed for the toggle.

Each row's steps scroll on their own, so a long-running opportunity does
not force the whole page sideways and does not drag its neighbours with
it. The summary card stays where it is beside them. Step cards carry
`data-state` and `data-group`; CSS turns those into colours (§6.3).

What is hidden is the scrollbar, not the scrolling. A row with more
steps than fit grows an arrow at each end of its track, which moves it a
card at a time; a row whose steps already fit grows neither. The wheel,
the trackpad and the keyboard still scroll the track, and the arrows
follow, because they read the scroll position rather than a count of
clicks — an index would go stale the moment the trackpad was used.

### On a phone

A summary beside its steps does not fit, so the row stacks:

```
-------------------------------------
| Staff Backend Engineer          › |   <- tap to expand downwards
| Northwind Analytics               |
-------------------------------------
| ‹ |   STEP 2 (one at a time)  | › |
-------------------------------------
```

The summary spans the viewport and shows two lines — title and company —
until it is tapped. The steps become one card at a time with an arrow
either side; the track does not scroll, so nothing is swiped sideways
and no step is half visible. An arrow that cannot move disables rather
than disappears, and a row with one step or none shows neither.

That needs state the CSS cannot hold on its own, so `static/js/board.js`
holds it: about eighty lines, vendored, deferred, no build step. It is
an enhancement rather than a requirement — the markup ships with every
summary expanded and the track scrollable, and the rules that take the
scrolling away are scoped to `.has-js`, which the script adds. A browser
that never runs it gets the laptop board at phone width.

### HTMX routes

There is no panel. A card shows what it has, edits itself, and is the shape
everything else borrows.

This table first described a drawer for everything, which was the GAS sidebar
carried over — and that sidebar existed because a spreadsheet had nothing else
to offer. Three things happen on the card instead:

- **Changing one value.** Click it and it becomes an input; blur or Enter
  commits, Escape puts it back.
- **Filling in what is not there.** An empty field is left off the card, so
  Edit opens the whole card as one form with every field showing, and Done
  saves it and hides the empty ones again.
- **Creating.** A blank card in edit mode — a row at the top of the board, a
  step at the near end of the track, a note at the top of the list — saved with
  one submit, because there is no row yet to save a field into.

| Method | Path | Returns |
|--------|------|---------|
| GET | `/` | full board |
| GET | `/<kind>/<id>/field/<name>` | that value, as an input |
| POST | `/<kind>/<id>/field/<name>` | that value again, or the board |
| GET | `/<kind>/<id>/field/<name>/cancel` | that value, untouched |
| GET | `/<kind>/<id>/edit` | the whole card, as one form |
| POST | `/<kind>/<id>/edit` | the card again, empty fields hidden |
| GET | `/opportunities/new` | a blank row, in edit mode |
| POST | `/opportunities/` | full board, new row marked (§6.6) |
| GET | `/opportunities/<id>/steps/new` | the row, with a blank step card |
| POST | `/opportunities/<id>/steps/` | row partial, or the board |
| GET | `/opportunities/<id>/notes/new` | the row, with a blank note |
| POST | `/opportunities/<id>/notes/` | row partial |
| GET | `/new/cancel` | nothing, which takes a blank card away |
| POST | `/opportunities/<id>/delete` | empty, swaps row out |
| POST | `/steps/<id>/delete` | row partial, or the board |
| POST | `/notes/<id>/delete` | row partial |
| POST | `/opportunities/<id>/archive` | empty, swaps row out |
| POST | `/opportunities/<id>/unarchive` | full board |
| POST | `/opportunities/archive-live` | full board, now empty |

`<kind>` is `opportunities`, `steps` or `notes`. `GET` and `POST` share a URL in
both editing shapes: what the `GET` replaces is what the `POST` puts back.

Naming a field in a URL is only safe against a whitelist, so `forms.EDITABLE`
holds one per model and anything else is a 404. `archived_at` is not in it —
archiving is its own action (§6.5) — and neither are the timestamps.

A mutation returns the value or the card it changed, and the whole board when
the change moved rows about — which a step's state or date can do, since the
sort keys an opportunity on its newest step. Which of them is read rather than
guessed, by comparing the board's order before the change with its order after.
A board response is retargeted onto `#board`, a row response onto its own row.
`django-htmx` gives `request.htmx` for partial-vs-full rendering; it is one
small dependency and earns its place.

Two of these are always the board. A create lands its row in sorted order rather
than on top (§6.6), so the board re-renders with the new row marked; and an
unarchive puts back a row that is not on the page to be swapped.

Nothing here needs the script. A value is an anchor with an `href`, so following
one without htmx opens a page with that field on it; a blank card asked for the
same way is a page too; and every input is a real form that posts and redirects
to the board. What the script adds is the swap and Escape.

## 8. Phases

TDD throughout, per AGENTS.md: failing test, confirm the failure is the
expected one, minimal implementation, refactor green. `task qa` before
every PR.

### Phase 0 — Scaffolding

- `uv init`, Python 3.14, Django, pytest, pytest-django, ruff, ty.
- `Taskfile.yml` with `task dev`, `task test`, `task qa`
  (`ruff check` + `ruff format --check` + `ty` + `pytest`).
- Add ruff and ty hooks to `.pre-commit-config.yaml`, which currently
  has no Python linters.
- `config/` project, `jobs/` app, `/healthz` returning 200.
- `.github/workflows/ci.yml` running `task qa` on PRs and `main`.

Pin `requires-python = ">=3.14"` in `pyproject.toml` and use the same
version in the CI matrix and on the VPS, so the three cannot drift.

Done when: `task qa` green in CI, `/healthz` returns 200 locally.

### Phase 1 — Models

- Tests for model defaults and constraints first.
- `Company`, `Contact`, `Employment`, `Source`, `State`, `Opportunity`,
  `Step` + migrations.
- Data migration seeding the 12 states from §6.1, a starter set of
  sources (LinkedIn, Wellfound, referral, direct, recruiter) and the
  sectors in §6.10 — picklists, not fixed vocabularies; new ones are
  created on the fly.
- `Employment.on(day)` with tests for the four `NULL` combinations
  (§6.7): open start, open end, both open, both set.
- Guard test: `State` exposes no colour field, so the boundary in
  §6.3 fails loudly rather than eroding.
- Django admin registered for every model: a free CRUD backdoor while
  the real UI is being built, and the place duplicate contacts and
  companies get merged later (§6.9).
- Fill in `docs/initial-context.md` (architecture, boundaries, the
  pydantic deviation from §5).

Done when: states and sources seeded, admin can create an opportunity
with steps, and a contact can be moved between companies without
losing the opportunities that point at them.

### Phase 2 — Ordering

The one piece of real domain logic. Port §4.5 exactly.

- Table-driven tests covering: group ranking, the `COMPLETE` inversion,
  step-position tie-break, opportunities with no steps, equal
  timestamps, null `time`.
- Implement as a queryset/manager method plus a pure sort key function.
  Keep the key function pure and directly unit-testable.

Done when: ordering tests pass and the rules in §4.5 are each covered
by a named test.

### Phase 3 — Read-only board

- Board view, row partial, summary card, step card.
- Tailwind standalone CLI wired into `task dev` in watch mode.
- Fixed summary + per-row horizontal scroll, and the phone layout (§7):
  a stacked row, a summary that collapses to two lines, and one step at
  a time behind arrows.
- State palette from §6.4 in one stylesheet, keyed on `data-state` /
  `data-group`.
- Tests: view returns 200; steps render newest-first; a row with no
  steps renders; cards emit `data-state` and `data-group`; a state
  with no per-state CSS still renders in its group's colours; a 2000
  character comment does not blow out the summary card; every
  pair in §6.4 clears 4.5:1, asserted by a contrast test so a later
  tweak cannot quietly break legibility.

Done when: a sheet-shaped board renders from seeded data and looks
right at phone width.

### Phase 4 — Mutations

- All routes in §7, with `ModelForm`s. Everything happens on the card:
  a value edits itself, Edit opens the fields an empty value hides, and
  creating is a blank card in edit mode. No panel.
- Company, contact, source and sector entered as free text backed by a
  `<datalist>`, resolved case-insensitively on save (§6.9). No separate
  management screens.
- Company's url, LinkedIn, head office and sector are optional and edited
  from the opportunity form; a company created mid-flow needs only a name.
- Creating an opportunity also creates its first step (§4.4).
- Archive, unarchive, and archive-everything-live (§6.5).
- After a create, highlight the new row and scroll it into view (§6.6).
- Delete confirmations; bulk archive confirms with its count.
- Tests: one per route, plus validation-failure re-render, plus the
  create-first-step behaviour, plus that editing the first opportunity
  updates rather than duplicates (the §4.6 bug, as a regression test),
  plus that the board excludes archived opportunities and that
  unarchiving puts one back, plus that typing an existing company reuses
  it rather than creating a second one, plus that `FinTech` and
  `fintech` resolve to one `Sector`, plus that a step keeps several
  contacts.

Done when: everything the GAS menus did is doable in the browser.

### Phase 5 — Production settings

- `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
  from environment.
- `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT=False` (Caddy already
  redirects), `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`.
- WhiteNoise, `collectstatic`.
- SQLite `OPTIONS`: `PRAGMA journal_mode=WAL`, `synchronous=NORMAL`,
  `transaction_mode="IMMEDIATE"`.
- `manage.py check --deploy` clean, asserted in CI.

Done when: `check --deploy` reports no issues.

### Phase 6 — Deploy

Files in `deploy/`, secrets never in the repo.

- `crm-jobs.service`: gunicorn, 2 workers, bound to `127.0.0.1:8000`,
  running as an unprivileged `crm` user, `EnvironmentFile=/etc/crm-jobs/env`.
- `Caddyfile`:
  ```
  crm.example.com {
      basic_auth {
          fritz <bcrypt hash from `caddy hash-password`>
      }
      reverse_proxy 127.0.0.1:8000
  }
  ```
- `.github/workflows/deploy.yml`: on push to `main`, needs the CI job,
  SSHes in and runs pull → `uv sync --frozen` → `migrate` →
  `collectstatic` → `systemctl restart crm-jobs`.
- Deploy user is `deploy`, not root. Its sudoers entry permits exactly
  `systemctl restart crm-jobs`.
- Paths: code `/srv/crm-jobs`, data `/var/lib/crm-jobs/db.sqlite3`,
  secrets `/etc/crm-jobs/env` mode 0600. Deploy touches code only.
- Firewall: 80, 443, and SSH. Port 8000 never exposed.

Done when: push to `main` lands on the VPS and the site answers over
HTTPS behind the password prompt.

### Phase 7 — Retire the GAS app

- Confirm backups have been running and a restore has been tested.
- Export the sheet to CSV and keep it outside the repo as the archive.
- Delete `clasp/`, or move it to `docs/archive/` if it is worth keeping
  as history.
- Archive this plan per AGENTS.md:
  `docs/archive/YYYY-MM-DD-HHMM-<shortsha>-001-port-gas-to-django.md`.

## 9. Local development

```bash
uv sync
task dev          # runserver + tailwind watch
task test
task qa
```

SQLite file lives at `./db.sqlite3` locally, gitignored.

## 10. Backups

Required before phase 7.

- systemd timer, daily:
  `sqlite3 /var/lib/crm-jobs/db.sqlite3 ".backup /var/backups/crm-$(date +%F).sqlite3"`
- Keep 14 days locally, push off-box with restic or rsync.
- Test a restore once, by hand, and note in `docs/` that it was done.

`.backup` is used rather than `cp` because it is safe against a
concurrently written WAL database.

## 11. Risks

| Risk | Mitigation |
|------|-----------|
| SQLite file is the only copy of the data | §10, tested before the sheet is retired |
| Shared basic-auth credential, no logout | Accepted for one user; gate is swappable without app changes |
| SQLite writer lock under concurrent writes | WAL + `IMMEDIATE` transactions; a single user will not hit it |
| Ordering rules ported subtly wrong | Phase 2 is test-first, with each rule in §4.5 named in a test |
| Deploy clobbers the database | Data lives outside the deploy directory |

## 12. Open questions

None outstanding. Resolved along the way:

| Was | Resolved in |
|-----|-------------|
| State list, groups, order | §6.1 |
| Palette | §6.4 |
| Whether `Pool` becomes a model | §4.7, §6.5 |
| Archive vs delete | §6.5 |
| Whether the `UNREMARKABLE` default is a bug | §6.6 |

## 13. After the port

Not in scope here. Listed so the port does not block them.

### Search — the named first follow-up

Search is what makes the archive usable, and it is the archive's only
UI (§6.5). Nothing in this plan should get in its way:

- Searchable text lives in ordinary columns — `company`, `position`,
  step `title`, both `comments` fields — not packed into one string as
  the sheet did (§4.2).
- `archived_at` is a filter, not a partition. Search spans live and
  archived in one query and can scope either way. This is why §6.5
  refuses a default manager that hides archived rows.
- Start with `icontains` across those columns. For a few hundred
  opportunities on SQLite that is instant, and it is about fifteen
  lines. Move to FTS5 only if it actually gets slow — that means a
  virtual table and triggers in a raw-SQL migration, which is real
  weight to carry for a personal tracker.
- Results reuse the existing row partial, so the summary-plus-steps
  layout works in search with no new templates.

### Import of the old sheets

Wanted, deliberately not now. §4.9 and §4.10 hold the packing rules and
the field mapping, validated against the sample export.

Decisions deferred to when it is built:

- How to recover `Step.state`, per the three options in §4.10.
- What `archived_at` becomes. There is no such timestamp in the sheet.
  The newest step date of each opportunity approximates when it went
  dormant and is better than the import time, which would collapse
  every generation of archive into one moment.
- Nothing about malformed cells: they are cleaned in the sheet before
  import, and the importer reports rather than guesses (§4.9).

### Contact autosuggest

The reason `Employment` exists now. Once the data is there:

- Adding a contact to a step suggests the people currently at that
  opportunity's company — `company.employments.on(step.date)`, which
  §6.7 already supports.
- A typed name matching someone at a different company raises "is this
  the same person?". Yes moves them: close the old `Employment` with an
  `ended_on`, open a new one. No creates a second `Contact` with the
  same name, which the schema allows on purpose.
- Suggesting by the step's date rather than today matters for archived
  opportunities, where "who was there then" is not "who is there now".

None of this is built in the port. The schema is what the port has to
get right, and it does.

### Possible later, not committed

- A coarse role classification on `Opportunity` — `Backend Engineer`,
  `Staff Engineer`, `Engineering Manager` — as a foreign key, separate
  from the advertised `title` (§6.8). Low-cardinality and worth
  filtering by, unlike the title itself.
- Split `location` and `salary` out of `title` (§4.8). They are
  already there by convention, and separate fields make them
  filterable. Left out of the port to keep the model a like-for-like
  move; worth doing once search exists.
- Dark mode: a media query over §6.4, no model change.
- Per-state colour editing without a deploy: a `theme` table read by a
  template tag, keeping hex out of `State`. Only if the palette turns
  out to change, which it is not expected to.
