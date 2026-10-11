import React, { useState } from 'react';

const CRITERIA = {
  residential_relevance: 'Residential relevance',
  service_complementarity: 'Service complementarity',
  geographic_coverage: 'Geographic coverage',
  engagement_fit: 'Engagement fit',
};

export default function Partners({ partners, navigate }) {
  const [selectedId, setSelectedId] = useState(partners[0]?.id);
  const [copied, setCopied] = useState(false);
  const selected = partners.find(partner => partner.id === selectedId) || partners[0];
  const link = selected ? `${window.location.origin}/home?ref=${encodeURIComponent(selected.referral_code)}` : '';
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2200);
    } catch {
      setCopied(false);
    }
  };

  return <>
    <section className="page-intro"><span className="eyebrow">02 / Partner discovery</span><h1>A channel to test,<br /><em>partner by partner.</em></h1><p>These businesses are fictional demo records. The ranking is a transparent weighted assessment—not a learned score or evidence of willingness to partner.</p></section>
    <section className="section-block compact-top"><div className="section-heading"><div><h2>Ranked demo partners</h2><p>Select a partner to inspect each score and copy its unique referral link.</p></div><span className="subtle-tag">Illustrative scoring weights</span></div>
      <div className="partner-grid"><div className="partner-list">{partners.map((partner, index) => <button key={partner.id} className={selected?.id === partner.id ? 'partner-row selected' : 'partner-row'} onClick={() => { setSelectedId(partner.id); setCopied(false); }}><span className="partner-rank">{String(index + 1).padStart(2, '0')}</span><span className="partner-row-main"><strong>{partner.name}</strong><small>{partner.customer_focus} focus · {partner.service_areas.length} demo areas</small></span><span className="partner-score">{partner.ranking.score}</span></button>)}</div>
        <div className="panel partner-detail">{selected ? <><span className="card-kicker">Suitability breakdown</span><h3>{selected.name}</h3><p>{selected.description}</p><div className="score-feature"><strong>{selected.ranking.score}<small>/ 100</small></strong><span>Illustrative weighted score</span></div>
          <div className="score-list">{Object.entries(CRITERIA).map(([key, label]) => <div key={key}><div className="score-label"><span>{label} <small>({Math.round(selected.ranking.weights[key] * 100)}%)</small></span><strong>{Math.round(selected.ranking.components[key] * 100)} / 100</strong></div><div className="bar-track"><div style={{ width: `${selected.ranking.components[key] * 100}%` }} /></div></div>)}</div>
          <div className="referral-box"><label htmlFor="referral-link">Unique referral link</label><div className="copy-row"><input id="referral-link" readOnly value={link} /><button className="button secondary" onClick={copy}>{copied ? 'Copied' : 'Copy link'}</button></div><button className="text-link inline-link" onClick={() => navigate('home', `?ref=${selected.referral_code}`)}>Open homeowner journey →</button></div>
          <p className="small-note">Source: fictional partner attributes supplied for the demo. A real discovery pipeline would require verified business data and human review.</p>
        </> : <div className="empty-state">No demo partners available.</div>}</div></div>
    </section>
  </>;
}
