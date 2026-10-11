# Bizsu Hackathon — AI-Powered Lead Generation & Sales Engine

## Project context
This is a **student hackathon proof of concept and business proposal**, not a production deployment. We cannot recruit real partners, contact homeowners, perform installations, or validate energy savings in the field. Build a convincing, runnable demo using **synthetic homeowner and referral data** and clearly marked assumptions. The proposed residential expansion is a hypothesis to validate with Bizsu, not an established company strategy.

## One-line pitch
A partner-led homeowner acquisition platform that uses AI to discover relevant air-conditioning service partners, tracks their referrals, qualifies homeowner enquiries, and automates sales follow-up.

## Proposed funnel
Air-con servicing partner → unique QR/referral link → homeowner landing page → enquiry form → rule-based qualification → sales dashboard → assessment/quote → sale (simulated) → reporting.

## Recommended MVP (build in this order)

### 1. Partner discovery and ranking (main AI feature)
- Ingest a small **curated demo CSV/JSON dataset** of air-con servicing businesses. Do not scrape sites or invent real-world company facts.
- Store company name, service area, residential/commercial focus, services offered, public business contact fields if legitimately sourced, and source URL/notes.
- Provide a transparent weighted suitability score using configurable criteria, e.g. residential relevance 40%, service complementarity 30%, geographic coverage 20%, engagement fit 10%. These are illustrative weights, not learned predictions.
- Optionally use an LLM to extract structured attributes from supplied company descriptions, with a deterministic fallback and explicit indication of AI-generated assessments.
- Show a ranked partner table and explain each score.

### 2. Partner referral tracking
- Generate a unique referral code and link for each demo partner, e.g. `/home?ref=partner001`.
- Preserve referral attribution when a homeowner submits an enquiry.
- Provide a copy-link button and optionally render a QR code.

### 3. Homeowner landing page and qualification
- Explain the *proposed* assessment process without promising specific savings.
- Collect minimal fields: area, property type, AC system type, number of units, estimated usage, optional estimated AC electricity spending, and contact details.
- Obtain explicit consent for follow-up; for the demo use synthetic contact details only.
- Use configurable **rules** for initial qualification (service area, supported AC configuration, sufficient information). Do not conflate qualification with likelihood of purchase.
- Display a confirmation state and store the enquiry with its referral source.

### 4. Sales pipeline and dashboard
- Pipeline stages: `new → qualified → assessment_booked → assessed → quoted → won/lost`.
- Allow manual stage changes and show a history of updates.
- Dashboard metrics: active partners, referral visits (if tracked), submitted enquiries, qualified leads, assessments booked, won deals, and stage conversion rates. Handle zero denominators and small samples.
- Filter by partner and stage. Seed realistic-looking but **explicitly synthetic** records for the demo.

### 5. Follow-up automation (demo-safe)
- Generate editable draft follow-up messages based on enquiry details and pipeline stage.
- **Do not send actual emails or messages** by default. Provide a review/approve interface or mock delivery log.
- Optionally use an LLM for drafting with a template fallback.

## Optional extensions (only after MVP)
- **ML conversion scoring prototype:** Train a classifier (e.g. logistic regression, random forest, XGBoost) on *synthetic labelled leads* purely to demonstrate the future architecture. Label its scores **demo-only; not validated probabilities**, and do not use it to make real business claims. Prefer not to build this unless time permits.
- **Illustrative savings/payback calculator:** Use clearly editable assumptions and show the calculation, e.g. annual savings = estimated monthly AC electricity spend × assumed reduction × 12; payback years = installed price / annual savings. Do **not** claim residential performance or use commercial savings as proven residential outcomes. State that Bizsu must validate applicability, costs, and measurement methods.
- Partner analytics and exportable summary report.

## Suggested implementation stack
- Frontend: React + Vite (or Next.js if the repository already uses it).
- Backend: Python FastAPI (or existing backend if one is present).
- Storage: SQLite for a standalone demo; Supabase/PostgreSQL if already configured.
- AI: optional LLM API for company-description extraction and message drafting, with offline deterministic fallbacks.
- ML: scikit-learn only for optional synthetic-data demonstration.
- Charts: Recharts or existing chart library.

**Prefer the repository's existing framework and conventions over introducing a new stack.** The demo must work without API keys using seeded data.

## Suggested data model
- `partners`: id, name, description, area, customer_focus, services, source_notes, score, referral_code, created_at.
- `leads`: id, partner_id (nullable), area, property_type, ac_type, ac_units, daily_hours, estimated_ac_spend, contact_name, contact_email, consent, qualification_status, qualification_reasons, stage, created_at.
- `stage_events`: id, lead_id, from_stage, to_stage, timestamp.
- `followup_drafts`: id, lead_id, message, status, created_at.
- `referral_events` (optional): id, partner_id, timestamp, session_id; avoid storing unnecessary personal data.

## Suggested demo walkthrough
1. Open partner discovery and show ranked demo partners with score explanations.
2. Select a partner and copy its unique referral link.
3. Open the homeowner page through that link and submit a **synthetic** enquiry.
4. Show deterministic eligibility rules and referral attribution.
5. Open the sales dashboard, find the new lead, change its stage, and generate an editable follow-up draft.
6. Show partner attribution and funnel metrics updating.
7. Explain future validation requirements: partner willingness, homeowner demand, product compatibility, installation economics, and measured residential energy savings.

## Business proposal: claims and metrics
- Frame the product as a **hypothesis for a scalable customer acquisition channel**, not an already-proven engine.
- Illustrative funnel assumptions may be shown but must be labelled hypothetical, never forecasts.
- Measure active partners, referred visits, enquiries, qualified enquiries, booked assessments, conversions, and cost per acquired customer once real pilots exist.
- Explicitly distinguish AI extraction, rule-based eligibility, and genuine ML predictions.
- Include consent, privacy, data provenance, and human review for outreach.

## Codex implementation instructions
1. Inspect the current repository and report its framework, scripts, and structure.
2. Propose a small implementation plan and file changes before coding.
3. Implement the MVP end-to-end, prioritising a polished demo flow over speculative features.
4. Seed synthetic partner and homeowner records. Mark all demo figures and outcomes as synthetic.
5. Avoid real scraping, real outbound messages, unsupported energy-saving claims, and dependencies on paid APIs.
6. Add input validation, graceful empty states, loading/error states, and basic tests for referral attribution, eligibility rules, and pipeline transitions.
7. Add a README with exact install/run commands, environment variables (if any), architecture, demo steps, limitations, and next steps.
8. After implementation, run the available checks/tests and summarize what works, what is mocked, and what remains.

## Acceptance criteria
- A reviewer can run the demo locally without credentials.
- A partner can be selected and a referral link generated.
- A homeowner enquiry submitted through that link appears in the dashboard with correct attribution.
- Qualification reasons are visible and understandable.
- Stage changes and draft follow-ups work without contacting real people.
- Dashboard metrics update consistently.
- AI features degrade gracefully if no model/API is configured.
- No screen presents synthetic ML outputs, projected savings, or sample conversion rates as validated Bizsu results.
