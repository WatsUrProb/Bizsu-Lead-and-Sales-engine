# Bizsu Lead & Sales Engine

**Explore a potential residential sales channel, from partner referral to reviewed enquiry.**

This Hack and Hire prototype starts with real, sourced air-conditioning service company profiles. For each company, you can review evidence, shortlist it, open a demo referral form, and inspect a company-filtered sales pipeline. It is a **local product demo** of a proposed residential channel, not a live Bizsu service.

> **Real profiles, simulated results:** Company facts come from public sources. Every company referral, homeowner detail, visit, enquiry and sales outcome is simulated. Listed companies have no stated partnership with Bizsu. Use fictional `.test` email addresses when trying the form.

## What the product does

| Step | In the demo |
| --- | --- |
| **Choose a company** | Review three sourced AC service companies, check evidence, change ranking weights, shortlist a candidate and save an outreach draft locally. |
| **Try its demo referral** | Use that company’s simulated referral link to submit a fictional homeowner enquiry. The company association is a demo scenario only. |
| **Follow its pipeline** | Filter the sales dashboard by company to see simulated visits, enquiries, screening results, stage history, drafts and outcomes. |

The proposed journey is: **service partner → referral link → homeowner enquiry → screening → human sales review → assessment and quote**. Assessments, quotes and wins can be represented in the demo pipeline; no real appointment is booked and no message is sent.

## Try it locally

Use Node.js 22+ and Python 3.13. The tested versions were Node 22.23.3 and Python 3.13. The bundled demo runs without an account, paid API key or external service.

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm install
```

Start the API in one terminal:

```bash
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Start the web app in another:

```bash
npm run dev -- --port 5173
```

Open **http://127.0.0.1:5173/**. Vite forwards `/api` requests to the local FastAPI server. On first run, the API creates `data/demo.db` and seeds fictional partners and enquiries. To start with a separate database, set `BIZSU_DB_PATH` to a new local file before starting the API.

### Five-minute walkthrough

1. On **Companies**, choose an aircon company. Review its sources and the simulated enquiry count.
2. Click **Try demo form**. Use fictional details and a `.test` email address, then submit.
3. Click **View this pipeline**. The company filter shows the new enquiry alongside that company’s other simulated records.
4. Select the enquiry to inspect screening reasons, update its stage and save a follow-up draft. No message is sent.

## How it works

- **Background data:** A data pipeline joins published 2020 Census household tables by planning area. Five area-level shares feed a descriptive K-Means model. This research is retained in the repository but is outside the main product flow because it does not establish company coverage or referral demand.
- **Company discovery:** A frozen research snapshot records official company websites, documented services and public contact details. Each fact links to evidence. Unknown service coverage is marked **Unverified**. The default evidence score weights documented residential work (40), servicing and installation (30), a maintenance plan (20), and stated Singapore-wide coverage (10). Sliders let reviewers change these weights during a session. The score is a research aid, not a prediction of willingness to partner.
- **Company scenarios:** Four fictional referral links are assigned to the three sourced company profiles for demonstration. One company has two links. The assignment, visits, enquiries and outcomes are wholly synthetic; no real company supplied them. Company filters aggregate records across all links assigned to that scenario.
- **Enquiry screening:** Stated rules check demo coverage, AC configuration and completeness. A human would still need to confirm product fit and arrange any real assessment.
- **Conversion score:** A logistic-regression model demonstrates where ML could fit in a future workflow. It was trained and tested only on simulated outcomes. Its score is **not a validated purchase probability**.
- **Sales record:** FastAPI and SQLite store referral visits, enquiries, stage events and editable follow-up drafts. The React and Vite frontend calls the local API.

The API, frontend and data pipeline live in [`backend/`](backend/), [`frontend/`](frontend/) and [`pipeline/`](pipeline/). The company research snapshot and its retrieval date are in [`data/company_candidates.json`](data/company_candidates.json); it does not refresh automatically. Model assumptions and synthetic evaluation are recorded in [`data/models/conversion_card.json`](data/models/conversion_card.json).

## Data sources and interpretation

The frozen public data, observation years, retrieval dates and file hashes are listed in [`data/sources.json`](data/sources.json). The demo uses:

| Source | Used for |
| --- | --- |
| SingStat Census 2020 [dwelling](https://data.gov.sg/datasets/d_388f9c61f437a588b47b008a012d13fa/view), [household-size](https://data.gov.sg/datasets/d_0ef47f84a0776b27010b242038ea2c6b/view) and [income](https://data.gov.sg/datasets/d_4e150bbd35c3145ea43019212c7b46c2/view) tables | Planning-area household profiles and descriptive clusters. These are separate aggregates, not individual records or a joint household dataset. |
| [SingStat 2023 AC availability](https://data.gov.sg/datasets/d_abef8a7f050670891ad530620bad67cb/view) | A national figure used as a uniform assumption when generating synthetic records; it is not an area estimate. |
| [EMA 2013 electricity dataset](https://data.gov.sg/datasets/d_47db177174ba5899aa9cee08797d9171/view) | Historical whole-home electricity context shown for some areas. It is not current AC use and is excluded from clustering and savings estimates. |

Two named planning areas lack published cells needed for clustering and remain visible without a cluster label. The Census `Others` category is non-geographic and is excluded from the area view. Suppressed values stay missing rather than being treated as zero.

Refreshing the public source snapshots is optional and requires internet access:

```bash
.venv/bin/python -m pipeline.fetch_sources
.venv/bin/python -m pipeline.build_data
.venv/bin/python -m pipeline.train_models
```

This changes the checked-in data and model artifacts. The bundled snapshots are sufficient to run the demo offline.

## Development checks

```bash
.venv/bin/python -m pytest -q
npm run build
```

The tests cover data joins, suppressed values, cluster selection, sourced candidate actions, simulated company attribution and funnel totals, enquiry validation, screening, stage history and drafts.

## What a real pilot must establish

This prototype has no production authentication, privacy controls or outbound messaging. No real partner recruitment, homeowner contact, installation, residential savings measurement or Bizsu conversion validation has taken place. Before operational use, Bizsu would need to validate partner willingness, homeowner demand, product compatibility, assessment and installation economics, consent and data handling, and measured outcomes. The synthetic conversion model would need representative real pilot data and fresh evaluation.
