# Sustainable Solutions Tanzania (SST)

The website for Sustainable Solutions Tanzania: About, Services, Products, Projects,
Insights & Opportunities, and Partners, built around two tools that share one set of
user accounts and one admin:

- **TakwimuBridge** (`/datasets/`), where students create accounts, upload their own
  socio-economic research datasets, and search/download datasets shared by other students.
- **TakwimuBridge QDA** (`/qda/`), a qualitative data analysis tool: code KIIs, FGDs,
  interviews and open-ended responses into themes, then get frequencies, weights,
  comparisons, theme clouds and exports. Projects are saved to the researcher's account.

TakwimuBridge itself replaces an earlier static Quarto proof-of-concept (archived in
`../SITE-1`), which only supported an admin-curated, view-only catalog with no real
accounts. The site was then rebranded from a standalone "DataBridge" product into
this fuller SST organizational site, with TakwimuBridge as one product within it.

## Requirements

- Python 3.11+

## Setup

```bash
python -m venv ../databridge_venv        # or your preferred venv location
../databridge_venv/Scripts/activate      # Windows; use `source .../bin/activate` on macOS/Linux
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_demo_data          # creates 9 sample datasets + categories + NBS link
python manage.py seed_sst_placeholders   # creates placeholder stats/project/insights rows
python manage.py createsuperuser         # for /admin/ access
python manage.py runserver
```

Visit http://127.0.0.1:8000/

## Project layout

```
databridge/         Project settings, root urls
accounts/           Custom User model (extends AbstractUser with `institution`), signup/login (username or email),
                    password change/reset
datasets/           Category & Dataset models; TakwimuBridge's catalog search/filter, upload, download, "My Uploads"
core/                Home, About Us, Services, Products, Projects, Insights & Opportunities, Partners, Data Custodians, Guidelines & FAQ, Contact
qda/                 TakwimuBridge QDA: project models + admin, sync API, pages; front-end in qda/static/qda/js/
templates/           base.html + per-app templates, registration/ (login, signup)
static/              custom.css (SST brand palette: navy + green), images/ (logo + category icons)
seed_files/          Sample CSVs used by `seed_demo_data` for the 9 demo datasets
media/               Uploaded dataset files land here (gitignored)
```

## Key behavior

- Anyone can browse and search the TakwimuBridge catalog (`/datasets/`) without an account.
- Uploading (`/datasets/upload/`) and downloading a file both require login.
- Uploads are published immediately, there is no admin approval step.
- Users can edit/delete their own uploads via "My Uploads" in the account menu.
- Allowed upload file types: csv, xlsx, xls, json, dta, sav, zip, pdf, max 20MB.
- The Services page's office email is a placeholder ("coming soon"), update
  `templates/core/services.html` once a real address is ready.
- The Data Custodians page (`core.DataCustodian` model) is seeded with only the
  National Bureau of Statistics (NBS); add more via `/admin/` once you've
  confirmed their URLs.
- `core.SiteStat`, `core.Project`, `core.Partner`, and `core.Insight` back the new
  Projects/Insights/Partners/stats-strip sections and are seeded with a single
  obviously-placeholder row each via `python manage.py seed_sst_placeholders`
  (`Partner` is seeded empty). Replace/add real ones via `/admin/`. `Project`,
  `Partner`, and `Insight` images are static-path strings (like `Category.icon`,
  e.g. `images/projects/example.jpg`), not uploads, so add the actual image files
  under `static/` yourself and reference their path.

## TakwimuBridge QDA (`/qda/`)

Moved here from the static Quarto + Supabase version (`../TAKWIMUBRIDGE-QDA`,
live on Vercel), keeping its front-end: the coding and analysis run in the
browser (`qda/static/qda/js/`), and Django adds accounts, storage and the admin.

- **Opening page.** `/qda/` opens on a sign-in page (`qda/views.py: welcome`). Signed-in
  users, and visitors who chose **Continue without an account** this browser session
  (a session cookie), can use the app pages; everyone else is sent to sign in and
  brought back afterwards. Guests' projects stay in their browser only. Switch guests
  off with `DJANGO_QDA_ALLOW_GUESTS=False`. The User Guide and About pages are public.
