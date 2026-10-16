import React, { useEffect, useMemo, useState } from 'react';
import { api, number, title } from './api.js';
import { stagePresentation, StatusBadge } from './stagePresentation.jsx';
import './sales.css';

const NEXT = { new: ['qualified', 'lost'], qualified: ['assessment_booked', 'lost'], assessment_booked: ['assessed', 'lost'], assessed: ['quoted', 'lost'], quoted: ['won', 'lost'], won: [], lost: [] };
const RULES = {
  new: 'Enquiry received. Screening and staff review are separate from the sales stage.',
  qualified: 'Screening passed or staff confirmed a listed area and supported AC system.',
  assessment_booked: 'An appointment was agreed. Record its date or booking confirmation.',
  assessed: 'A technical assessment was completed. Record what was checked.',
  quoted: 'A quotation was shared. Record the reference or summary.',
  won: 'The customer accepted the quotation. Record acceptance evidence.',
  lost: 'The opportunity will not proceed. Record the reason.',
};
const ACTIVE = new Set(['new', 'qualified', 'assessment_booked', 'assessed', 'quoted']);
const defaultAction = lead => ({ new: lead.qualification_status === 'needs_review' ? 'Review compatibility' : 'Move to Qualified', qualified: 'Schedule assessment', assessment_booked: 'Complete assessment', assessed: 'Prepare quotation', quoted: 'Follow up on quotation', won: 'No action required', lost: 'Closed' })[lead.stage];
const dueState = lead => {
  if (!lead.follow_up_due_at || !ACTIVE.has(lead.stage)) return 'none';
  const due = new Date(lead.follow_up_due_at);
  if (Number.isNaN(due.getTime())) return 'none';
  const today = new Date();
  return due < today ? 'overdue' : due.toDateString() === today.toDateString() ? 'today' : 'upcoming';
};
const dueLabel = value => value ? new Date(value).toLocaleString('en-SG', { dateStyle: 'medium', timeStyle: 'short' }) : 'No date set';
const localInput = value => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

