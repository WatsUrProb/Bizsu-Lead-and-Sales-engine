# Bizsu growth lab — student hackathon demo

For Hack and Hire.

A local proof of concept for a **proposed** partner-led residential enquiry channel. It combines real Singapore **planning-area aggregate statistics** with fictional partner, homeowner and sales records. It does not represent an existing Bizsu residential programme, observed conversion performance or measured energy savings.

## Run locally

Requires Node.js 22+ and Python 3.13 (the tested versions were Node 22.23.3 and Python 3.13). No account, paid API key or external service is needed to run the bundled demo.

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm install
```

Start the backend in one terminal:

```bash
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Start the frontend in another:

```bash
npm run dev -- --port 5173
```

Open **http://127.0.0.1:5173/**. The Vite development server proxies `/api` to the local FastAPI server. The backend creates `data/demo.db` and seeds fictional partners and enquiries on first run. To use a fresh separate database, set `BIZSU_DB_PATH` to a new local file before starting the backend. The app is intended for local use only; it has no login or production privacy controls.

## Demo walkthrough

1. **Market:** inspect the 2020 planning-area clusters, housing counts, source links and descriptive filters. Open a selected area's historical 2013 electricity context.
2. **Partners:** inspect a fictional partner's weighted score and copy its unique referral link.
3. **Homeowner:** open that link, fill the form using a `.test` email address, consent to **simulated** follow-up and submit.
4. **Sales:** find the attributed enquiry, read the rule-based screening reasons and unvalidated synthetic ML score, move it to an allowed stage and save an editable follow-up draft. No message is sent.
5. Return to the dashboard to see enquiry and referral metrics update.

## Data provenance and level

The exact source URLs, observation years, source update dates, retrieval timestamp and snapshot SHA-256 hashes are in [`data/sources.json`](data/sources.json). The frozen JSON snapshots allow offline use. Each Census table has 31 rows after excluding its national `Total` row; one of the 31 is the non-geographic `Others` row. The tables were joined **only on planning-area name and Census year**. Counts and shares remain area aggregates.

| Snapshot | Observation | Content and limit |
| --- | --- | --- |
| [SingStat dwelling type](https://data.gov.sg/datasets/d_388f9c61f437a588b47b008a012d13fa/view) | Census 2020; source updated 18 Jun 2021 | Household counts by planning area and dwelling type. Suppressed cells are missing, never zero. |
| [SingStat household size](https://data.gov.sg/datasets/d_0ef47f84a0776b27010b242038ea2c6b/view) | Census 2020; source updated 28 Jul 2022 | Separate area-level size counts; no dwelling-size cross-tabulation. |
| [SingStat income bands](https://data.gov.sg/datasets/d_4e150bbd35c3145ea43019212c7b46c2/view) | Census 2020; table updated 30 Jun 2026 | Separate area-level income counts with an updated income definition. No individual income is inferred. |
| [SingStat AC availability](https://data.gov.sg/datasets/d_abef8a7f050670891ad530620bad67cb/view) | 2023; source updated 28 Nov 2024 | National 81.9% ownership/availability figure. It has no area or dwelling-type breakdown. |
| [EMA historical electricity](https://data.gov.sg/datasets/d_47db177174ba5899aa9cee08797d9171/view) | **2013**; portal refreshed 24 Jun 2026 | Planning-area average monthly **whole-home** kWh. Used as explicitly historical context only, never in clustering or savings estimates. |

EMA's [current Singapore Energy Statistics Chapter 3](https://www.ema.gov.sg/resources/singapore-energy-statistics/chapter3) publishes newer electricity context and links to downloadable workbooks. The source page was reviewed, but automated retrieval of the current workbook was blocked; its exact columns and join quality were therefore **not verified**, and it was not integrated. The 2026 portal refresh of the 2013 GeoJSON does not change its observation year. HDB's [dwelling units by town and flat type](https://data.gov.sg/datasets/d_07b1eeeb22efdf7faf5bd6a13667359d/view) was assessed but not joined: HDB town units and Census planning-area resident households have different geographies, measures and dates.

Public source refresh is optional and needs internet access:

```bash
.venv/bin/python -m pipeline.fetch_sources
.venv/bin/python -m pipeline.build_data
.venv/bin/python -m pipeline.train_models
```

The refresh script uses the public [data.gov.sg dataset APIs](https://guide.data.gov.sg/developer-guide/dataset-apis) without a key and respects low unauthenticated rate limits. It changes the frozen snapshots and model artifacts; run it only when you intend to update the demo's data basis.

## Architecture and model methods

| Layer | Implementation |
| --- | --- |
| Data pipeline | `pipeline/fetch_sources.py` freezes public data with hashes; `build_data.py` validates common planning-area keys and totals, preserves missing cells, and creates aggregate profiles. |
| Segmentation | `train_models.py` uses five observed area-level shares: HDB, 4/5-room HDB, condo/apartment, 4+ person households, and $10k+ work-income households. It standardises them, evaluates K-Means `k=2,3,4` with silhouette, repeated 80% subsample adjusted Rand stability and minimum group size, and selects the strongest configuration. Labels come from observed relative centroid features. |
| Synthetic data | Geographic and dwelling frequencies follow Census counts for the 28 cluster-eligible areas. Household size is drawn separately within area. AC ownership uses the national 2023 figure uniformly **as an assumption**. AC units, system type, usage, enquiry selection and conversion mechanisms are simulated. No missing observed record is invented. |
| Conversion model | scikit-learn logistic regression uses property type, AC type, number of units and daily hours. Its 75/25 stratified held-out evaluation is on **synthetic outcomes only**. Scores shown to users are unvalidated demonstrations, not real purchase probabilities. Assumptions and test metrics are in `data/models/conversion_card.json`. |
| API and persistence | FastAPI owns ranking, qualification, inference, pipeline transitions and metrics. SQLite stores partners, leads, stage history, anonymous referral visits and editable drafts. `BIZSU_DB_PATH` can change the local DB file. |
| Frontend | React + Vite provides Market, Partners, Homeowner and Sales screens. It uses only local API calls. |

Two named areas have suppressed Census cells required for the five features and are displayed without cluster labels. `Others` is not a planning area. The selected two-cluster solution is **descriptive**, based on just 28 geographic areas; it is not evidence of commercial opportunity or household behaviour. Electricity is excluded from K-Means because the verified local area source is from 2013.

Partner scores are illustrative weighted sums: residential relevance 40%, service complementarity 30%, geographic coverage 20%, and fictional engagement fit 10%. Homeowner screening checks the assumed demo coverage, split or multi-split AC configuration, number of units and usage information. Neither is a validated prediction. Draft follow-ups are templates with a human review step and no sending integration.

## Checks

```bash
.venv/bin/python -m pytest -q
npm run build
```

The tests cover Census join integrity and suppressed values, candidate cluster configurations, referral attribution and deduplication, synthetic-only contact validation, qualification, pipeline transition history, draft editing and dashboard updates.

## Limitations and next validation

- No real partner recruitment, homeowner contact, field installation, residential savings measurement or Bizsu conversion evidence occurred.
- Census 2020 area profiles cannot be used as individual household records. The 2013 EMA reference is historical and is not AC-specific.
- Synthetic model performance measures only agreement with an invented outcome generator. The model should be retrained and evaluated on consented, representative pilot outcomes before any operational use.
- Partner willingness, homeowner demand, compatibility, unit economics and measurable energy impact require a real pilot. The demo has no production authentication, privacy retention policy or outbound messaging.
