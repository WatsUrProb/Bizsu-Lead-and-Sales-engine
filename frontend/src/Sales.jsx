import React, { useEffect, useMemo, useState } from 'react';
import { api, number, title } from './api.js';

const NEXT = {
  new: ['qualified', 'lost'], qualified: ['assessment_booked', 'lost'],
  assessment_booked: ['assessed', 'lost'], assessed: ['quoted', 'lost'],
  quoted: ['won', 'lost'], won: [], lost: [],
};

export default function Sales({ leads, partners, dashboard, refresh }) {
  const [partnerFilter, setPartnerFilter] = useState('all');
  const [stageFilter, setStageFilter] = useState('all');
  const [selectedId, setSelectedId] = useState(leads[0]?.id);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const filtered = useMemo(() => leads.filter(lead => (partnerFilter === 'all' || lead.partner_id === partnerFilter) && (stageFilter === 'all' || lead.stage === stageFilter)), [leads, partnerFilter, stageFilter]);
  const shownId = filtered.some(lead => lead.id === selectedId) ? selectedId : filtered[0]?.id;

  const loadDetail = async id => {
    if (!id) { setDetail(null); return; }
    setDetailError('');
    try { setDetail(await api(`/leads/${id}`)); } catch (err) { setDetailError(err.message); }
  };
  useEffect(() => { loadDetail(shownId); }, [shownId]);

  return <>
    <section className="page-intro sales-intro"><span className="eyebrow">04 / Sales engine</span><h1>Every referral,<br /><em>one clear trail.</em></h1><p>Explore a simulated sales funnel and inspect every enquiry. All referral sources here are fictional; real company candidates on the Partners page are not connected to these results.</p></section>
    <section className="section-block compact-top">
      <div className="data-banner"><strong>Synthetic performance dashboard</strong><span>Visits, enquiries, stage changes and wins are demo activity only. These figures are not Bizsu or researched-company results.</span></div>
      <div className="funnel-summary"><div><strong>Demo referral funnel</strong><span>Follow the synthetic journey from a visit to a simulated win.</span></div><span>{number(dashboard.active_partners)} fictional referral sources</span></div>
      <div className="funnel-steps" aria-label="Simulated referral funnel">{[
        ['01', 'Visits', dashboard.referral_visits],
        ['02', 'Enquiries', dashboard.submitted_enquiries],
        ['03', 'Qualified', dashboard.qualified_enquiries],
        ['04', 'Booked', dashboard.assessments_booked],
        ['05', 'Won', dashboard.won_deals],
      ].map(([step, label, value]) => <div key={step}><small>{step}</small><strong>{number(value)}</strong><span>{label}</span></div>)}</div>
      <div className="funnel-note"><strong>Small-sample demo funnel</strong><span>Enquiry → qualified: {dashboard.conversion_rates.enquiry_to_qualified_percent ?? '—'}% · Qualified → booked: {dashboard.conversion_rates.qualified_to_booked_percent ?? '—'}% · Booked → won: {dashboard.conversion_rates.booked_to_won_percent ?? '—'}%</span><small>{dashboard.note}</small></div>
      <div className="section-heading sales-heading"><div><h2>Lead pipeline</h2><p>Filter by referral partner and current stage. Select a lead to inspect attribution, qualification and history.</p></div><span className="subtle-tag">Synthetic records only</span></div>
      <div className="filter-bar"><label>Demo referral source<select value={partnerFilter} onChange={event => setPartnerFilter(event.target.value)}><option value="all">All demo sources</option>{partners.map(partner => <option key={partner.id} value={partner.id}>{partner.name}</option>)}</select></label><label>Current stage<select value={stageFilter} onChange={event => setStageFilter(event.target.value)}><option value="all">All stages</option>{Object.keys(NEXT).map(stage => <option key={stage} value={stage}>{title(stage)}</option>)}</select></label><span className="filter-result">{filtered.length} enquiries shown</span></div>
      <div className="sales-grid"><div className="lead-list panel">{filtered.length ? filtered.map(lead => <button key={lead.id} className={shownId === lead.id ? 'lead-row selected' : 'lead-row'} onClick={() => setSelectedId(lead.id)}><span className="lead-avatar">{lead.contact_name.split(' ').at(-1)?.slice(0, 2)}</span><span className="lead-main"><strong>{lead.contact_name}</strong><small>{lead.area} · {lead.partner_name || 'Direct enquiry'}</small></span><span className={`stage-badge ${lead.stage}`}>{title(lead.stage)}</span></button>) : <div className="empty-state">No enquiries match these filters.</div>}</div>
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
    <div className="detail-section"><h4>Attribution & qualification</h4><div className="detail-pair"><span>Demo referral source</span><strong>{lead.partner_name || 'Direct enquiry'}</strong></div><div className="detail-pair"><span>Referral code</span><strong>{lead.referral_code || '—'}</strong></div><div className="detail-pair"><span>Screening</span><strong>{title(lead.qualification_status)}</strong></div><ul className="reason-list">{lead.qualification_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></div>
    <div className="detail-section"><h4>Area context & demo ML</h4><p className="small-note">{lead.area_context ? `The ${lead.area} planning-area cluster is described as “${lead.area_context}.”` : 'This area has no cluster because published input cells are missing.'} This is aggregate context, not a description of the household.</p><div className="ml-score"><strong>{lead.ml_score == null ? '—' : `${lead.ml_score}/100`}</strong><span>Synthetic conversion score<br /><small>Unvalidated · model {lead.model_version}</small></span></div><p className="small-note">This classifier was trained and evaluated only on simulated outcomes. Its score is not a real purchase probability.</p></div>
    <div className="detail-section"><h4>Pipeline history</h4><ol className="event-list">{lead.stage_events.map(event => <li key={event.id}><span>{title(event.to_stage)}</span><small>{new Date(event.created_at).toLocaleString('en-SG')}</small></li>)}</ol>{options.length > 0 && <div className="stage-controls"><select value={nextStage} onChange={event => setNextStage(event.target.value)}>{options.map(stage => <option key={stage} value={stage}>Move to {title(stage)}</option>)}</select><button className="button secondary" disabled={working} onClick={() => action(() => api(`/leads/${lead.id}/stage`, { method: 'PATCH', body: JSON.stringify({ stage: nextStage }) }), 'Pipeline stage updated.')}>Update stage</button></div>}</div>
    <div className="detail-section draft-section"><h4>Follow-up draft</h4><p className="small-note">Template-based, editable and local. Human review is required; no outbound service is connected.</p>{draftId ? <><textarea aria-label="Editable follow-up draft" rows="5" value={message} onChange={event => setMessage(event.target.value)} /><div className="draft-actions"><button className="button secondary" onClick={generateDraft} disabled={working}>Regenerate</button><button className="button primary" onClick={saveDraft} disabled={working || message.trim().length < 5}>Save draft</button></div></> : <button className="button secondary" onClick={generateDraft} disabled={working}>Generate draft</button>}{feedback && <p className="action-feedback" role="status">{feedback}</p>}</div>
  </>;
}
