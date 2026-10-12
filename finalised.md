# Bizsu Partner Discovery & Acquisition Prototype — Implementation Specification

## Objective and scope
Build a working Bizsu prototype that allows staff to browse real Singapore air-conditioning servicing **prospects**, evaluate their fit as potential referral partners, generate **company-specific partnership proposal emails**, and track recruitment through a **Kanban-style pipeline**. Prioritise partner acquisition over residential market-intelligence charts. This is a hackathon demonstration, not an operational outreach campaign.

## Confirmed product decisions
1. **Allow manual company creation and editing.** Seed the initial dataset from the provided `Bizsu_aircon_partner_prospects.pdf` (20 researched companies). Bizsu staff must be able to add new prospects, edit details, and record evidence without editing source code.
2. **Lead with a referral partnership proposal**, rather than a generic collaboration. Describe referral commissions only as a *possible incentive subject to discussion and agreement*. Never imply a commission rate, existing partnership, guaranteed energy savings, or residential product compatibility has been confirmed.
3. Use a **Kanban-style partner acquisition interface**, with clickable cards and accessible non-drag controls for changing stages.
4. Include **email personalisation controls** for email purpose, tone, and partnership incentive, plus editable generated drafts.
5. Use real, publicly sourced company information for discovery; use explicitly labelled fictional/demo data for onboarding, homeowner enquiries, conversions and performance metrics. Do not imply the 20 real prospects are Bizsu partners.

## 1. Screens and user journeys

### A. Partner Discovery (default landing page)
- Search by company name and filter by residential servicing, recurring maintenance, installation capability, geographic coverage, and pipeline stage.
- Sort by name and transparent suitability score.
- Each company row/card shows name, key service evidence, maintenance offering, coverage, score, evidence status, and **View / Shortlist** actions.
- **Add Company** form allows manual entry of name, website, description/residential evidence, recurring maintenance details, installation capability, coverage, public business contact method, source URL, retrieval date, and unknowns. Validate required fields and URLs.
- Allow staff to edit an existing company and mark uncertain attributes **Unverified**. Preserve evidence URLs and retrieval dates.
- Show a clear banner: **“Prospective companies only — no partnership is implied.”**

### B. Company Profile & Suitability
- Show the researched fields, evidence links, retrieval dates, unknowns, and current pipeline stage.
- Explain suitability as a **weighted business rubric**, not an ML prediction. Example configurable starting weights: residential relevance 35%, recurring maintenance 30%, geographic coverage 20%, installation capability 15%.
- Display criterion-level contributions and reasons. Treat unknown attributes as **Unverified**, not as verified negatives; display missing-evidence warnings. Make weights editable and recalculate scores consistently.
- Provide **Shortlist**, **Generate Email**, **Edit Company**, and **View in Pipeline** actions.

### C. Company-Specific Email Composer
- Generate a tailored Bizsu referral-partnership pitch grounded only in the selected company's verified/researched attributes.
- **Personalisation controls:**
  - **Email purpose:** Initial partnership proposal / Follow-up / Meeting request.
  - **Tone:** Professional / Friendly / Concise.
  - **Partnership angle:** Potential referral commission (terms to be agreed) / Additional value to existing customers / Potential installation collaboration (subject to technical approval).
  - Optional editable call-to-action or notes, if straightforward.
- Display an editable **subject** and **body**; allow **Generate**, **Regenerate**, **Save Draft**, **Copy**, and **Open in Email App** (mailto where practical). Do not send emails automatically.
- Personalise with specific supported details (e.g., quarterly maintenance, HDB/condo servicing), not generic flattery. Avoid invented customer counts, partnership willingness, unverified service areas, specific commission rates, and guaranteed energy savings.
- Store the generation settings and the edited draft. If an LLM API key is unavailable, use a deterministic company-aware template so the demo works offline.
- Generating/saving a draft **must not** automatically mark a company as Contacted.