- **Accounts** are the site's accounts: one SST account works for the dataset catalogue
  and the QDA tool. People sign in with their username or email address
  (`accounts/backends.py`); new sign-ups need an email no other account uses.
- **Storage.** The browser keeps the working copy (fast, and it keeps working if the
  connection drops) and `cloud.js` uploads each change a moment later to
  `/qda/api/projects/` (`qda/api.py`). Each project is stored as rows — `Project`,
  `Analysis`, `Source` (transcripts), `Theme`, `Coding` (`qda/models.py`) — so the admin
  can browse everything; `qda/sync.py` converts between the app's project document and
  those rows without losing anything.
- **No silent overwrites.** Every upload names the revision it started from. If the same
  project changed on another computer meanwhile, the server refuses and the browser keeps
  its version as a separate "(conflicted copy)" project. An upload whose reply was lost
  (dropped mobile connection) can be resent safely. Large uploads are gzipped, and
  transcripts are only re-sent when they change.
- **Signing out** (sidebar or My Account) uploads what's left and removes the account's
  projects from that browser, which matters on shared computers. Logging out from the
  website's menu has the same effect the next time the tool is opened.
- **Admin** (`/admin/` → TakwimuBridge QDA): every researcher's projects, sources, themes
  and coded references, searchable. Project content is read-only there (the researchers'
  browsers own it). Actions: *Download backup (JSON)*, which anyone can restore in the
  tool with Projects → Restore; *Move to trash* / *Restore from trash* (deleting in the
  app also moves a project to the trash); and delete for good. Deactivate a person by
  unticking *Active* on their user account.

Data protection: transcripts can contain personal information, and SST's administrators
can read every project stored here. Check that this fits the projects' consent forms
and Tanzania's Personal Data Protection Act.

## Running the tests

```bash
python manage.py test
```