export default function Sales({ leads, areas, dashboard, refresh }) {
  const params = new URLSearchParams(window.location.search);
  const linkedId = Number(params.get('lead'));
  const linked = leads.find(lead => lead.id === linkedId);
  const companies = Object.entries(dashboard.company_breakdown).filter(([, value]) => value.active_partners > 0).map(([id, value]) => ({ id, name: value.company_name })).sort((a, b) => a.name.localeCompare(b.name));
  const [tab, setTab] = useState('manage');
  const [view, setView] = useState('list');
  const [filtersOpen, setFiltersOpen] = useState(() => window.innerWidth > 650);
  const [source, setSource] = useState(linked?.data_kind === 'synthetic seeded enquiry' ? 'sample' : leads.some(lead => lead.data_kind === 'synthetic submitted enquiry') ? 'submitted' : 'all');
  const [partner, setPartner] = useState(linked?.company_id || (companies.some(item => item.id === params.get('company')) ? params.get('company') : 'all'));
  const [search, setSearch] = useState('');
  const [stage, setStage] = useState('all');
  const [review, setReview] = useState('all');
  const [owner, setOwner] = useState('all');
  const [due, setDue] = useState('all');
  const [quick, setQuick] = useState('all');
  const [selectedId, setSelectedId] = useState(linked?.id || null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');

  const scoped = useMemo(() => leads.filter(lead => (partner === 'all' || lead.company_id === partner) && (source === 'all' || (source === 'submitted' ? lead.data_kind === 'synthetic submitted enquiry' : lead.data_kind === 'synthetic seeded enquiry'))), [leads, partner, source]);
  const buckets = {
    new: lead => lead.stage === 'new',
    review: lead => lead.stage === 'new' && lead.qualification_status === 'needs_review',
    due: lead => ['overdue', 'today'].includes(dueState(lead)),
    pending: lead => ['qualified', 'assessment_booked', 'assessed', 'quoted'].includes(lead.stage),
  };
  const cards = [
    ['new', 'New enquiries', 'Recently received'], ['review', 'Needs review', 'Compatibility to confirm'],
    ['due', 'Follow-ups due', 'Today or overdue'], ['pending', 'Assessments / quotes pending', 'Work in progress'],
  ];
  const filtered = scoped.filter(lead => {
    const query = search.trim().toLowerCase().replace(/^#/, '');
    return (!query || lead.contact_name.toLowerCase().includes(query) || String(lead.id).includes(query))
      && (stage === 'all' || lead.stage === stage)
      && (review === 'all' || (review === 'needs_review' ? lead.qualification_status === 'needs_review' : review === 'passed' ? lead.qualification_status === 'qualified' : lead.review_outcome === review))
      && (owner === 'all' || (owner === 'unassigned' ? !lead.assigned_to : lead.assigned_to === owner))
      && (due === 'all' || (due === 'none' ? !lead.follow_up_due_at : dueState(lead) === due))
      && (quick === 'all' || buckets[quick](lead));
  });
  const owners = [...new Set(leads.map(lead => lead.assigned_to).filter(Boolean))].sort();
  const metrics = partner === 'all' ? dashboard : dashboard.company_breakdown[partner];
  const open = lead => {
    setSelectedId(lead.id); setDetail(null); setDetailError('');
    const query = new URLSearchParams(window.location.search);
    query.set('lead', String(lead.id));
    if (partner !== 'all') query.set('company', partner); else query.delete('company');
    window.history.replaceState({}, '', `/demo/sales?${query}`);
  };
  const close = () => {
    setSelectedId(null); setDetail(null);
    const query = new URLSearchParams(window.location.search);
    query.delete('lead');
    window.history.replaceState({}, '', `/demo/sales${query.size ? '?' + query : ''}`);
  };
  const changePartner = value => {
    setPartner(value); setQuick('all');
    const query = new URLSearchParams(window.location.search);
    if (value === 'all') query.delete('company'); else query.set('company', value);
    window.history.replaceState({}, '', `/demo/sales${query.size ? '?' + query : ''}`);
  };
  const loadDetail = async id => {
    if (!id) return;
    setDetailError('');
    try { setDetail(await api(`/leads/${id}`)); } catch (error) { setDetailError(error.message); }
  };
  useEffect(() => { loadDetail(selectedId); }, [selectedId]);
  useEffect(() => {
    if (!selectedId) return;
    const onKeyDown = event => { if (event.key === 'Escape') close(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectedId]);
  const refreshDetail = async () => { await refresh(); await loadDetail(selectedId); };

  return <main className="cp-page">
    <header className="cp-header"><div><span className="cp-eyebrow">Customer acquisition</span><h1>Customer Pipeline</h1><p>See who needs attention and move each simulated enquiry to its next action.</p></div><span className="cp-demo" title="All customer activity and outcomes are simulated. Company profiles are research prospects, not confirmed partners.">ⓘ Demo mode · simulated customer activity</span></header>
    <nav className="cp-top-tabs" aria-label="Customer Pipeline views"><button className={tab === 'manage' ? 'active' : ''} onClick={() => setTab('manage')}>Manage Enquiries</button><button className={tab === 'performance' ? 'active' : ''} onClick={() => setTab('performance')}>Performance Overview</button></nav>
    {tab === 'manage' ? <>
      <div className="cp-summary">{cards.map(([id, label, caption]) => <button key={id} className={quick === id ? 'cp-summary-card active' : 'cp-summary-card'} onClick={() => setQuick(quick === id ? 'all' : id)} aria-pressed={quick === id}><strong>{number(scoped.filter(buckets[id]).length)}</strong><span>{label}</span><small>{caption}</small></button>)}</div>
      <section className="cp-list-section"><div className="cp-section-head"><div><h2>Enquiries</h2><p>{filtered.length} matching records · all customer activity is simulated</p></div><div className="cp-view-toggle" role="group" aria-label="Enquiry view"><button className={view === 'list' ? 'active' : ''} onClick={() => setView('list')}>List</button><button className={view === 'kanban' ? 'active' : ''} onClick={() => setView('kanban')}>Kanban</button></div></div>
        <button className="cp-mobile-filter" aria-expanded={filtersOpen} onClick={() => setFiltersOpen(!filtersOpen)}>{filtersOpen ? 'Hide filters' : 'Show filters'} · {filtered.length} results</button>
        <div className={filtersOpen ? "cp-filters open" : "cp-filters"}><label>Search<input value={search} onChange={event => setSearch(event.target.value)} placeholder="Name or enquiry #" /></label><label>Partner<select value={partner} onChange={event => changePartner(event.target.value)}><option value="all">All referral sources</option>{companies.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><label>Stage<select value={stage} onChange={event => setStage(event.target.value)}><option value="all">All stages</option>{Object.entries(stagePresentation).map(([key, item]) => <option value={key} key={key}>{item.label}</option>)}</select></label><label>Review<select value={review} onChange={event => setReview(event.target.value)}><option value="all">Any review status</option><option value="needs_review">Needs review</option><option value="passed">Screening passed</option><option value="need_more_information">More information needed</option><option value="not_compatible">Not suitable</option></select></label><label>Owner<select value={owner} onChange={event => setOwner(event.target.value)}><option value="all">All owners</option><option value="unassigned">Unassigned</option>{owners.map(name => <option key={name}>{name}</option>)}</select></label><label>Due date<select value={due} onChange={event => setDue(event.target.value)}><option value="all">Any due date</option><option value="overdue">Overdue</option><option value="today">Today</option><option value="upcoming">Upcoming</option><option value="none">No date set</option></select></label><label>Records<select value={source} onChange={event => setSource(event.target.value)}><option value="submitted">Form submissions</option><option value="sample">Sample journeys</option><option value="all">All demo records</option></select></label></div>
        <details className="cp-stage-legend"><summary>Stage legend</summary><div>{Object.keys(stagePresentation).map(item => <StatusBadge key={item} value={item} />)}</div></details>
        {quick !== 'all' && <button className="cp-clear" onClick={() => setQuick('all')}>Clear “{cards.find(item => item[0] === quick)?.[1]}” filter ×</button>}
        {filtered.length ? view === 'list' ? <div className="cp-list">{filtered.map(lead => <EnquiryCard key={lead.id} lead={lead} onOpen={() => open(lead)} selected={selectedId === lead.id} />)}</div> : <div className="cp-kanban">{Object.entries(stagePresentation).map(([key, item]) => <section key={key} className="cp-column"><h3><StatusBadge value={key} /><span>{filtered.filter(lead => lead.stage === key).length}</span></h3>{filtered.filter(lead => lead.stage === key).map(lead => <EnquiryCard key={lead.id} lead={lead} onOpen={() => open(lead)} selected={selectedId === lead.id} compact />)}</section>)}</div> : <div className="cp-empty">No enquiries match these filters. Try another partner, stage, or record type.</div>}
      </section>
    </> : <Performance leads={leads} metrics={metrics} partner={partner} companies={companies} onPartner={changePartner} />}
    {selectedId && <div className="cp-drawer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) close(); }}><aside className="cp-drawer" role="dialog" aria-modal="true" aria-label={`Enquiry #${selectedId} workspace`}><button className="cp-close" onClick={close} aria-label="Close enquiry" autoFocus>×</button>{detailError ? <div className="cp-empty" role="alert">{detailError}<button onClick={() => loadDetail(selectedId)}>Retry</button></div> : detail?.id === selectedId ? <LeadWorkspace key={selectedId} lead={detail} areas={areas} refresh={refreshDetail} /> : <div className="cp-empty">Loading enquiry…</div>}</aside></div>}
  </main>;
}

function EnquiryCard({ lead, onOpen, selected, compact = false }) {
  const reviewStatus = lead.review_outcome || (lead.qualification_status === 'needs_review' ? 'needs_review' : 'qualified');
  return <article className={`cp-enquiry ${selected ? 'selected' : ''} ${compact ? 'compact' : ''}`}><div className="cp-enquiry-main"><span className="cp-avatar">{lead.contact_name.trim().split(' ').at(-1)?.slice(0, 2).toUpperCase()}</span><div><strong>{lead.contact_name} <small>#{lead.id}</small></strong><p>{lead.company_name ? `Referred via ${lead.company_name}` : 'Direct enquiry'} · {lead.property_type} · {title(lead.ac_type)} · {lead.ac_units} unit{lead.ac_units === 1 ? '' : 's'}</p></div></div><div className="cp-enquiry-status"><StatusBadge value={lead.stage} /><StatusBadge value={reviewStatus} kind="review" /></div><div className="cp-enquiry-action"><span>{lead.next_action || defaultAction(lead)}</span><small className={dueState(lead) === 'overdue' ? 'cp-overdue' : ''}>{lead.follow_up_due_at ? `Due ${dueLabel(lead.follow_up_due_at)}` : 'No due date'}{lead.assigned_to ? ` · ${lead.assigned_to}` : ''}</small></div><button className="cp-open" onClick={onOpen}>Open enquiry <span aria-hidden="true">→</span></button></article>;
}

function Performance({ leads, metrics, partner, companies, onPartner }) {
  const values = [metrics.referral_visits, metrics.submitted_enquiries, metrics.qualified_enquiries, metrics.assessments_booked, metrics.won_deals];
  const labels = ['Visits', 'Enquiries', 'Qualified', 'Assessment booked', 'Won'];
  const rates = [null, null, ...values.slice(2).map((value, index) => values[index + 1] ? `${Math.round(value / values[index + 1] * 1000) / 10}%` : '—')];
  const scoped = leads.filter(lead => partner === 'all' || lead.company_id === partner);
  const losses = scoped.filter(lead => lead.stage === 'lost');
  const reasons = losses.map(lead => lead.outcome_reason || null).filter(Boolean);
  return <section className="cp-performance"><div className="cp-section-head"><div><h2>Simulated performance</h2><p>Counts come from stored demo visits, enquiries and stage events.</p></div><label>Partner<select value={partner} onChange={event => onPartner(event.target.value)}><option value="all">All referral sources</option>{companies.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label></div><div className="cp-funnel">{labels.map((label, index) => <div key={label}><small>{String(index + 1).padStart(2, '0')} · {label}</small>{index >= 2 && <StatusBadge value={['', '', 'qualified', 'assessment_booked', 'won'][index]} />}<strong>{number(values[index])}</strong>{index === 1 && <span>Direct enquiries make a visit rate incomparable</span>}{index > 1 && <span>{rates[index]} from {labels[index - 1].toLowerCase()}</span>}</div>)}</div><div className="cp-insights"><article><h3>Closed without conversion</h3><strong>{losses.length}</strong><p>{reasons.length ? `${reasons.length} recorded outcome reason${reasons.length === 1 ? '' : 's'}` : 'No outcome reasons have been recorded.'}</p>{reasons.length > 0 && <ul>{reasons.slice(0, 5).map((reason, index) => <li key={index}>{reason}</li>)}</ul>}</article><article><h3>How to read this funnel</h3><p>Qualified counts current screening results; booked counts assessment booking events; won counts current Won records. Empty denominators display “—”.</p><p>Historical visit dates are not available for a reliable date-range filter. All company associations and outcomes are simulated.</p></article></div></section>;
}

function LeadWorkspace({ lead, areas, refresh }) {
  const [tab, setTab] = useState('overview');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const [actionForm, setActionForm] = useState(() => ({ assigned_to: lead.assigned_to || '', next_action: lead.next_action || '', follow_up_due_at: localInput(lead.follow_up_due_at), priority: lead.priority || 'normal', internal_notes: lead.internal_notes || '' }));
  const [decision, setDecision] = useState('potentially_compatible');
  const [reason, setReason] = useState('');
  const [area, setArea] = useState(areas.some(item => item.name === lead.area) ? lead.area : '');
  const [acType, setAcType] = useState(['split', 'multi_split'].includes(lead.ac_type) ? lead.ac_type : '');
  const [nextStage, setNextStage] = useState('');
  const [stageReason, setStageReason] = useState('');
  const [draft, setDraft] = useState(lead.drafts[0]?.message || '');
  const [draftId, setDraftId] = useState(lead.drafts[0]?.id || null);
  const [draftStatus, setDraftStatus] = useState(lead.drafts[0]?.status || 'draft');
  const [draftDirty, setDraftDirty] = useState(false);
  useEffect(() => { setActionForm({ assigned_to: lead.assigned_to || '', next_action: lead.next_action || '', follow_up_due_at: localInput(lead.follow_up_due_at), priority: lead.priority || 'normal', internal_notes: lead.internal_notes || '' }); setNextStage(''); setStageReason(''); }, [lead.id, lead.stage, lead.follow_up_due_at, lead.assigned_to, lead.next_action, lead.priority, lead.internal_notes]);
  const run = async (request, success) => {
    setBusy(true); setNotice(null);
    try { await request(); await refresh(); setNotice({ text: success, error: false }); }
    catch (error) { setNotice({ text: error.message, error: true }); }
    finally { setBusy(false); }
  };
  const saveAction = () => run(() => api(`/leads/${lead.id}/actions`, { method: 'PATCH', body: JSON.stringify({ ...actionForm, assigned_to: actionForm.assigned_to || null, next_action: actionForm.next_action || null, internal_notes: actionForm.internal_notes || null, follow_up_due_at: actionForm.follow_up_due_at ? new Date(actionForm.follow_up_due_at).toISOString() : null }) }), 'Next action saved.');
  const reviewLead = () => run(() => api(`/leads/${lead.id}/review`, { method: 'POST', body: JSON.stringify({ decision, reason: reason.trim(), area: area || null, ac_type: acType || null }) }), decision === 'potentially_compatible' ? 'Review recorded. Qualified is now available.' : decision === 'not_compatible' ? 'Review recorded and enquiry closed as Lost.' : 'Review recorded. Follow-up task created.');
  const moveStage = () => run(() => api(`/leads/${lead.id}/stage`, { method: 'PATCH', body: JSON.stringify({ stage: nextStage, reason: stageReason.trim() || null }) }), 'Stage updated and added to activity.');
  const createDraft = () => run(async () => { const created = await api(`/leads/${lead.id}/draft`, { method: 'POST' }); setDraftId(created.id); setDraft(created.message); setDraftStatus('draft'); setDraftDirty(false); }, 'Draft created for review.');
  const saveDraft = () => run(async () => { await api(`/drafts/${draftId}`, { method: 'PATCH', body: JSON.stringify({ message: draft }) }); setDraftDirty(false); }, 'Draft saved locally.');
  const copyDraft = async () => { try { await navigator.clipboard.writeText(`To: ${lead.contact_email}\nSubject: Your Bizsu enquiry — reference #${lead.id}\n\n${draft}`); setNotice({ text: 'Draft copied.', error: false }); } catch { setNotice({ text: 'Clipboard access is unavailable.', error: true }); } };
  const markSent = () => { if (window.confirm('Confirm you sent this message in your email app?')) run(async () => { await api(`/drafts/${draftId}/mark-sent`, { method: 'POST', body: JSON.stringify({ confirmed: true }) }); setDraftStatus('sent'); }, 'Marked sent. The pipeline stage did not change.'); };
  const reviewStatus = lead.review_outcome || (lead.qualification_status === 'needs_review' ? 'needs_review' : 'qualified');
  const stages = NEXT[lead.stage] || [];
  return <><div className="cp-workspace-head"><span className="cp-eyebrow">{lead.data_kind === 'synthetic seeded enquiry' ? 'Sample journey' : 'Form submission'} · Enquiry #{lead.id}</span><h2>{lead.contact_name}</h2><p>{lead.company_name ? `Referred via ${lead.company_name} (demo)` : 'Direct enquiry'}</p><div className="cp-badges"><StatusBadge value={lead.stage} /><StatusBadge value={reviewStatus} kind="review" /></div></div><nav className="cp-detail-tabs" aria-label="Enquiry details">{['overview', 'activity', 'followup'].map(item => <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item === 'followup' ? 'Follow-up' : item[0].toUpperCase() + item.slice(1)}</button>)}</nav>{notice && <div className={notice.error ? 'cp-notice error' : 'cp-notice'} role="status">{notice.text}</div>}
    {tab === 'overview' && <div className="cp-detail-body"><div className="cp-next"><small>Next recommended action</small><strong>{lead.next_action || defaultAction(lead)}</strong><span>{lead.follow_up_due_at ? `Due ${dueLabel(lead.follow_up_due_at)}` : 'Set an owner and follow-up date below.'}</span>{lead.stage === 'new' && lead.qualification_status === 'needs_review' && <button onClick={() => document.getElementById(`review-${lead.id}`)?.scrollIntoView({ behavior: 'smooth' })}>Review compatibility ↓</button>}{ACTIVE.has(lead.stage) && !(lead.stage === 'new' && lead.qualification_status === 'needs_review') && <button onClick={() => document.getElementById(`stage-${lead.id}`)?.scrollIntoView({ behavior: 'smooth' })}>Continue to stage action ↓</button>}</div><section><h3>Homeowner and referral</h3><dl className="cp-facts"><div><dt>Email</dt><dd>{lead.contact_email}</dd></div><div><dt>Phone</dt><dd>{lead.contact_phone || 'Not provided'}</dd></div><div><dt>Referral</dt><dd>{lead.company_name ? `${lead.company_name} · ${lead.referral_code}` : 'Direct enquiry'}</dd></div><div><dt>Housing / area</dt><dd>{lead.property_type} · {lead.area}</dd></div><div><dt>AC / usage</dt><dd>{title(lead.ac_type)} · {lead.ac_units} unit{lead.ac_units === 1 ? '' : 's'} · {lead.daily_hours} hours daily</dd></div></dl>{lead.enquiry_note && <p className="cp-note"><b>Homeowner note</b><br />{lead.enquiry_note}</p>}<p className="cp-caveat">All referral associations shown here are simulated; real company profiles do not imply a partnership.</p></section><section><h3>Screening</h3><StatusBadge value={reviewStatus} kind="review" /><ul className="cp-reasons">{lead.qualification_reasons.map((item, index) => <li key={index}>{item}</li>)}</ul>{lead.reviewed_at && <p className="cp-muted">Latest review: {dueLabel(lead.reviewed_at)} · {lead.review_notes}</p>}{lead.confirmed_area && <p className="cp-muted">Staff confirmed: {lead.confirmed_area} · {title(lead.confirmed_ac_type)}</p>}</section>
      {lead.stage === 'new' && lead.qualification_status === 'needs_review' && <section id={`review-${lead.id}`} className="cp-review"><h3>Compatibility Review</h3><p>The recorded screening reasons above explain what needs confirmation. The homeowner’s original answers remain in the section above.</p><label>Review decision<select value={decision} onChange={event => setDecision(event.target.value)}><option value="potentially_compatible">Potentially compatible</option><option value="need_more_information">Need more information</option><option value="not_compatible">Not compatible</option></select></label>{decision === 'potentially_compatible' && <div className="cp-two"><label>Confirmed planning area<select value={area} onChange={event => setArea(event.target.value)}><option value="">Select listed area</option>{areas.filter(item => item.name !== 'Others').map(item => <option key={item.name}>{item.name}</option>)}</select></label><label>Confirmed AC system<select value={acType} onChange={event => setAcType(event.target.value)}><option value="">Select supported system</option><option value="split">Split unit</option><option value="multi_split">Multi-split</option></select></label></div>}<label>What did staff confirm?<textarea rows="3" maxLength="500" value={reason} onChange={event => setReason(event.target.value)} placeholder="Write at least 10 characters explaining the decision." /></label><p className="cp-muted">Potentially compatible unlocks Qualified only when the backend eligibility rules pass. More information creates a follow-up task. Not compatible closes as Lost.</p><button className="cp-primary" disabled={busy || reason.trim().length < 10 || (decision === 'potentially_compatible' && (!area || !acType))} onClick={reviewLead}>Confirm after review</button></section>}
      <section><h3>Next action and owner</h3><div className="cp-two"><label>Owner<input value={actionForm.assigned_to} maxLength="80" onChange={event => setActionForm({ ...actionForm, assigned_to: event.target.value })} placeholder="Staff name" /></label><label>Priority<select value={actionForm.priority} onChange={event => setActionForm({ ...actionForm, priority: event.target.value })}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label></div><label>Next action<input value={actionForm.next_action} maxLength="200" onChange={event => setActionForm({ ...actionForm, next_action: event.target.value })} placeholder="What should happen next?" /></label><label>Follow-up due<input type="datetime-local" value={actionForm.follow_up_due_at} onChange={event => setActionForm({ ...actionForm, follow_up_due_at: event.target.value })} /></label><label>Internal notes<textarea rows="3" maxLength="3000" value={actionForm.internal_notes} onChange={event => setActionForm({ ...actionForm, internal_notes: event.target.value })} /></label><button className="cp-secondary" disabled={busy} onClick={saveAction}>Save next action</button></section><section id={`stage-${lead.id}`}><h3>Move to next stage</h3>{stages.length ? <><label>Stage<select value={nextStage} onChange={event => { setNextStage(event.target.value); setStageReason(''); }}><option value="">Choose a stage</option>{stages.map(item => <option value={item} key={item} disabled={item === 'qualified' && lead.qualification_status !== 'qualified'}>{stagePresentation[item].label}{item === 'qualified' && lead.qualification_status !== 'qualified' ? ' · review first' : ''}</option>)}</select></label>{lead.stage === 'new' && lead.qualification_status !== 'qualified' && <p className="cp-muted">Confirm compatibility review before choosing Qualified.</p>}{nextStage && <p className="cp-muted">{RULES[nextStage]}</p>}{nextStage && nextStage !== 'qualified' && <label>Evidence or outcome reason<textarea rows="2" maxLength="500" value={stageReason} onChange={event => setStageReason(event.target.value)} placeholder="At least 10 characters" /></label>}<button className="cp-secondary" disabled={busy || !nextStage || (nextStage !== 'qualified' && stageReason.trim().length < 10)} onClick={moveStage}>Update stage</button></> : <p className="cp-muted">This enquiry is closed. Stage history remains available in Activity.</p>}</section></div>}
    {tab === 'activity' && <div className="cp-detail-body"><section><h3>Activity timeline</h3><ol className="cp-timeline">{[...lead.stage_events.map(event => ({ id: `stage-${event.id}`, at: event.created_at, stage: event.to_stage, detail: event.reason || 'No reason recorded.' })), ...lead.activity.map(event => ({ id: `activity-${event.id}`, at: event.created_at, kind: event.kind, detail: event.detail }))].sort((a, b) => new Date(b.at) - new Date(a.at)).map(event => <li key={event.id}><span className="cp-timeline-dot" /><div><small>{dueLabel(event.at)}</small><strong>{event.stage ? <StatusBadge value={event.stage} /> : event.kind === 'review' ? 'Compatibility review' : event.kind === 'screening' ? 'Initial screening' : 'Follow-up updated'}</strong><p>{event.detail}</p></div></li>)}</ol></section><details className="cp-rules"><summary>Why this stage? View all stage criteria</summary>{Object.entries(RULES).map(([key, rule]) => <p key={key}><StatusBadge value={key} /> {rule}</p>)}</details>{lead.data_kind === 'synthetic seeded enquiry' && <p className="cp-caveat">Seeded journey stages are illustrative and do not represent actual bookings, quotes, or sales.</p>}</div>}
    {tab === 'followup' && <div className="cp-detail-body"><section><h3>Follow-up message</h3><p className="cp-muted">Drafts are local and unsent. Review the message, then open your email app to send it manually.</p><dl className="cp-facts"><div><dt>To</dt><dd>{lead.contact_email}</dd></div><div><dt>Subject</dt><dd>Your Bizsu enquiry — reference #{lead.id}</dd></div></dl>{draftId ? <><label>Message<textarea rows="10" value={draft} disabled={draftStatus === 'sent'} onChange={event => { setDraft(event.target.value); setDraftDirty(true); }} /></label><div className="cp-draft-actions"><button className="cp-secondary" onClick={createDraft} disabled={busy}>Create new draft</button>{draftStatus === 'draft' && <><button className="cp-secondary" disabled={busy || !draftDirty || draft.trim().length < 5} onClick={saveDraft}>Save changes</button><button className="cp-secondary" disabled={busy || draftDirty} onClick={copyDraft}>Copy draft</button><a className={draftDirty ? 'cp-secondary disabled' : 'cp-primary'} href={draftDirty ? undefined : `mailto:${encodeURIComponent(lead.contact_email)}?subject=${encodeURIComponent(`Your Bizsu enquiry — reference #${lead.id}`)}&body=${encodeURIComponent(draft)}`}>Open email app ↗</a></> }</div>{draftStatus === 'draft' ? <button className="cp-text-button" disabled={busy || draftDirty} onClick={markSent}>I sent this message in my email app</button> : <p className="cp-muted">Marked sent. Create a new draft for another follow-up.</p>}</> : <button className="cp-primary" disabled={busy} onClick={createDraft}>Create suggested draft</button>}</section></div>}
  </>;
}