### D. Kanban Partnership Pipeline
- Columns: **Discovered → Shortlisted → Contacted → Interested → Negotiating → Onboarded**, plus **Rejected / Archived** as a separate outcome lane or filter.
- Each card shows company name, suitability score, last activity, follow-up due date (if set), and a short next action.
- Clicking a card opens the company profile and associated email drafts/notes.
- Support drag-and-drop if feasible, **and** a stage dropdown/buttons for accessibility and reliability.
- Permit staff to record notes, contact date, follow-up date, and reason for rejection.
- **Only mark Contacted after the user explicitly confirms actual outreach**; generating or copying an email is not proof of sending.
- **Only mark Onboarded after explicit confirmation of an agreement.** For hackathon end-to-end demonstrations, use a clearly labelled **fictional demo partner**; keep real prospects unconfirmed.
- Persist all stage changes and display stage history where practical.

### E. Referral & Sales Demo (subsequent milestone)
- Onboarded **demo** partner receives a unique referral code, shareable link, and QR code.
- Homeowner demo enquiry form validates fields and stores the referral source.
- Demonstrate qualification, stage updates, and dashboard metrics using **synthetic data** labelled as such.
- Do not claim actual referrals, conversions, or commission payments.

## 2. Data model (SQLite; adapt to existing repo conventions)

### `companies`
`id`, `name`, `website`, `residential_evidence`, `recurring_maintenance_details`, `installation_capability` (yes/no/unverified), `geographic_coverage`, `public_contact_channel`, `contact_url`, `source_url`, `retrieval_date`, `unknowns`, `is_demo`, `created_at`, `updated_at`.

### `company_assessments` (or derived values)
`company_id`, structured feature values, verification states, criterion-level evidence, calculated suitability score, scoring configuration version. Do not overwrite raw research notes when changing a score.

### `scoring_config`
Weights for residential relevance, recurring maintenance, geographic coverage and installation capability; enforce non-negative weights and normalise to 100%.

### `partner_pipeline`
`company_id`, `stage`, `last_contacted_at`, `next_follow_up_at`, `notes`, `updated_at`.

### `pipeline_events`
`id`, `company_id`, `from_stage`, `to_stage`, `occurred_at`, `note`.

### `outreach_drafts`
`id`, `company_id`, `purpose`, `tone`, `partnership_angle`, `subject`, `body`, `generation_method`, `draft_status`, `created_at`, `updated_at`.

### Later: `partners`, `referrals`, `leads`, `lead_stage_events`
Implement when referral-demo milestone begins; do not block partner discovery on these tables.

## 3. Suggested implementation order
1. Inspect existing React/Vite + FastAPI + SQLite project and reuse functioning components. Keep the current site runnable.
2. Import the 20 PDF prospects with accurate source references; provide manual Add/Edit Company forms.
3. Build searchable/filterable Partner Discovery and detailed Company Profile.
4. Implement explainable, editable weighted scoring and missing-evidence handling.
5. Implement company-specific email composer with personalisation controls, editable saved drafts, and template fallback.
6. Build persistent Kanban pipeline, explicit stage transitions, notes, and follow-ups.
7. Add a **fictional** onboarded partner and demonstrate referral link → enquiry → sales metrics as a separate milestone.
8. Add loading/empty/error states, seed/reset demo instructions, README, and smoke tests.

## 4. Demo acceptance criteria
- A reviewer can search the 20 real researched companies and open a profile with source evidence.
- A reviewer can **add a new company manually**, save it, refresh, and still find it.
- A reviewer can change scoring weights and see rankings and score explanations update.
- Selecting two different companies generates **meaningfully different, evidence-grounded emails**.
- Email purpose, tone, and partnership angle controls change the draft; subject/body remain editable and savable.
- A saved draft does **not** mark a company Contacted.
- A reviewer can move a prospect from Discovered to Shortlisted, explicitly mark Contacted, and see the card move on the Kanban board after refresh.
- Real prospects remain clearly labelled **not confirmed Bizsu partners**; only fictional/demo partner is used for simulated onboarding and referrals.
- Prototype can run locally without an LLM API key, and README contains exact start commands.

## Research input
Source: `Bizsu_aircon_partner_prospects.pdf` (20 company-operated websites researched on 11 Oct 2026). Preserve the PDF's distinctions between confirmed website evidence, unknowns and unverified attributes. Published maintenance packages do not establish customer retention, and no prospect's willingness to partner has been verified.