Covers the QDA sync (document ↔ rows, revisions, conflicts, resends, gzip, size limits,
CSRF, one user never seeing another's projects), the sign-in page and its guest mode,
the admin actions, and sign-in by username or email, sign-up and password change/reset.

## Deployment (PythonAnywhere)

A paid account is needed: free accounts have no Postgres, can only reach a short list of
outside websites (so no email service), and their web apps stop unless renewed every three
months. Choose the **EU** site (eu.pythonanywhere.com) when signing up; it's closer to
Tanzania than the US one, and accounts can't move between them later. Replace `<you>`
below with your PythonAnywhere username.

1. **Database (Postgres).** On the *Databases* tab, buy Postgres, set its superuser
   password and note the host and port. In a *Bash console*:
   ```bash
   psql -h <host> -p <port> -U super
   CREATE DATABASE databridge;
   CREATE USER databridge WITH PASSWORD 'choose-a-long-password';
   ALTER DATABASE databridge OWNER TO databridge;
   \q
   ```
   (MySQL, which paid accounts include, also works: add `mysqlclient` to
   `requirements.txt` and use a `mysql://` `DATABASE_URL`. Postgres is the better fit:
   proper full-text search later, and easy to move to another host.)
2. **Code and packages** (Bash console):
   ```bash
   git clone https://github.com/RESEARCH-STD/SITE-1.git databridge
   cd databridge && git checkout <branch>
   mkvirtualenv --python=python3.12 databridge-venv
   pip install -r requirements.txt
   ```
3. **Settings.** `cp .env.example .env` and fill in at least:
   ```
   DJANGO_SECRET_KEY=<output of: python -c "import secrets; print(secrets.token_urlsafe(50))">
   DJANGO_DEBUG=False
   DJANGO_ALLOWED_HOSTS=<you>.eu.pythonanywhere.com
   DATABASE_URL=postgres://databridge:choose-a-long-password@<host>:<port>/databridge
   ```
   plus the `DJANGO_EMAIL_*` lines once an email service is set up (password-reset
   links need it). Leave `CLOUDINARY_URL` empty: PythonAnywhere keeps uploaded files.
4. **Prepare** (same console, inside `databridge/`):
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py createsuperuser
   python manage.py seed_demo_data && python manage.py seed_sst_placeholders   # optional
   ```
5. **Web app.** *Web* tab → *Add a new web app* → *Manual configuration* → Python 3.12.
   Set *Virtualenv* to `/home/<you>/.virtualenvs/databridge-venv`, and replace the WSGI
   file's contents with:
   ```python
   import os, sys
   path = "/home/<you>/databridge"
   if path not in sys.path:
       sys.path.insert(0, path)
   os.environ["DJANGO_SETTINGS_MODULE"] = "databridge.settings"
   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
   Under *Static files* add `/static/` → `/home/<you>/databridge/staticfiles` and
   `/media/` → `/home/<you>/databridge/media`. Turn on *Force HTTPS*, then *Reload*.
   If pages keep redirecting to themselves, add `DJANGO_SECURE_SSL_REDIRECT=False` to
   `.env` and reload.
6. **Updating later:** `git pull`, `pip install -r requirements.txt`,
   `python manage.py migrate`, `python manage.py collectstatic --noinput`, then *Reload*.
7. **Backups.** Make a nightly copy of the database on the *Tasks* tab, for example:
   ```bash
   cd ~/databridge && mkdir -p ~/backups && pg_dump "$(~/.virtualenvs/databridge-venv/bin/python -c 'from dotenv import dotenv_values; print(dotenv_values(".env")["DATABASE_URL"])')" | gzip > ~/backups/databridge-$(date +%F).sql.gz
   ```
   Run it once in a console first to check it works, and download a copy now and then.

## Deployment (Render)

This repo is set up to deploy on [Render](https://render.com) via the included
`render.yaml` blueprint: production settings switch on env vars (`databridge/settings.py`),
static files are served by WhiteNoise, the database is Postgres via `DATABASE_URL`,
and uploaded dataset files go to Cloudinary (so they survive redeploys, unlike
Render's local disk).

1. **Push this repo to GitHub** (or GitLab/Bitbucket) — Render deploys from a
   connected git repo.
2. **Create a free [Cloudinary](https://cloudinary.com) account.** Its dashboard
   shows an "API Environment variable" value shaped like
   `cloudinary://<api_key>:<api_secret>@<cloud_name>` — copy it.
3. **In the Render dashboard:** New → Blueprint → connect this repo. Render reads
   `render.yaml` and provisions a free Postgres database plus a free web service.
4. When Render asks for the `CLOUDINARY_URL` env var (it's marked `sync: false`
   in the blueprint so it's never committed to the repo), paste the value from
   step 2.
5. The first deploy runs `build.sh`: installs dependencies, runs `collectstatic`,
   and runs `migrate`.
6. Once it's live, open the service's **Shell** tab in the Render dashboard and run:
   ```bash
   python manage.py createsuperuser
   python manage.py seed_demo_data          # optional: seeds the 9 demo datasets
   python manage.py seed_sst_placeholders   # optional: seeds placeholder stats/project/insights
   ```
7. **Using a custom domain?** Add it to the `DJANGO_ALLOWED_HOSTS` env var
   (comma-separated). Render's own `*.onrender.com` domain is picked up
   automatically and doesn't need this.

Notes on the free tier: Render's free Postgres database expires after 90 days
(you'll need to create a new one and re-migrate/re-seed, or upgrade to a paid
plan), and free web services spin down when idle, so the first request after a
quiet period takes a few extra seconds to wake up.

## Not yet built (follow-up work)

- Email verification on signup (password reset works once outgoing email is configured).
- TakwimuBridge QDA: team projects shared by several researchers, inter-coder
  reliability, and AI-suggested codes (the server can now hold an AI key safely).
- Content moderation / reporting workflow beyond deleting via Django admin.
