import React, { useEffect, useMemo, useState } from 'react';
import { api, number, title } from './api.js';

const NEXT = {
  new: ['qualified', 'lost'], qualified: ['assessment_booked', 'lost'],
  assessment_booked: ['assessed', 'lost'], assessed: ['quoted', 'lost'],
  quoted: ['won', 'lost'], won: [], lost: [],
};

export default function Sales({ leads, catalog, dashboard, refresh }) {
  const initialCompany = new URLSearchParams(window.location.search).get('company');
  const [companyFilter, setCompanyFilter] = useState(catalog.candidates.some(item => item.id === initialCompany) ? initialCompany : 'all');
  const [stageFilter, setStageFilter] = useState('all');
  const [selectedId, setSelectedId] = useState(leads[0]?.id);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const filtered = useMemo(() => leads.filter(lead => (companyFilter === 'all' || lead.company_id === companyFilter) && (stageFilter === 'all' || lead.stage === stageFilter)), [leads, companyFilter, stageFilter]);
  const metrics = companyFilter === 'all' ? dashboard : dashboard.company_breakdown[companyFilter];
  const companyName = companyFilter === 'all' ? 'All companies' : metrics.company_name;
  const chooseCompany = id => {
    setCompanyFilter(id);
    window.history.replaceState({}, '', id === 'all' ? '/sales' : `/sales?company=${id}`);
  };
  const shownId = filtered.some(lead => lead.id === selectedId) ? selectedId : filtered[0]?.id;

  const loadDetail = async id => {
    if (!id) { setDetail(null); return; }
    setDetailError('');
    try { setDetail(await api(`/leads/${id}`)); } catch (err) { setDetailError(err.message); }
  };
  useEffect(() => { loadDetail(shownId); }, [shownId]);

  return <>
    <section className="page-intro sales-intro"><span className="eyebrow">03 / Sales pipeline</span><h1>See each company.<br /><em>Follow every lead.</em></h1><p>Choose an aircon company to see its simulated referrals, enquiries and outcomes.</p></section>
    <section className="section-block compact-top">
      <div className="data-banner"><strong>Simulation only</strong><span>The company names are real research profiles. Every visit, enquiry and outcome below is invented for this demo. No partnership is implied.</span></div>
      <div className="company-tabs" role="group" aria-label="Filter by aircon company"><button className={companyFilter === 'all' ? 'active' : ''} onClick={() => chooseCompany('all')}>All companies</button>{catalog.candidates.map(candidate => <button key={candidate.id} className={companyFilter === candidate.id ? 'active' : ''} onClick={() => chooseCompany(candidate.id)}>{candidate.name}<small>{dashboard.company_breakdown[candidate.id]?.submitted_enquiries ?? 0} enquiries</small></button>)}</div>
      <div className="funnel-summary"><div><strong>{companyName} · demo funnel</strong><span>Follow the simulated journey from visit to win.</span></div><span>Simulated data</span></div>
      <div className="funnel-steps" aria-label="Simulated referral funnel">{[
        ['01', 'Visits', metrics.referral_visits],
        ['02', 'Enquiries', metrics.submitted_enquiries],
        ['03', 'Qualified', metrics.qualified_enquiries],
        ['04', 'Booked', metrics.assessments_booked],
        ['05', 'Won', metrics.won_deals],
      ].map(([step, label, value]) => <div key={step}><small>{step}</small><strong>{number(value)}</strong><span>{label}</span></div>)}</div>
      <div className="funnel-note"><strong>Demo stage rates</strong><span>Enquiry → qualified: {metrics.conversion_rates.enquiry_to_qualified_percent ?? '—'}% · Qualified → booked: {metrics.conversion_rates.qualified_to_booked_percent ?? '—'}% · Booked → won: {metrics.conversion_rates.booked_to_won_percent ?? '—'}%</span><small>{dashboard.note}</small></div>
      <div className="section-heading sales-heading"><div><h2>Enquiries</h2><p>Select a lead to see why it qualified, its stage history and its follow-up draft.</p></div><span className="subtle-tag">Synthetic records</span></div>
      <div className="filter-bar"><label>Stage<select value={stageFilter} onChange={event => setStageFilter(event.target.value)}><option value="all">All stages</option>{Object.keys(NEXT).map(stage => <option key={stage} value={stage}>{title(stage)}</option>)}</select></label><span className="filter-result">{filtered.length} enquiries for {companyName.toLowerCase()}</span></div>
      <div className="sales-grid"><div className="lead-list panel">{filtered.length ? filtered.map(lead => <button key={lead.id} className={shownId === lead.id ? 'lead-row selected' : 'lead-row'} onClick={() => setSelectedId(lead.id)}><span className="lead-avatar">{lead.contact_name.split(' ').at(-1)?.slice(0, 2)}</span><span className="lead-main"><strong>{lead.contact_name}</strong><small>{lead.company_name || 'Direct demo enquiry'} · {lead.area}</small></span><span className={`stage-badge ${lead.stage}`}>{title(lead.stage)}</span></button>) : <div className="empty-state">No enquiries match these filters.</div>}</div>
        <div className="panel lead-detail">{detailError ? <div className="form-error">{detailError}</div> : detail && detail.id === shownId ? <LeadDetail key={detail.id} lead={detail} refresh={async () => { await refresh(); await loadDetail(detail.id); }} /> : <div className="empty-state">Select an enquiry to view its details.</div>}</div></div>
    </section>
  </>;
}

