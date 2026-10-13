import React, { useEffect, useMemo, useState } from 'react';
import { api, number, title } from './api.js';

const NEXT = {
  new: ['qualified', 'lost'], qualified: ['assessment_booked', 'lost'],
  assessment_booked: ['assessed', 'lost'], assessed: ['quoted', 'lost'],
  quoted: ['won', 'lost'], won: [], lost: [],
};
const STAGE_RULES = {
  new: 'Form submitted with contact consent. Screening is separate from pipeline progress.',
  qualified: 'Known Singapore planning area, supported split or multi-split AC, and complete usage details; or an explicit staff review.',
  assessment_booked: 'A customer appointment has been agreed. Record the date or booking confirmation.',
  assessed: 'A technical assessment has been completed. Record what was checked and the outcome.',
  quoted: 'A quote has been shared with the customer. Record the quote reference or summary.',
  won: 'The customer accepted the quote. Record the acceptance evidence.',
  lost: 'The opportunity will not proceed. Record the reason.',
};
const EVIDENCE_PROMPTS = {
  assessment_booked: 'Appointment date and customer confirmation',
  assessed: 'Assessment date and technical outcome',
  quoted: 'Quote reference and what was offered',
  won: 'Customer acceptance or agreement',
  lost: 'Why this enquiry will not proceed',
};