## 5. UI/UX direction — engaging, intuitive, action-first (high priority)

### Core design principle
**Build a partner-acquisition workspace, not a statistics dashboard.** The first thing a Bizsu user should understand is **which company to approach, why it is relevant, and what action to take next**. Keep numerical analytics secondary and available on demand. Avoid walls of charts, dense tables, unexplained scores, and decorative AI claims.

### Navigation and information architecture
- Primary navigation: **Discover**, **Pipeline**, **Outreach Drafts**. Put **Referral Demo** in a separate clearly labelled demo section when implemented.
- Default landing view: **Discover** with a short action-oriented heading (e.g., “Find your next referral partner”), a prominent search box, 3–4 useful filter chips, and a curated shortlist of prospect cards.
- Keep a consistent **Add Company** action accessible from Discover.
- Use progressive disclosure: summary on cards → company details in a side panel or focused detail page → full evidence and scoring breakdown in expandable sections.
- Do not add a separate analytics homepage merely to fill space. If summary indicators help, show at most three lightweight operational counts (e.g., Prospects, Shortlisted, Follow-ups due), not multiple charts.

### Discover experience
- Prefer **scannable company cards** or a compact card/list toggle over a wide, spreadsheet-like table. Each card should contain:
  1. Company name and **Prospect / Unverified** status.
  2. One-sentence evidence-backed reason to consider it (e.g., “Residential HDB/condo servicing with quarterly maintenance”).
  3. Two or three concise tags: **Residential**, **Recurring maintenance**, **Installation**; show **Unverified** explicitly when needed.
  4. Suitability indicator with plain-language label (e.g., “Strong match — based on published services”) and a **Why this match?** affordance.
  5. Clear primary action: **View company** or **Shortlist**.
- Support instant search, filters, sorting, and a visible **Clear filters** action. Display results count without overwhelming users.
- If there are no matching companies, explain why and offer to reset filters or add a company.
- Do not equate a high score with confirmed partnership interest.

### Company detail: guide the next action
- Use a clear visual hierarchy:
  1. **Company summary** (who they serve, what they offer, contact channel).
  2. **Why Bizsu might approach them** (2–3 evidence-backed bullets).
  3. **Recommended next action** (e.g., “Shortlist” or “Draft proposal email”).
  4. **Evidence and unknowns** (expandable; source URLs and research dates preserved).
  5. **Suitability breakdown** (expandable; editable weights via a clearly named settings control).
- Put **Generate tailored email** near the main call-to-action rather than burying it among technical details.
- Use clear distinction between **Verified from source**, **Unverified**, **Demo**, and **User-entered** data. Never use colour alone to communicate these states.
- Provide brief contextual help explaining that the suitability score is a transparent business rubric, **not a machine-learning prediction**.

### AI email composer: make it the “aha” moment
- Open as a focused workspace or two-column layout on wide screens, stacked on mobile:
  - **Left: Personalise** — purpose, tone, partnership angle, optional notes/CTA, and a small **Company facts used** panel.
  - **Right: Your draft** — editable subject and email body with clear actions.
- Keep controls lightweight: segmented controls or simple dropdowns; sensible defaults of **Initial proposal**, **Professional**, and **Referral partnership / potential commission subject to agreement**.
- Primary action: **Generate tailored email**. Secondary actions: **Regenerate**, **Save draft**, **Copy**, **Open in email app**. Show a visible success message after save/copy.
- Make the draft genuinely company-specific: use 1–2 researched service details and explain why they matter to the referral proposal. When a fact is unverified, omit it rather than inventing it.
- Display a compact **“Personalised using”** list of the specific facts referenced in the email, with links to supporting evidence where available.
- Offer a preview of the generated subject/body before copying; preserve user edits unless they explicitly regenerate or reset.
- If AI is unavailable, label the output **Template-generated** rather than presenting it as LLM-generated. The fallback must still incorporate company-specific verified facts.
- **Never auto-send**; generating, copying, saving or opening an email does not mark the prospect as Contacted. Only explicit user confirmation does.

