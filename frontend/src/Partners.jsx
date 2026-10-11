import React, { useEffect, useState } from 'react';
import { api } from './api.js';

const SIGNAL_LABELS = {
  residential: 'Residential work',
  servicing_and_installation: 'Servicing and installation',
  maintenance_plan: 'Recurring maintenance plan',
  coverage: 'Singapore-wide coverage stated',
};

export default function Partners({ partners, catalog, navigate }) {
  const [candidates, setCandidates] = useState(catalog?.candidates || []);
  const [weights, setWeights] = useState(catalog?.weights || {});
  const [selectedId, setSelectedId] = useState(catalog?.candidates?.[0]?.id);
  const [shortlistOnly, setShortlistOnly] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [demoId, setDemoId] = useState(partners[0]?.id);
  const [copied, setCopied] = useState(false);

  const score = candidate => {
    const total = Object.values(weights).reduce((sum, value) => sum + Number(value), 0);
    if (!total) return 0;
    return Math.round(100 * Object.entries(weights).reduce((sum, [key, value]) =>
      sum + (candidate.signals[key] ? Number(value) : 0), 0) / total);
  };
  const visible = candidates.filter(candidate => !shortlistOnly || candidate.shortlisted)
    .sort((a, b) => score(b) - score(a) || a.name.localeCompare(b.name));
  const selected = visible.find(candidate => candidate.id === selectedId) || visible[0];
  const demoPartner = partners.find(partner => partner.id === demoId) || partners[0];
  const demoLink = demoPartner ? `${window.location.origin}/home?ref=${encodeURIComponent(demoPartner.referral_code)}` : '';

  useEffect(() => { setDraft(selected?.outreach_draft || ''); setFeedback(''); }, [selected?.id]);

  const save = async shortlisted => {
    if (!selected) return;
    setSaving(true);
    setFeedback('');
    try {
      await api(`/candidates/${selected.id}`, {
        method: 'PATCH', body: JSON.stringify({ shortlisted, outreach_draft: draft }),
      });
      setCandidates(current => current.map(item => item.id === selected.id
        ? { ...item, shortlisted, outreach_draft: draft } : item));
      setFeedback('Saved locally. No outreach was sent.');
    } catch (error) { setFeedback(error.message); }
    finally { setSaving(false); }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(demoLink);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2200);
    } catch { setCopied(false); }
  };

  return <>
    <section className="page-intro"><span className="eyebrow">02 / Partner discovery</span><h1>Find candidates.<br /><em>Check the evidence.</em></h1><p>Research real Singapore aircon service companies, shortlist those worth reviewing, and prepare an editable outreach draft. No company listed here is a Bizsu partner.</p></section>
    <section className="section-block compact-top">
      <div className="data-banner"><strong>Public company information</strong><span>{catalog?.note} Sources checked {catalog?.retrieved_on}.</span></div>
      <div className="section-heading"><div><h2>Company candidates</h2><p>Evidence scores rank documented fit. Missing details stay unverified; review each source before contacting anyone.</p></div><span className="subtle-tag">{candidates.filter(item => item.shortlisted).length} shortlisted · {candidates.length} researched</span></div>
      <div className="weight-controls panel"><div><strong>Set research priorities</strong><small>Adjust the weights to re-rank documented evidence. Changes stay in this browser session.</small></div><div className="weight-grid">{Object.entries(weights).map(([key, value]) => <label key={key}><span>{SIGNAL_LABELS[key]} <b>{value}</b></span><input type="range" min="0" max="100" step="10" value={value} onChange={event => setWeights(current => ({ ...current, [key]: Number(event.target.value) }))} /></label>)}</div></div>
      <div className="filter-bar"><label className="checkbox-filter"><input type="checkbox" checked={shortlistOnly} onChange={event => setShortlistOnly(event.target.checked)} /> Shortlisted only</label><span className="filter-result">{visible.length} candidates shown</span></div>
      <div className="partner-grid"><div className="partner-list">{visible.length ? visible.map((candidate, index) => <button key={candidate.id} className={selected?.id === candidate.id ? 'partner-row selected' : 'partner-row'} onClick={() => setSelectedId(candidate.id)}><span className="partner-rank">{String(index + 1).padStart(2, '0')}</span><span className="partner-row-main"><strong>{candidate.name}</strong><small>{candidate.focus}{candidate.shortlisted ? ' · Shortlisted' : ''}</small></span><span className="partner-score">{score(candidate)}</span></button>) : <div className="empty-state">No candidates shortlisted yet. Turn off the filter to review the list.</div>}</div>
        <div className="panel partner-detail">{selected ? <>
          <span className="card-kicker">Sourced candidate · no partnership implied</span><h3>{selected.name}</h3><p>{selected.summary}</p>
          <div className="score-feature"><strong>{score(selected)}<small>/ 100</small></strong><span>Documented fit score</span></div>
          <div className="score-list">{Object.entries(weights).map(([key, weight]) => <div key={key}><div className="score-label"><span>{SIGNAL_LABELS[key]} <small>(weight {weight})</small></span><strong>{selected.signals[key] ? 'Documented' : 'Unverified'}</strong></div><div className="bar-track"><div style={{ width: selected.signals[key] ? '100%' : '0%' }} /></div></div>)}</div>
          <div className="detail-section"><h4>What is documented</h4><div className="detail-pair"><span>Services</span><strong>{selected.services.join(', ')}</strong></div><div className="detail-pair"><span>Maintenance</span><strong>{selected.maintenance_plan}</strong></div><div className="detail-pair"><span>Coverage</span><strong>{selected.coverage}</strong></div><div className="detail-pair"><span>Public contact</span><strong>{[selected.contact.phone, selected.contact.email].filter(Boolean).join(' · ') || 'Unverified'}</strong></div></div>
          <div className="detail-section"><h4>Evidence</h4><ul className="evidence-list">{selected.evidence.map(item => <li key={item.url}><a href={item.url} target="_blank" rel="noreferrer">{item.label} ↗</a></li>)}</ul><small>Checked {catalog.retrieved_on}. Confirm current details on the company site.</small></div>
          <div className="candidate-actions"><button className="button secondary" disabled={saving} onClick={() => save(!selected.shortlisted)}>{selected.shortlisted ? 'Remove from shortlist' : 'Add to shortlist'}</button><a className="text-link" href={selected.website} target="_blank" rel="noreferrer">Official website ↗</a></div>
          <div className="detail-section draft-section"><h4>Editable outreach draft</h4><p className="small-note">Research draft only. Confirm Bizsu's proposal and company details before any contact.</p><textarea aria-label="Candidate outreach draft" rows="8" value={draft} onChange={event => setDraft(event.target.value)} /><div className="draft-actions"><button className="button primary" disabled={saving} onClick={() => save(selected.shortlisted)}>Save draft</button></div>{feedback && <p className="action-feedback" role="status">{feedback}</p>}</div>
        </> : <div className="empty-state">Select a company to inspect its evidence.</div>}</div></div>
    </section>
    <section className="section-block demo-lab" id="demo-referrals"><div className="section-heading"><div><span className="eyebrow">Separate simulation</span><h2>Try the referral journey</h2><p>These fictional demo partners exist only to show attribution and sales workflow. Their visits and enquiries are simulated and are never assigned to the real companies above.</p></div><span className="subtle-tag">Synthetic sandbox</span></div>
      <div className="demo-referral-panel panel"><label>Demo referral source<select value={demoPartner?.id || ''} onChange={event => { setDemoId(event.target.value); setCopied(false); }}>{partners.map(partner => <option key={partner.id} value={partner.id}>{partner.name}</option>)}</select></label><div className="copy-row"><input aria-label="Synthetic demo referral link" readOnly value={demoLink} /><button className="button secondary" onClick={copy}>{copied ? 'Copied' : 'Copy link'}</button></div><button className="button primary" onClick={() => navigate('home', `?ref=${demoPartner.referral_code}`)}>Open demo homeowner form →</button></div>
    </section>
  </>;
}
