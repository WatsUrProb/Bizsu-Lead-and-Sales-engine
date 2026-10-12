# Bizsu Partner Workspace

A local hackathon prototype for finding potential Singapore aircon referral partners. Staff can inspect sourced company evidence, shortlist prospects, draft company-specific proposal emails, and track actual recruitment stages. The separate referral and sales demo contains fictional data.

**The 20 listed companies are prospects, not confirmed Bizsu partners.** Their public service information was reviewed on 11 Oct 2026 from the supplied `data/Bizsu_aircon_partner_prospects.pdf`. “Unverified” means the research did not establish the attribute. Published maintenance packages do not prove customer retention or partnership interest.

## Start locally

Use Node.js 22+ and Python 3.13. No LLM key or external service is required.

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm install
```

In separate terminals:

```bash
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
npm run dev -- --port 5173
```

Open **http://127.0.0.1:5173/**. Vite proxies `/api` to FastAPI. SQLite data is stored at `data/demo.db`. Set `BIZSU_DB_PATH` to a different local file to use a separate database. Existing databases are migrated in place; the seed import uses `INSERT OR IGNORE` and does not overwrite staff edits.

## 90-second demonstration

1. On **Discover**, search for a company such as **81Aircon**. Its card gives a short service summary and published-service fit.
2. Open the company. Inspect the source and unknowns in **Evidence and unknowns**. The score is a weighted business rubric, not a prediction of willingness to partner.
3. Click **Shortlist**. Go to **Pipeline** to see the card move to Shortlisted.
4. Open **Generate tailored email**. Change tone or partnership angle, generate a draft, edit a sentence, and save it.
5. Return to the profile or **Outreach drafts** to find the saved copy. It remains Shortlisted until someone explicitly confirms actual outreach.
6. In Pipeline, use **Move to…** to record later stages. Contacted and Onboarded each require explicit confirmation.

The email composer uses a deterministic template grounded in the selected record. It shows the generation method and facts used. It never sends an email. A potential referral commission is presented only as subject to discussion and agreement; installation collaboration requires technical approval.

## Data and design

- `data/partner_prospects.json` is the 20-company research snapshot transcribed from the supplied PDF. Each seeded company retains its source URL, review date, and unknowns.
- Staff can add and edit companies through the interface. Company, pipeline, event, settings, and draft records persist in SQLite.
- Fit starts with residential relevance 35%, recurring maintenance 30%, geographic coverage 20%, and installation 15%. Staff can edit and save weights that sum to 100%. Unverified attributes contribute no points.
- **Referral form** and **Sales flow** under **Separate demo** retain the earlier synthetic walkthrough. All referrals, enquiries and outcomes there are fictional scenarios; the real companies did not supply them.

## Checks

```bash
.venv/bin/python -m pytest -q
npm run build
```

The workspace tests cover 20-record import, company-specific generation, control changes, persistence, and stage confirmation. Existing demo tests remain in `tests/test_demo.py`.

This prototype has no authentication or outbound messaging and is not a live outreach system. Before operational use, Bizsu would need to confirm company willingness, product compatibility, consent, data handling, and measured pilot outcomes.
