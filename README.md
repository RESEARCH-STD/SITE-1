# Sustainable Solutions Tanzania (SST)

The website for Sustainable Solutions Tanzania: About, Services, Products, Projects,
Insights & Opportunities, and Partners, built around **TakwimuBridge**, a Django app
where students create accounts, upload their own socio-economic research datasets,
and search/download datasets shared by other students.

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
accounts/           Custom User model (extends AbstractUser with `institution`), signup/login
datasets/           Category & Dataset models; TakwimuBridge's catalog search/filter, upload, download, "My Uploads"
core/                Home, About Us, Services, Products, Projects, Insights & Opportunities, Partners, Data Custodians, Guidelines & FAQ, Contact
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

- Email verification on signup.
- Content moderation / reporting workflow beyond deleting via Django admin.