### Kanban pipeline: intuitive and interactive
- Make the board feel like a **working deal tracker**, not a static chart.
- Use the agreed columns: **Discovered**, **Shortlisted**, **Contacted**, **Interested**, **Negotiating**, **Onboarded**; provide **Rejected / Archived** as a separate view or filter.
- Each card should show only: company name, one-line reason/next step, compact fit label, and follow-up indicator if applicable. Avoid repeating every company attribute on the board.
- Enable drag-and-drop where practical **plus a visible “Move to…” control** for keyboard, touch, and reliability.
- Clicking a card opens a detail panel with **Draft email**, **Add note**, **Set follow-up**, and **Change stage**.
- Stage transitions should give immediate visual feedback and persist after refresh; provide a lightweight confirmation for **Contacted** and **Onboarded** to avoid misleading status claims.
- Display a subtle per-column count; avoid charts for pipeline totals. Highlight **follow-ups due** as actionable items rather than red-number overload.
- Use an empty-column state with useful guidance (e.g., “Shortlist a company from Discover”).
- For real prospects, do not simulate that outreach happened. Any fictional walkthrough should be clearly marked **Demo**.

### Visual style and interaction quality
- Aim for a polished, modern **B2B SaaS workspace**: calm neutral surfaces, generous spacing, consistent typography, restrained Bizsu-inspired accent colour, meaningful icons, and clear primary buttons.
- Use cards, badges, short descriptions, and visual hierarchy to help scanning; do not use excessive gradients, animations, oversized hero graphics, or meaningless KPI tiles.
- Add subtle microinteractions for shortlist, save, stage movement, and email generation; keep animations brief and respect reduced-motion settings.
- Make it responsive: desktop board can scroll horizontally within the board area; mobile gets a stage-filtered list or stacked columns, without whole-page horizontal overflow.
- Use accessible labels, visible focus states, sufficient contrast, readable type, and a non-drag way to move Kanban cards.
- Every interaction must work: buttons should have meaningful actions; use loading skeletons/spinners for asynchronous requests, clear error recovery, confirmation for destructive actions, and useful empty states.

### Suggested 90-second demonstration flow
1. Open **Discover**: search for a real researched company and show its concise fit summary.
2. Open its profile: reveal **why it is relevant** and inspect one evidence link / unknown.
3. **Shortlist** it: show the card appear in the **Kanban** Shortlisted column.
4. Click **Generate tailored email**: change **Tone** or **Partnership angle**, generate a visibly company-specific draft, edit one sentence, and **Save draft**.
5. Return to Kanban: show the draft attached to the prospect; explain that **Contacted** requires explicit confirmation.
6. Optionally switch to the separately labelled fictional partner to demonstrate later-stage onboarding/referrals.

### UX acceptance criteria (must pass)
- Within 10 seconds, a first-time reviewer can identify the primary workflow and the next action without a tutorial.
- A reviewer can search, inspect evidence, shortlist, generate/edit/save an email, and locate the saved draft in **five or fewer major navigation steps** (excluding text entry).
- Two different companies yield meaningfully different evidence-grounded emails; changing purpose/tone/angle visibly changes the content.
- No screen is dominated by charts or unexplained statistics. Numbers support decisions; **actions lead**.
- Kanban stage updates and saved drafts persist across refresh; mobile users can perform all actions without dragging.
- Real prospects are never presented as existing Bizsu partners; unknown data is visibly unverified; simulated outcomes are clearly marked.

## 6. Implementation note for Codex
Treat Section 5 as **product requirements, not optional visual polish**. Before coding, inspect the current frontend and propose a compact screen map and component plan. Reuse functioning infrastructure; refactor cluttered dashboards rather than stacking new widgets on top. Implement and verify the complete **Discover → Profile → Shortlist → Generate/Save Email → Kanban** journey before adding extra analytics, residential charts, or advanced ML. Prioritise a polished end-to-end interaction over the number of features.


## 7. Visual references and final design requirements
The user supplied two visual references. Treat them as **design inspiration, not dashboard content to copy**:

