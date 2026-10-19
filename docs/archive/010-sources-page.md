# 010 — A page of sources

Status: implemented
Date: 2026-10-19

Closes #25. Besides the board there is nowhere to keep track of places to look
for future opportunities.

## 1. Goal

- A page at `/sources/` listing places to look: a link and free-text notes each
- Create, update and delete, as plain forms that work without the script
- Reachable from the board's header, with a link back

## 2. Non-goals

- Turning a source into an opportunity
- htmx swaps; a POST and a redirect is enough for a page this small
- Touching `Source`, the picklist of where an existing opportunity came from

## 3. Design

- New model `Lead` (`url`, `notes`), newest first. Named apart from `Source` so
  the two ideas do not blur
- `LeadForm` validates the link; a bad one re-renders the page with the error
  and keeps what was typed
- Routes: `sources/`, `sources/new`, `sources/<pk>/`, `sources/<pk>/delete`
- Each row is its own form with Save and Delete (`formaction`) buttons
- Styling in `assets/forms.css`; the templates carry class names only

## 4. Tests

`tests/jobs/test_leads_page.py`: listing and order, create, update, delete,
invalid links, 404, GET cannot delete, links between board and page.
