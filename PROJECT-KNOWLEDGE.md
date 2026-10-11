# Bizsu project knowledge

## Current checkpoint

Local student hackathon proof of concept implemented from [`Bizsutext.md`](Bizsutext.md) and the user's approved architecture and refinements. No Codex Page link was supplied; this local file records the working context. Prototype location: this directory. The application has not been validated with actual partners or homeowners.

## Intent and scope

Proposed Singapore residential acquisition funnel: fictional AC service partner → unique referral link → synthetic homeowner enquiry → rule-based screening → human-managed pipeline → editable, unsent follow-up. Market dashboard describes Census planning areas; conversion ML is trained only on simulated outcomes. No real outreach, energy-saving claim or paid API dependency.

## Actual sources and methods

Official SingStat Census 2020 dwelling, household-size and income tables were downloaded through data.gov.sg APIs and joined by planning area. A 2023 national AC-availability table and EMA's historical 2013 planning-area electricity GeoJSON were also inspected and frozen. Exact URLs, observation dates, retrieval dates and hashes: `data/sources.json`. EMA's current Chapter 3 page was reviewed, but its workbook could not be retrieved for schema inspection. See `README.md` for transformations, model assumptions and limitations.

## Tools and experiments

Implementation: Python 3.13, FastAPI, SQLite, scikit-learn, React, Vite. K-Means compared 2–4 clusters; the initial run selected two. Logistic regression was trained and tested on synthetic records. Local API tests and a Vite build passed, and the market and sales screens were captured in a local headless browser. AI coding assistance was used to research, plan, implement and document the prototype; no model API is required at runtime. No third-party visual assets were used.

## Open validation work

The team should review the live flow and presentation, confirm whether the proposed Bizsu residential use case matches its actual product and service constraints, and assess whether a pilot with real partners and consented homeowners is feasible. The current EMA workbook requires manual schema inspection before contemporary area electricity values can be added.