export default function Sales({ leads, areas, dashboard, refresh }) {
  const scenarioCompanies = Object.entries(dashboard.company_breakdown).filter(([,item]) => item.active_partners > 0).map(([id,item]) => ({id,name:item.company_name})).sort((a,b)=>a.name.localeCompare(b.name));
  const initialCompany = new URLSearchParams(window.location.search).get('company');
  const initialLeadId = Number(new URLSearchParams(window.location.search).get('lead'));
  const linkedLead = leads.find(item => item.id === initialLeadId);
  const startingCompany = linkedLead?.company_id || (scenarioCompanies.some(item => item.id === initialCompany) ? initialCompany : 'all');
  const [companyFilter, setCompanyFilter] = useState(startingCompany);
  const [stageFilter, setStageFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState(linkedLead?.data_kind === 'synthetic seeded enquiry' ? 'sample' : leads.some(item => item.data_kind === 'synthetic submitted enquiry' && (startingCompany === 'all' || item.company_id === startingCompany)) ? 'submitted' : 'sample');
  const [selectedId, setSelectedId] = useState(linkedLead?.id || leads[0]?.id);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const filtered = useMemo(() => leads.filter(lead => (companyFilter === 'all' || lead.company_id === companyFilter) && (stageFilter === 'all' || lead.stage === stageFilter) && (sourceFilter === 'all' || (sourceFilter === 'submitted' ? lead.data_kind === 'synthetic submitted enquiry' : lead.data_kind === 'synthetic seeded enquiry'))), [leads, companyFilter, stageFilter, sourceFilter]);
  const metrics = companyFilter === 'all' ? dashboard : dashboard.company_breakdown[companyFilter];
  const companyName = companyFilter === 'all' ? 'All companies' : metrics.company_name;
  const chooseCompany = id => {
    setCompanyFilter(id);
    if (sourceFilter === 'submitted' && !leads.some(item => item.data_kind === 'synthetic submitted enquiry' && (id === 'all' || item.company_id === id))) setSourceFilter('sample');
    window.history.replaceState({}, '', id === 'all' ? '/demo/sales' : `/demo/sales?company=${id}`);
  };
  const shownId = filtered.some(lead => lead.id === selectedId) ? selectedId : filtered[0]?.id;

  const loadDetail = async id => {
    if (!id) { setDetail(null); return; }
    setDetailError('');
    try { setDetail(await api(`/leads/${id}`)); } catch (err) { setDetailError(err.message); }
  };
  useEffect(() => { loadDetail(shownId); }, [shownId]);

  return <>
    <section className="page-intro sales-intro"><span className="eyebrow">03 / Customer pipeline</span><h1>From referral<br /><em>to next action.</em></h1><p>See who referred each homeowner, what they told us, why screening passed, and what evidence supports each stage.</p></section>
    <section className="section-block compact-top">
      <div className="data-banner"><strong>Simulation only</strong><span>The company names are real research profiles. Every visit, enquiry and outcome below is invented for this demo. No partnership is implied.</span></div>
      <div className="company-tabs" role="group" aria-label="Filter by aircon company"><button className={companyFilter === 'all' ? 'active' : ''} onClick={() => chooseCompany('all')}>All companies</button>{scenarioCompanies.map(candidate => <button key={candidate.id} className={companyFilter === candidate.id ? 'active' : ''} onClick={() => chooseCompany(candidate.id)}>{candidate.name}<small>{dashboard.company_breakdown[candidate.id]?.submitted_enquiries ?? 0} enquiries</small></button>)}</div>
      <div className="funnel-summary"><div><strong>{companyName} · demo funnel</strong><span>Follow the simulated journey from visit to win.</span></div><span>Simulated data</span></div>
      <div className="funnel-steps" aria-label="Simulated referral funnel">{[
        ['01', 'Visits', metrics.referral_visits],
        ['02', 'Enquiries', metrics.submitted_enquiries],
        ['03', 'Qualified', metrics.qualified_enquiries],
        ['04', 'Booked', metrics.assessments_booked],
        ['05', 'Won', metrics.won_deals],
      ].map(([step, label, value]) => <div key={step}><small>{step}</small><strong>{number(value)}</strong><span>{label}</span></div>)}</div>
      <div className="funnel-note"><strong>Demo stage rates</strong><span>Enquiry → qualified: {metrics.conversion_rates.enquiry_to_qualified_percent ?? '—'}% · Qualified → booked: {metrics.conversion_rates.qualified_to_booked_percent ?? '—'}% · Booked → won: {metrics.conversion_rates.booked_to_won_percent ?? '—'}%</span><small>{dashboard.note}</small></div>
      <div className="section-heading sales-heading"><div><h2>Customer enquiries</h2><p>Form submissions and seeded example journeys are separated so each stage is easier to interpret.</p></div><span className="subtle-tag">Internal demo</span></div>
      <div className="filter-bar"><label>Records<select value={sourceFilter} onChange={event => setSourceFilter(event.target.value)}><option value="submitted">Form submissions</option><option value="sample">Sample journeys</option><option value="all">All demo records</option></select></label><label>Stage<select value={stageFilter} onChange={event => setStageFilter(event.target.value)}><option value="all">All stages</option>{Object.keys(NEXT).map(stage => <option key={stage} value={stage}>{title(stage)}</option>)}</select></label><span className="filter-result">{filtered.length} enquiries for {companyName.toLowerCase()}</span></div>
      <div className="sales-grid"><div className="lead-list panel">{filtered.length ? filtered.map(lead => <button key={lead.id} className={shownId === lead.id ? 'lead-row selected' : 'lead-row'} onClick={() => setSelectedId(lead.id)}><span className="lead-avatar">{lead.contact_name.split(' ').at(-1)?.slice(0, 2)}</span><span className="lead-main"><strong>{lead.contact_name} <small>#{lead.id}</small></strong><small>{lead.company_name ? 'Referred via ' + lead.company_name : 'Direct enquiry'}</small><small>{lead.property_type} · {lead.area} · {lead.data_kind === 'synthetic seeded enquiry' ? 'Sample journey' : 'Form submission'}</small></span><span className={`stage-badge ${lead.stage}`}>{title(lead.stage)}</span></button>) : <div className="empty-state">No enquiries match these filters.</div>}</div>
        <div className="panel lead-detail">{detailError ? <div className="form-error">{detailError}</div> : detail && detail.id === shownId ? <LeadDetail key={detail.id} lead={detail} areas={areas} refresh={async () => { await refresh(); await loadDetail(detail.id); }} /> : <div className="empty-state">Select an enquiry to view its details.</div>}</div></div>
    </section>
  </>;
}

function LeadDetail({ lead, areas, refresh }) {
  const options = NEXT[lead.stage].filter(stage => stage !== 'qualified' || lead.qualification_status === 'qualified');
  const [nextStage, setNextStage] = useState('');
  const [message, setMessage] = useState(lead.drafts[0]?.message || '');
  const [draftId, setDraftId] = useState(lead.drafts[0]?.id || null);
  const [draftStatus, setDraftStatus] = useState(lead.drafts[0]?.status || 'draft');
  const [draftDirty, setDraftDirty] = useState(false);
  const [working, setWorking] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [reviewReason, setReviewReason] = useState('');
  const [reviewArea, setReviewArea] = useState(lead.area === 'Not provided' ? '' : lead.area);
  const [reviewAcType, setReviewAcType] = useState(['split','multi_split'].includes(lead.ac_type) ? lead.ac_type : '');
  const [stageEvidence, setStageEvidence] = useState('');
  useEffect(() => { setNextStage(''); setStageEvidence(''); }, [lead.stage, lead.qualification_status]);

  const action = async (fn, success) => {
    setWorking(true); setFeedback('');
    try { await fn(); setFeedback(success); await refresh(); } catch (err) { setFeedback(err.message); }
    finally { setWorking(false); }
  };
  const generateDraft = () => action(async () => {
    const draft = await api(`/leads/${lead.id}/draft`, { method: 'POST' });
    setDraftId(draft.id); setMessage(draft.message); setDraftStatus('draft'); setDraftDirty(false);
  }, 'New draft created for review.');
  const saveDraft = () => action(async () => {
    await api(`/drafts/${draftId}`, { method: 'PATCH', body: JSON.stringify({ message }) });
    setDraftDirty(false);
  }, 'Draft saved locally. No message was sent.');
  const markSent = () => {
    if (!window.confirm('Confirm that you actually sent this message using your email app?')) return;
    action(async () => {
      await api(`/drafts/${draftId}/mark-sent`, {method:'POST',body:JSON.stringify({confirmed:true})});
      setDraftStatus('sent');
    }, 'Message marked sent. This does not change the customer stage.');
  };
  const emailSubject = `Bizsu enquiry #${lead.id}: next steps`;

  return <><div className="detail-top"><div><span className="card-kicker">Enquiry #{lead.id} · {lead.data_kind === 'synthetic seeded enquiry' ? 'sample journey' : 'form submission'}</span><h3>{lead.contact_name}</h3><span className="muted">{lead.property_type} · {lead.area}</span></div><span className={`stage-badge ${lead.stage}`}>{title(lead.stage)}</span></div>
    <div className="detail-section referral-detail"><h4>Referral attribution</h4><strong>{lead.company_name ? lead.company_name + ' · demo referral' : 'Direct enquiry · no aircon company referral'}</strong><p>{lead.company_name ? 'This company label comes from the referral code in the homeowner link. It is a fictional demo association, not a confirmed Bizsu partnership.' : 'No referral code was supplied with this enquiry.'}</p>{lead.referral_code && <div className="detail-pair"><span>Referral code</span><strong>{lead.referral_code}</strong></div>}{lead.partner_id && <div className="detail-pair"><span>Demo partner ID</span><strong>{lead.partner_id}</strong></div>}</div>
    <div className="detail-section"><h4>What the homeowner provided</h4><div className="detail-pair"><span>Housing and area</span><strong>{lead.property_type} · {lead.area}</strong></div><div className="detail-pair"><span>AC setup</span><strong>{title(lead.ac_type)} · {lead.ac_units} unit{lead.ac_units===1?'':'s'}</strong></div><div className="detail-pair"><span>Daily use</span><strong>{lead.daily_hours} hours</strong></div><div className="detail-pair"><span>Contact</span><strong>{lead.contact_email}{lead.contact_phone ? ' · ' + lead.contact_phone : ''}</strong></div>{lead.enquiry_note && <div className="enquiry-note"><b>Homeowner note</b><p>{lead.enquiry_note}</p></div>}</div>
    <div className="detail-section"><h4>Screening decision</h4><div className="detail-pair"><span>Result</span><strong>{title(lead.qualification_status)}</strong></div><ul className="reason-list">{lead.qualification_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul><p className="small-note">A qualified screening result permits staff to move the record to Qualified. It does not book an assessment or imply a sale.</p>{lead.stage==='new'&&lead.qualification_status==='needs_review'&&<div className="manual-review"><label>Confirmed planning area<select value={reviewArea} onChange={event=>setReviewArea(event.target.value)}><option value="">Select area</option>{areas.map(area=><option key={area.name} value={area.name}>{area.name}</option>)}</select></label><label>Confirmed AC system<select value={reviewAcType} onChange={event=>setReviewAcType(event.target.value)}><option value="">Select supported system</option><option value="split">Split unit</option><option value="multi_split">Multi-split</option></select></label><label>Review outcome note<input value={reviewReason} onChange={event=>setReviewReason(event.target.value)} placeholder="What did staff confirm with the homeowner?" /></label><button className="button secondary" disabled={working||!reviewArea||!reviewAcType||reviewReason.trim().length<10} onClick={()=>action(()=>api(`/leads/${lead.id}/review`,{method:'POST',body:JSON.stringify({area:reviewArea,ac_type:reviewAcType,reason:reviewReason.trim()})}),'Suitability confirmed. This enquiry can now move to Qualified.')}>Confirm after review</button></div>}</div>
    <div className="detail-section"><h4>Why this stage?</h4><div className="stage-rule"><b>{title(lead.stage)}</b><p>{STAGE_RULES[lead.stage]}</p></div>{lead.data_kind === 'synthetic seeded enquiry' && <p className="sample-caveat">This is a seeded example journey. Its stage was assigned for demonstration and has no real booking, assessment, quote, or sale behind it.</p>}<details className="stage-guide"><summary>See criteria for every stage</summary><ul>{Object.entries(STAGE_RULES).map(([stage,rule])=><li key={stage}><b>{title(stage)}:</b> {rule}</li>)}</ul></details></div>
    <div className="detail-section"><h4>Stage history and next action</h4><ol className="event-list">{lead.stage_events.map(event => <li key={event.id}><div><b>{title(event.to_stage)}</b><span>{event.reason || (lead.data_kind === 'synthetic seeded enquiry' ? 'Illustrative seeded stage; no verified outcome.' : 'No supporting note was recorded for this older demo event.')}</span></div><small>{new Date(event.created_at).toLocaleString('en-SG')}</small></li>)}</ol>{options.length > 0 && <div className="stage-update"><label>Next stage<select value={nextStage} onChange={event => {setNextStage(event.target.value);setStageEvidence('')}}><option value="">Choose a stage</option>{options.map(stage => <option key={stage} value={stage}>{title(stage)}</option>)}</select></label>{nextStage && <p>{STAGE_RULES[nextStage]}</p>}{nextStage && nextStage !== 'qualified' && <label>Evidence or outcome reason<textarea rows="2" maxLength="500" value={stageEvidence} onChange={event=>setStageEvidence(event.target.value)} placeholder={EVIDENCE_PROMPTS[nextStage]} /></label>}<button className="button secondary" disabled={working || !nextStage || (nextStage !== 'qualified' && stageEvidence.trim().length < 10)} onClick={() => action(() => api(`/leads/${lead.id}/stage`, { method: 'PATCH', body: JSON.stringify({ stage: nextStage, reason: stageEvidence.trim() || null }) }), 'Pipeline stage updated with its reason.')}>Update stage</button></div>}</div>
    <div className="detail-section draft-section"><h4>Follow-up message</h4><p className="small-note">Create a suggested message, edit it, then open your email app to send it yourself. The prototype never sends automatically.</p><div className="detail-pair"><span>To</span><strong>{lead.contact_email}</strong></div><div className="detail-pair"><span>Subject</span><strong>{emailSubject}</strong></div>{draftId ? <><textarea aria-label="Editable follow-up draft" rows="6" value={message} disabled={draftStatus==='sent'} onChange={event => {setMessage(event.target.value);setDraftDirty(true)}} /><div className="draft-actions"><button className="button secondary" onClick={generateDraft} disabled={working}>Create new draft</button>{draftStatus==='draft' && <button className="button secondary" onClick={saveDraft} disabled={working || !draftDirty || message.trim().length < 5}>Save changes</button>}{draftStatus==='draft' && <button className="button secondary" disabled={working || draftDirty} onClick={async()=>{await navigator.clipboard.writeText(`To: ${lead.contact_email}\nSubject: ${emailSubject}\n\n${message}`);setFeedback('Saved message copied.');}}>Copy message</button>}{draftStatus==='draft' && <a className={draftDirty?'button secondary disabled':'button primary'} href={draftDirty?undefined:`mailto:${encodeURIComponent(lead.contact_email)}?subject=${encodeURIComponent(emailSubject)}&body=${encodeURIComponent(message)}`}>Open email app ↗</a>}</div>{draftStatus==='draft' ? <div className="sent-confirm"><span>After sending in your email app:</span><button className="button secondary" disabled={working || draftDirty} onClick={markSent}>Confirm message sent</button></div> : <p className="sent-status">✓ Marked sent. Create a new draft for another follow-up.</p>}</> : <button className="button secondary" onClick={generateDraft} disabled={working}>Create suggested message</button>}{feedback && <p className="action-feedback" role="status">{feedback}</p>}</div>
  </>;
}
