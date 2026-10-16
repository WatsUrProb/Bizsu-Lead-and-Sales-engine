# Bizsu Partner and Customer Pipeline

A prototype for researching Singapore air-conditioning servicing partners, preparing reviewable outreach, and following attributed homeowner enquiries. Company profiles come from public research. Referral partners, visits, enquiry outcomes, and any walkthrough figures are simulated; no listed company has agreed to partner with Bizsu.

The prototype does not send email or book appointments. Staff review and send drafts outside the app.

## Screenshots

Captured from the local prototype on 16 October 2026. The customer pipeline is empty after the sample-enquiry reset; the company list is research for prospective partners, not a list of confirmed Bizsu partners.

### Partner discovery

![Bizsu partner discovery screen with a search field, filters, and prospective company list](docs/screenshots/partner-discovery.png)

Start here to find potential servicing partners. Search or filter the company list, then open a profile to check its sources before drafting an introduction. The sidebar keeps partner work and customer enquiries easy to reach.

### Homeowner enquiry form

![Bizsu homeowner form showing housing, planning area, and air-conditioning questions](docs/screenshots/homeowner-form.png)

Homeowners first share a few details about their home and air-conditioning system. Step two collects contact information so Bizsu can review the enquiry. The referral source indicates whether they arrived directly or through a partner link.

### Customer pipeline

![Bizsu customer pipeline showing zero enquiries, follow-ups, and pending assessments](docs/screenshots/customer-pipeline-empty.png)

The pipeline starts empty after the sample-enquiry reset. As enquiries arrive, the cards show what needs attention, while search and filters help staff find a customer and track the next step.

## Tech stack

| Layer | Technology | Role |
| --- | --- | --- |
| Frontend | React 19, Vite 7, CSS | Partner workspace, homeowner form, and customer pipeline |
| API | Python 3.13, FastAPI, Uvicorn | Enquiry handling, partner research, outreach drafts, and pipeline updates |
| Data | SQLite locally; Supabase PostgreSQL via psycopg when `DATABASE_URL` is set | Stores enquiries, referral activity, drafts, and sales history |
| Hosting | Vercel configuration | Builds the frontend and serves FastAPI through a Python Function |
| Optional features | Exported JSON model and OpenAI API | Synthetic conversion scoring and assisted outreach drafting; the app can run without an OpenAI key |

The Supabase and Vercel integration is configured in the repository; a live deployment still needs project credentials and environment variables.

## Watch the walkthrough

[Watch the 2:56 Bizsu pitch walkthrough](public/videos/bizsu-client-pitch.mp4). It was recorded on 15 October 2026 with illustrative enquiries and an earlier interface. The current app starts with an empty customer pipeline.

## Run locally

Use Node.js 22+ and Python 3.13. Install dependencies:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
npm ci
```

Start FastAPI and Vite in separate terminals:

```bash
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
npm run dev -- --port 5173
```

Open <http://127.0.0.1:5173/>. The API creates an ignored `data/demo.db` on first run. It seeds fictional referral sources and a research snapshot of potential partner companies, **but no sample enquiries**. Submit fictional contact details through `/demo/form` to try the customer pipeline. Saved drafts remain manual; nothing is sent.

Vercel installs only `requirements.txt`. The synthetic conversion model runs from the small exported `data/models/conversion_model.json`; scikit-learn, NumPy, SciPy and joblib are needed only to retrain it with `python -m pipeline.train_models` after installing `requirements-dev.txt`.

The local database is not committed. To reset an existing local demo, back it up and clear `leads`, `stage_events`, `lead_activity`, `followup_drafts`, and `referral_events`. The current local copy was reset before this release. The `seed_enquiries=True` option exists only for explicit test and presentation fixtures.

## Deploy to Vercel with Supabase

The frontend is a Vite app; `api/index.py` exposes FastAPI as a Vercel Python Function. The catch-all rewrite in `vercel.json` supports direct links to the SPA routes. The deployment build enables the staff workspace and shows a staff-key prompt before it loads.

1. Create a Supabase project in an appropriate region. Copy its **Transaction pooler** connection URI from **Connect**. Use the URI as the Vercel `DATABASE_URL` environment variable. The server connects over TLS; never use a browser-visible `VITE_` variable for this credential.
2. Generate a long random value and set it as `BIZSU_ADMIN_KEY` in Vercel. Share it only with staff who may view enquiry contact details. The key is checked by the API and kept in browser session storage for the current tab. Leave `BIZSU_PUBLIC_FORM` unset or `0` for a staff-only demo.
3. Import this repository into Vercel with the root directory set to the repository root. The committed `vercel.json` builds the frontend and routes `/api/*` to FastAPI. Pin Python 3.13 using `.python-version`.
4. Deploy a preview first. Check `/api/health`, unlock the workspace, verify the empty enquiry list, submit a fictional enquiry, refresh, and confirm that it remains. Review access before promoting to production.

The first API startup creates the required tables in Supabase Postgres and seeds only fictional referral sources and sourced company profiles. All mutable workspace records, including enquiries, drafts and stage history, use the same Supabase database when `DATABASE_URL` is set. Vercel's temporary filesystem is never used for customer records.

For a public homeowner form, set **both** `BIZSU_PUBLIC_FORM=1` and `VITE_PUBLIC_FORM=true` in Vercel and redeploy. Do this only after Bizsu has reviewed its privacy notice, consent text, retention policy, and anti-abuse controls for real enquiries. The public form does not grant access to saved enquiries; staff access still requires the key.

The current project has no Supabase credentials in Git. Do not commit `.env` files or connection strings.

## Checks

```bash
.venv/bin/python -m pytest -q
npm test
npm run build
```

The source data, dates, and caveats are recorded in [data/sources.json](data/sources.json), [data/company_candidates.json](data/company_candidates.json), and [PROJECT-KNOWLEDGE.md](PROJECT-KNOWLEDGE.md). The conversion model is trained only on synthetic examples and is not a validated sales prediction.