- **Reference A (gradient analytics cards):** soft lavender/peach accents, polished typography, rounded corners, careful spacing and restrained depth. Do **not** replicate the cryptocurrency metrics, oversized gauges or doughnut charts.
- **Reference B (project-management workspace):** compact icon/sidebar navigation, pill filters, clean off-white canvas, white rounded panels, simple card hierarchy and immediately visible actions. Adapt this layout to Bizsu partner discovery and Kanban management.

### Suggested visual tokens (starting points, not hard constraints)
- App background `#F5F6FA`; card background `#FFFFFF`; main text `#182033`.
- Indigo accent `#6258E8`; pale lavender `#EAE7FF`; soft peach `#FFD7C2`; soft mint `#D9F5E5`.
- Rounded cards roughly 16–24 px, consistent 8-point spacing, readable text, light borders and subtle shadows.
- Use gradient emphasis on **one** featured call-to-action or summary surface at a time. Never rely on colour alone to communicate stage or verification status.
- Use icons with labels, visible focus rings, accessible contrast and reduced-motion support.

### Interaction design details
- **Discover:** quick search, pill filters, responsive cards, compact fit explanation and direct Shortlist/Generate Email actions. Keep full evidence one click away.
- **Company detail:** a clear header with company name, prospect disclaimer and next best action; show evidence-backed facts first, then collapsible unknowns and scoring breakdown.
- **AI Outreach:** two-column desktop layout (personalisation controls left; editable draft preview right); stack vertically on mobile. Display *Facts used to personalise* and warn when a claim is unverified. Provide loading, regenerate, save, copy and error states.
- **Kanban:** compact cards grouped by stage, horizontal scroll **inside** the board on desktop; stage-select list on small screens. Show stage count and next action, not charts. Allow opening the email composer from any card.
- **Notifications:** non-intrusive confirmation after shortlist, draft save and stage change; preserve inputs when an API call fails.

## 8. AI email-generation contract (engineering requirement)
1. On Generate, frontend sends company ID, email purpose, tone, partnership angle and optional custom instructions to FastAPI.
2. Backend fetches the current company record and its evidence; never trust user-supplied company claims as verified facts.
3. If an LLM provider is configured, request structured output containing `subject`, `body`, `facts_used` and `generation_method`. Validate and handle malformed responses.
4. If the LLM is unavailable, produce a **company-aware deterministic template** using the same controls. Show the method used; do not label templates as AI-generated.
5. Only cite published company attributes that exist in the record. Do not infer company size, number of customers, willingness to partner, guaranteed savings, referral fees or Bizsu product compatibility.
6. Keep the default proposal focused on a **potential referral partnership**. Present commissions only as optional, subject to mutually agreed terms. Installation collaboration is speculative and requires technical approval.
7. The generated email must remain editable. Save the edited subject/body and control selections; regenerating should warn before overwriting unsaved edits.
8. **Never send emails automatically.** Copy/open-email are user-initiated actions. Marking Contacted requires separate explicit confirmation; merely generating, saving or copying a draft does not count.
9. Include at least two deterministic tests: different companies produce distinct personalised content, and changing purpose/tone/angle changes the output.

## 9. Scope guardrails and final handoff checklist
- **Build now:** real-prospect import, manual add/edit, Discover, evidence-based profiles, explainable scoring, AI/template email composer, persistent Kanban pipeline.
- **Build later:** demo-only referral links, homeowner enquiries and sales pipeline. **Defer:** residential market intelligence, K-Means, synthetic conversion ML and decorative analytics.
- Real company records are **unconfirmed prospects**; use a separately labelled fictional partner for any simulated onboarding or sales activity.
- Existing local app should remain runnable. Inspect repository before editing, reuse working code, document migrations/seed behaviour, and avoid destructive resets of user edits.
- Provide exact startup instructions, environment variable examples without secrets, a small test suite and a repeatable 90-second demonstration script.
- Final implementation should pass this journey end to end: **Find a real company → inspect evidence → shortlist → generate a company-specific referral email → edit and save → locate draft from Kanban → update status explicitly → refresh and verify persistence.**
