# Takwimu Bridge (placeholder name) — Student Data Portal POC

A proof-of-concept **Quarto website** for a socio-economic data portal aimed at
Tanzanian university students: browse a curated dataset catalog, view full
metadata, request access, and (once approved) download — no fieldwork required.

> **Naming & branding note:** "Takwimu Bridge" ("Takwimu" is Swahili for
> "statistics/data"), the color palette, university list, and all logos in this
> repo are **placeholders** chosen to demonstrate the design. Swap them for the
> officially approved name/brand once confirmed — see "Where placeholders live"
> below.

## What this is (and isn't)

This is a **static site** (no backend, no database, no real authentication).
It fully implements the *user experience* of the request → approve → download
workflow, but the "approve" and "download" steps are simulated:

| Feature | Status |
|---|---|
| Data catalog with search / filter / sort | ✅ Real, works fully (Quarto listing page) |
| Dataset detail pages with full metadata | ✅ Real content, sample/placeholder datasets |
| Request Access form | ⚠️ Wired to a form-service placeholder (Formspree) — needs a real endpoint |
| "Pending Approval" state | 🧪 Mocked — every dataset always shows this state |
| Download button | 🧪 Mocked — permanently disabled, no real file gating |
| Authentication / accounts | ❌ Not implemented (by design for this phase) |

Every mocked/placeholder area is marked in the source with an
`<!-- TODO: backend -->` comment so it's easy to grep for later.

## Requirements

- [Quarto](https://quarto.org/docs/get-started/) ≥ 1.4 (tested with 1.10)
- No other dependencies — this is a static HTML/CSS/JS site once rendered.

## Install & Run

```bash
# 1. Install Quarto (if not already installed)
#    https://quarto.org/docs/get-started/

# 2. From the project root:
quarto preview      # live-reloading local preview at http://localhost:xxxx
quarto render        # builds the static site into ./_site
```

If `quarto` isn't recognized in your shell, make sure its `bin/` folder is on
your `PATH` (on Windows, typically `C:\Program Files\Quarto\bin`).

## Project Structure

```
_quarto.yml                Site config: navbar, footer, search, theme
custom.scss                 Bootstrap variable overrides + component styles
_includes/head-extra.html   Google Fonts + Bootstrap Icons <link> tags
index.qmd                   Home page (hero, problem, how-it-works, featured, partners)
catalog.qmd                 Data Catalog — Quarto listing page (search/filter/sort)
datasets/*.qmd              9 individual dataset detail pages (the listing "contents")
data/*.csv                  Small placeholder sample CSVs referenced by dataset pages
request-access.qmd          Request Access form (Formspree placeholder)
about.qmd                   Mission, problem statement, governance placeholder
partners.qmd                For Universities & Partners
guidelines.qmd               Guidelines & FAQ (data-use terms, citation, turnaround)
contact.qmd                  Contact page + demo contact form
images/                      Logo, dataset thumbnails, partner logo placeholders (SVG)
```

## Where to plug in the form endpoint

Two files contain a **live** `<form>` element pointed at a Formspree
placeholder — search for `YOUR_FORM_ID`:

- [`request-access.qmd`](request-access.qmd) — the main dataset request form
- [`contact.qmd`](contact.qmd) — the contact form

To go live with [Formspree](https://formspree.io/):

1. Create a free Formspree account and a new form; copy its endpoint,
   e.g. `https://formspree.io/f/abcd1234`.
2. Replace `https://formspree.io/f/YOUR_FORM_ID` in the `action="..."`
   attribute of each `<form>` tag.
3. Re-render (`quarto render`) — no other changes needed.

**Alternative:** replace the `<form>...</form>` block with an embedded Google
Form, e.g.:

```html
<iframe src="https://docs.google.com/forms/d/e/YOUR_FORM_ID/viewform?embedded=true"
        width="100%" height="900" frameborder="0">Loading…</iframe>
```

The `?dataset=...` pre-fill script at the bottom of `request-access.qmd` is
specific to the native `<form>` approach; if you switch to an embedded Google
Form, use Google Forms' own "pre-filled link" feature instead and update the
`href`s in each `datasets/*.qmd` page's **Request Access** button accordingly.

## Where placeholders live

| Placeholder | Where | Replace with |
|---|---|---|
| Portal name "Takwimu Bridge" | `_quarto.yml` (`website.title`, navbar, footer), all `pagetitle:` fields | Officially approved portal name |
| Brand colors | `custom.scss` (`scss:defaults` section, top of file) | Approved brand palette |
| Logo | `images/logo.svg` | Real logo |
| Partner universities & logos | `partners.qmd`, `index.qmd` (logo strip), `request-access.qmd` (university dropdown), `images/partners/*.svg` | Confirmed partner list & real logos |
| Form endpoint | `request-access.qmd`, `contact.qmd` (`YOUR_FORM_ID`) | Real Formspree ID or Google Form embed |
| Site URL | `_quarto.yml` (`website.site-url`) | Production domain |
| Sample datasets & CSVs | `datasets/*.qmd`, `data/*.csv` | Real curated datasets, once available |
| Governance/team table | `about.qmd` | Real names/roles |
| Contact details | `contact.qmd` | Real email/phone/address |

## Phase 2 — what a real backend would add

This POC deliberately stops at the static-site boundary. A production version
would need:

1. **Authentication** — real student/staff accounts (likely via a university
   SSO/OAuth provider, or a simple email + institutional-domain check),
   replacing the "no login" static experience.
2. **An approval workflow** — a backend service (e.g. a small API + database,
   or a Shiny/Flask/Django app) to store requests, notify administrators,
   record approve/deny decisions, and email requesters.
3. **Truly gated downloads** — files served only to authenticated, approved
   users (e.g. signed short-lived URLs from cloud storage, or a small
   API endpoint that checks approval status before streaming the file),
   instead of the always-disabled Download button shown here.
4. **Admin/reporting dashboard** — for reviewing pending requests and
   reporting request volume per university (ties into the "For Universities"
   partnership model).

Every place in the code where this matters is flagged with
`<!-- TODO: backend -->` — search the project for that string to find them all.

## Sample Dataset Categories

The 9 sample datasets span: Demographics & Census · Household Budget / Income
& Consumption · Health & Nutrition · Education · Labour & Employment ·
Agriculture & Food Security · Poverty & Living Standards · Gender · Migration
& Urbanization. All metadata is realistic but illustrative; downloadable CSVs
are small, clearly-labeled placeholder files — **not real or real-looking
microdata**.