function LeadDetail({ lead, refresh }) {
  const options = NEXT[lead.stage].filter(stage => stage !== 'qualified' || lead.qualification_status === 'qualified');
  const [nextStage, setNextStage] = useState(options[0] || '');
  const [message, setMessage] = useState(lead.drafts[0]?.message || '');
  const [draftId, setDraftId] = useState(lead.drafts[0]?.id || null);
  const [working, setWorking] = useState(false);
  const [feedback, setFeedback] = useState('');
  useEffect(() => { setNextStage(options[0] || ''); }, [lead.stage, lead.qualification_status]);

  const action = async (fn, success) => {
    setWorking(true); setFeedback('');
    try { await fn(); setFeedback(success); await refresh(); } catch (err) { setFeedback(err.message); }
    finally { setWorking(false); }
  };
  const generateDraft = () => action(async () => {
    const draft = await api(`/leads/${lead.id}/draft`, { method: 'POST' });
    setDraftId(draft.id); setMessage(draft.message);
  }, 'Draft generated for review.');
  const saveDraft = () => action(() => api(`/drafts/${draftId}`, { method: 'PATCH', body: JSON.stringify({ message }) }), 'Draft saved locally. No message was sent.');

  return <><div className="detail-top"><div><span className="card-kicker">Enquiry #{lead.id}</span><h3>{lead.contact_name}</h3><span className="muted">{lead.area} · {lead.property_type}</span></div><span className={`stage-badge ${lead.stage}`}>{title(lead.stage)}</span></div>
    <div className="detail-section"><h4>Company scenario & screening</h4><div className="detail-pair"><span>Aircon company</span><strong>{lead.company_name || 'Direct demo enquiry'} · simulated association</strong></div><div className="detail-pair"><span>Screening</span><strong>{title(lead.qualification_status)}</strong></div><ul className="reason-list">{lead.qualification_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></div>
    <div className="detail-section"><h4>Pipeline history</h4><ol className="event-list">{lead.stage_events.map(event => <li key={event.id}><span>{title(event.to_stage)}</span><small>{new Date(event.created_at).toLocaleString('en-SG')}</small></li>)}</ol>{options.length > 0 && <div className="stage-controls"><select value={nextStage} onChange={event => setNextStage(event.target.value)}>{options.map(stage => <option key={stage} value={stage}>Move to {title(stage)}</option>)}</select><button className="button secondary" disabled={working} onClick={() => action(() => api(`/leads/${lead.id}/stage`, { method: 'PATCH', body: JSON.stringify({ stage: nextStage }) }), 'Pipeline stage updated.')}>Update stage</button></div>}</div>
    <div className="detail-section draft-section"><h4>Follow-up draft</h4><p className="small-note">Template-based, editable and local. Human review is required; no outbound service is connected.</p>{draftId ? <><textarea aria-label="Editable follow-up draft" rows="5" value={message} onChange={event => setMessage(event.target.value)} /><div className="draft-actions"><button className="button secondary" onClick={generateDraft} disabled={working}>Regenerate</button><button className="button primary" onClick={saveDraft} disabled={working || message.trim().length < 5}>Save draft</button></div></> : <button className="button secondary" onClick={generateDraft} disabled={working}>Generate draft</button>}{feedback && <p className="action-feedback" role="status">{feedback}</p>}</div>
  </>;
}
