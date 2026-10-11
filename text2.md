# Bizsu Prototype — Company Data Strategy

## Decision A: Where will company data come from?

### Selected approach: Real Singapore companies + synthetic referral outcomes

Use **real, publicly available company information** to discover and evaluate potential air-conditioning servicing partners in Singapore. Use **clearly labelled synthetic data** to demonstrate downstream partnership activity, homeowner referrals, and sales outcomes.

### Real company data for partner discovery

Collect publicly available information about actual Singapore air-conditioning servicing companies, such as:

- Company name and official website
- Residential versus commercial servicing focus
- Air-conditioning servicing and installation offerings
- Recurring maintenance packages, where publicly documented
- Service coverage areas, where publicly documented
- Public business contact channels
- Source URLs and retrieval dates for verification

**Advantages**

- Makes the demonstration more credible.
- Produces a shortlist that could be useful to Bizsu.
- Demonstrates that the platform can analyse real business information.

**Data safeguards**

- Respect website terms, robots directives, and applicable access restrictions.
- Do not invent missing company attributes; label them **Unverified**.
- Show evidence or source links for extracted characteristics.
- Do not imply any listed company has agreed to partner with Bizsu.

### Synthetic data for downstream demonstration

Use fictional, explicitly labelled records to demonstrate:

- Partner outreach and onboarding statuses
- Unique referral links and attributed homeowner enquiries
- Lead qualification and sales pipeline stages
- Referral counts, simulated conversions, and illustrative commissions

Do not present simulated partnerships, enquiries, conversions, or revenue as real Bizsu results.

### Recommended prototype flow

1. Discover real Singapore air-conditioning servicing companies.
2. Extract relevant characteristics and supporting evidence.
3. Rank potential partners using transparent, configurable criteria.
4. Let Bizsu shortlist companies and prepare editable outreach drafts.
5. Simulate partner onboarding and homeowner referrals.
6. Display a clearly labelled demo referral-performance dashboard.

**Core principle:** Real-world evidence for *who Bizsu could approach*; synthetic data for *how the proposed partnership and referral workflow would operate*.
