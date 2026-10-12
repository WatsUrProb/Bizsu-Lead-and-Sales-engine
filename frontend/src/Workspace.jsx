import React, { useEffect, useMemo, useState } from 'react';
import { api } from './api.js';

const fields = ['name','website','residential_evidence','maintenance','installation','coverage','contact','source','retrieved_on','unknowns'];
const emptyCompany = {name:'',website:'https://',residential_evidence:'',maintenance:'Unverified',installation:'unverified',coverage:'Unverified',contact:'Unverified',source:'https://',retrieved_on:new Date().toISOString().slice(0,10),unknowns:''};
const labels = {residential:'Residential relevance',maintenance:'Recurring maintenance',coverage:'Geographic coverage',installation:'Installation capability'};
const stages = ['Discovered','Shortlisted','Contacted','Interested','Negotiating','Onboarded','Rejected / Archived'];
const scoreFor = (c,w) => {
  const present = {residential:!/unclear|unverified/i.test(c.residential_evidence),maintenance:!/^unverified$/i.test(c.maintenance),coverage:/islandwide|homes across singapore/i.test(c.coverage),installation:c.installation==='yes'};
  const total = Object.values(w).reduce((a,b)=>a+Number(b||0),0) || 1;
  const contributions = Object.fromEntries(Object.keys(labels).map(k=>[k,present[k]?Math.round(Number(w[k]||0)*100/total):0]));
  return {value:Object.values(contributions).reduce((a,b)=>a+b,0),present,contributions};
};
const fitLabel = score => score>=75?'Strong match':score>=50?'Promising match':'Needs more evidence';
const pilotTier = {contact_first:'Contact first',backup_pilot:'Backup pilot',scale_stage:'Later stage',alternative_channel:'Alternative channel'};

function PilotResearch({research}) {
  if (!research) return null;
  return <section className="profile-section pilot-insight">
    <h3>Pilot recommendation <span>#{research.rank} · {pilotTier[research.tier]}</span></h3>
    <p className="pilot-idea">{research.idea}</p>
    <p>{research.rationale}</p>
    <details className="profile-accordion"><summary>Research sources</summary><ul>{research.evidence.map(item=><li key={item.url}><a href={item.url} target="_blank" rel="noreferrer">{item.label} ↗</a></li>)}</ul><small>Checked {research.retrieved_on}. Confirm current details before outreach.</small></details>
    <small>Internal research recommendation only. No partnership interest or endorsement is implied.</small>
  </section>;
}

export default function Workspace({page,navigate}) {
  const [data,setData] = useState(null);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const [notice,setNotice] = useState('');
  const [query,setQuery] = useState('');
  const [filter,setFilter] = useState('All prospects');
  const [sort,setSort] = useState('score');
  const [selected,setSelected] = useState(null);
  const [mode,setMode] = useState('');
  const [detail,setDetail] = useState(null);
  const [form,setForm] = useState(emptyCompany);
  const [weights,setWeights] = useState(null);
  const [weightsOpen,setWeightsOpen] = useState(false);
  const [purpose,setPurpose] = useState('Initial proposal');
  const [tone,setTone] = useState('Professional');
  const [angle,setAngle] = useState('Potential referral commission');
  const [instructions,setInstructions] = useState('');
  const [subject,setSubject] = useState('');
  const [body,setBody] = useState('');
  const [facts,setFacts] = useState([]);
  const [dirty,setDirty] = useState(false);
  const [pipelineNote,setPipelineNote] = useState('');
  const [followUp,setFollowUp] = useState('');
  const [mobileStage,setMobileStage] = useState('Discovered');

  const refresh = async () => {
    const next = await api('/workspace');
    setData(next); setWeights(current=>current||next.weights);
    return next;
  };
  useEffect(()=>{refresh().catch(e=>setError(e.message));},[]);
  const openCompany = async (id,nextMode='profile') => {
    setSelected(id); setMode(nextMode); setNotice('');
    try { const item=await api(`/workspace/companies/${id}`); setDetail(item); setPipelineNote(item.note||''); setFollowUp(item.follow_up||''); }
    catch(e){setError(e.message);}
  };
  const close = () => {setMode('');setSelected(null);setDetail(null);setNotice('');};
  const action = async (fn,success) => {
    setBusy(true);setNotice('');
    try {await fn();await refresh(); if(selected) setDetail(await api(`/workspace/companies/${selected}`));setNotice(success);}
    catch(e){setNotice(e.message);}finally{setBusy(false);}
  };
  const openForm = item => {setForm(item?Object.fromEntries(fields.map(k=>[k,item[k]])):emptyCompany);setSelected(item?.id||null);setMode('form');setNotice('');};
  const submitForm = async event => {
    event.preventDefault();setBusy(true);setNotice('');
    try {const result=await api(selected?`/workspace/companies/${selected}`:'/workspace/companies', {method:selected?'PUT':'POST',body:JSON.stringify(form)});await refresh();await openCompany(result.id);setNotice(selected?'Company updated.':'Company added.');}
    catch(e){setNotice(e.message);}finally{setBusy(false);}
  };
  const changeStage = async (c,stage,force=false) => {
    if(stage===c.stage&&!force)return;
    let confirmed=false;
    if(stage!==c.stage&&stage==='Contacted') {confirmed=window.confirm('Confirm actual outreach was sent to this company? A saved or copied draft does not count.');if(!confirmed)return;}
    if(stage!==c.stage&&stage==='Onboarded') {confirmed=window.confirm('Confirm that Bizsu has an actual agreement with this company?');if(!confirmed)return;}
    const note = selected===c.id ? pipelineNote : c.note||'';
    const date = selected===c.id ? followUp : c.follow_up||null;
    await action(()=>api(`/workspace/companies/${c.id}/stage`,{method:'POST',body:JSON.stringify({stage,note,follow_up:date,confirmed})}),stage===c.stage?'Note and date saved.':`${c.name} moved to ${stage}.`);
  };
  const openComposer = async c => {await openCompany(c.id,'composer');setSubject('');setBody('');setFacts([]);setDirty(false);};
  const generate = async () => {
    if(dirty && !window.confirm('Replace your unsaved changes with a new draft?'))return;
    setBusy(true);setNotice('');
    try {const result=await api(`/workspace/companies/${selected}/generate`,{method:'POST',body:JSON.stringify({purpose,tone,angle,instructions})});setSubject(result.subject);setBody(result.body);setFacts(result.facts_used);setDirty(false);setNotice('Template generated from the company record. Nothing was sent.');}
    catch(e){setNotice(e.message);}finally{setBusy(false);}
  };
  const saveDraft = () => action(()=>api(`/workspace/companies/${selected}/drafts`,{method:'POST',body:JSON.stringify({purpose,tone,angle,instructions,subject,body})}),'Draft saved. The company remains in its current stage.');
  const list = data?.companies||[];
  const scored = useMemo(()=>list.map(c=>({...c,fit:scoreFor(c,weights||data?.weights||{})})),[list,weights,data?.weights]);
  const visible = scored.filter(c=>{
    const match=(c.name+' '+c.residential_evidence+' '+c.coverage).toLowerCase().includes(query.toLowerCase());
    const condition=filter==='All prospects'||(filter==='Pilot reviewed'&&!!c.pilot_research)||(filter==='Shortlisted'&&c.stage==='Shortlisted')||(filter==='Recurring maintenance'&&c.fit.present.maintenance)||(filter==='Residential'&&c.fit.present.residential)||(filter==='Installation'&&c.fit.present.installation)||(filter==='Coverage stated'&&c.fit.present.coverage);
    return match&&condition;
  }).sort((a,b)=>sort==='name'?a.name.localeCompare(b.name):sort==='pilot'?(a.pilot_research?.rank??Infinity)-(b.pilot_research?.rank??Infinity)||a.name.localeCompare(b.name):b.fit.value-a.fit.value||a.name.localeCompare(b.name));
  const count = stage => scored.filter(c=>c.stage===stage).length;
  if(error&&!data)return <div className="ws-state"><h2>Could not load partner workspace</h2><p>{error}</p><button className="ws-button primary" onClick={()=>refresh().catch(e=>setError(e.message))}>Retry</button></div>;
  if(!data)return <div className="ws-state">Loading partner prospects…</div>;
  const current = scored.find(c=>c.id===selected);
  return <div className="ws-content">
    {notice&&!mode&&<div className="ws-feedback global-feedback" role="status">{notice}<button onClick={()=>setNotice('')} aria-label="Dismiss message">×</button></div>}
    {page==='discover' && <>
      <div className="ws-hero"><div><span className="ws-eyebrow">PARTNER DISCOVERY</span><h1>Find your next<br/><em>referral partner.</em></h1><p>Find a relevant aircon service company, check the evidence, then decide whether to approach them.</p><div className="hero-steps"><span><b>1</b> Explore</span><span>→</span><span><b>2</b> Shortlist</span><span>→</span><span><b>3</b> Draft outreach</span></div></div><div className="hero-art" aria-hidden="true"><div className="art-back"/><div className="art-card one"><span className="art-line short"/><span className="art-line"/><span className="art-line medium"/></div><div className="art-card two"><span className="art-circle">✓</span><span className="art-line medium"/><span className="art-line short"/></div><div className="art-orbit">✦</div></div></div>
      <div className="ws-trust"><span className="trust-icon">i</span><div><strong>Prospective companies only — no partnership is implied.</strong><small>Service details come from public company pages reviewed 11–12 Oct 2026. Unknowns stay marked unverified.</small></div></div>
      <div className="ws-section-head"><div><span className="ws-eyebrow">EXPLORE THE LIST</span><h2>Companies to consider <span>{list.length}</span></h2><p>Start with published services. Open a company for sources, unknowns and next steps.</p></div><button className="ws-button primary" onClick={()=>openForm(null)}>＋ Add company</button></div>
      <div className="ws-toolbar"><label className="ws-search"><span aria-hidden="true">⌕</span><input aria-label="Search companies" placeholder="Search company, service or area…" value={query} onChange={e=>setQuery(e.target.value)}/></label><select aria-label="Sort companies" value={sort} onChange={e=>setSort(e.target.value)}><option value="score">Sort: strongest match</option><option value="pilot">Sort: pilot priority</option><option value="name">Sort: company name</option></select></div>
      <div className="filter-chips">{['All prospects','Pilot reviewed','Residential','Recurring maintenance','Installation','Coverage stated','Shortlisted'].map(item=><button key={item} className={filter===item?'active':''} onClick={()=>setFilter(item)}>{item}</button>)}<button className="clear-chip" onClick={()=>{setFilter('All prospects');setQuery('');}}>Clear filters</button></div>
      <div className="result-note">Showing {visible.length} of {list.length} companies</div>
      {visible.length?<div className="company-grid">{visible.map(c=><article className="company-card" key={c.id}><div className="card-top"><span className="company-avatar">{c.name.slice(0,1)}</span><span className="origin-badge">{c.pilot_research?`Pilot #${c.pilot_research.rank}`:c.origin==='Public research'?'Public prospect':'User-entered'}</span></div><h3>{c.name}</h3><p>{c.residential_evidence}.</p><div className="tag-row"><span>Residential: {c.fit.present.residential?'published':'unverified'}</span><span>Maintenance: {c.fit.present.maintenance?'published':'unverified'}</span><span>Installation: {c.installation==='yes'?'listed':c.installation}</span></div><div className="card-bottom"><div><strong>{fitLabel(c.fit.value)}</strong><small>{c.fit.value}/100 · published service fit</small></div><button className="card-arrow" aria-label={`View ${c.name}`} onClick={()=>openCompany(c.id)}>↗</button></div><div className="card-actions"><button onClick={()=>openCompany(c.id)}>View company</button><button onClick={()=>c.stage==='Shortlisted'?openComposer(c):changeStage(c,'Shortlisted')}>{c.stage==='Shortlisted'?'Draft email':'Shortlist'}</button></div></article>)}</div>:<div className="ws-empty"><h3>No matching companies</h3><p>Try a different search or clear filters to see the full prospect list.</p><button className="ws-button secondary" onClick={()=>{setFilter('All prospects');setQuery('');}}>Clear filters</button></div>}
    </>}
    {page==='pipeline' && <><div className="ws-page-head"><span className="ws-eyebrow">PARTNER ACQUISITION</span><h1>Pipeline</h1><p>Move companies as real conversations progress. Drafts alone never mark outreach as sent.</p></div><div className="ws-trust slim"><span className="trust-icon">i</span><div><strong>Real prospects are unconfirmed.</strong><small>Contacted and Onboarded require explicit confirmation of actual outreach or agreement.</small></div></div><div className="mobile-stage"><label>Show stage <select value={mobileStage} onChange={e=>setMobileStage(e.target.value)}>{stages.map(s=><option key={s}>{s}</option>)}</select></label></div><div className="kanban-scroll"><div className="kanban-board">{stages.map(stage=><div className={`kanban-column ${mobileStage===stage?'mobile-visible':''}`} key={stage}><header><span>{stage}</span><b>{count(stage)}</b></header>{scored.filter(c=>c.stage===stage).map(c=><article className="kanban-card" key={c.id}><button className="kanban-title" onClick={()=>openCompany(c.id)}>{c.name} ↗</button><p>{c.residential_evidence}</p><div className="kanban-meta"><span>{fitLabel(c.fit.value)}</span>{c.follow_up&&<span>Follow up {c.follow_up}</span>}</div><div className="kanban-actions"><button onClick={()=>openComposer(c)}>Draft email</button><select aria-label={`Move ${c.name} to stage`} value={c.stage} onChange={e=>changeStage(c,e.target.value)}>{stages.map(s=><option key={s}>{s}</option>)}</select></div></article>)}{!count(stage)&&<div className="column-empty">{stage==='Shortlisted'?'Shortlist a company from Discover.':'No companies here yet.'}</div>}</div>)}</div></div></>}
    {page==='drafts' && <><div className="ws-page-head"><span className="ws-eyebrow">OUTREACH</span><h1>Saved drafts</h1><p>Review saved proposals before any real outreach. Drafting does not change a company’s pipeline stage.</p></div><div className="draft-list">{scored.filter(c=>c.draft_count).map(c=><button className="draft-list-row" key={c.id} onClick={()=>openCompany(c.id)}><span className="company-avatar">{c.name[0]}</span><span><strong>{c.name}</strong><small>{c.draft_count} saved draft{c.draft_count!==1?'s':''} · {c.stage}</small></span><span>View drafts ↗</span></button>)}</div>{!scored.some(c=>c.draft_count)&&<div className="ws-empty"><h3>No drafts saved yet</h3><p>Open a company in Discover and generate a tailored proposal.</p><button className="ws-button primary" onClick={()=>navigate('discover')}>Explore companies</button></div>}</>}
    {mode&&<div className="drawer-backdrop" onMouseDown={e=>e.target===e.currentTarget&&close()}><section className="ws-drawer" role="dialog" aria-modal="true" aria-label={mode==='form'?'Company form':current?.name||'Company details'}><div className="drawer-top"><span>{mode==='form'?(selected?'EDIT COMPANY':'ADD COMPANY'):mode==='composer'?'TAILORED OUTREACH':'COMPANY PROFILE'}</span><button onClick={close} aria-label="Close panel">×</button></div>
      {mode==='form'?<form className="company-form" onSubmit={submitForm}><h2>{selected?'Edit company':'Add a company'}</h2><p>Record what the source actually says. Use “Unverified” for unknown attributes.</p>{fields.map(key=><label key={key}>{({name:'Company name',website:'Website URL',residential_evidence:'Residential service evidence',maintenance:'Recurring maintenance',installation:'Installation capability',coverage:'Coverage',contact:'Public contact method',source:'Evidence source URL',retrieved_on:'Research date',unknowns:'Unknowns to verify'})[key]}{key==='installation'?<select value={form[key]} onChange={e=>setForm({...form,[key]:e.target.value})}><option value="yes">Listed</option><option value="no">Not offered</option><option value="unverified">Unverified</option></select>:key==='residential_evidence'||key==='unknowns'?<textarea rows="3" value={form[key]} onChange={e=>setForm({...form,[key]:e.target.value})}/>:<input type={key==='retrieved_on'?'date':key==='website'||key==='source'?'url':'text'} required={!['unknowns'].includes(key)} value={form[key]} onChange={e=>setForm({...form,[key]:e.target.value})}/>}</label>)}<div className="drawer-actions"><button className="ws-button primary" disabled={busy}>{busy?'Saving…':'Save company'}</button><button type="button" className="ws-button secondary" onClick={close}>Cancel</button></div>{notice&&<p className="ws-feedback" role="status">{notice}</p>}</form>:current&&detail&&<div className="drawer-body">
        {mode==='profile'?<><div className="profile-head"><span className="origin-badge">{current.origin==='Public research'?'Public prospect':'User-entered'}</span><h2>{current.name}</h2><p>{current.residential_evidence}.</p><div className="profile-score"><strong>{current.fit.value}<small>/100</small></strong><div><b>{fitLabel(current.fit.value)}</b><span>Based on published services, not partnership interest</span></div></div></div><div className="drawer-actions sticky"><button className="ws-button primary" onClick={()=>openComposer(current)}>Generate tailored email →</button><button className="ws-button secondary" onClick={()=>changeStage(current,'Shortlisted')}>{current.stage==='Shortlisted'?'Shortlisted ✓':'Shortlist'}</button></div><section className="profile-section"><h3>Why Bizsu might approach them</h3><ul><li>{current.residential_evidence}</li>{current.fit.present.maintenance&&<li>Published {current.maintenance.toLowerCase()} offering could support repeat customer conversations.</li>}{current.installation==='yes'&&<li>Installation is listed among their services; any collaboration requires technical approval.</li>}</ul></section><PilotResearch research={current.pilot_research}/><section className="profile-section"><h3>At a glance</h3><div className="fact-list"><div><span>Maintenance</span><b>{current.maintenance}</b></div><div><span>Coverage</span><b>{current.coverage}</b></div><div><span>Installation</span><b>{current.installation==='yes'?'Listed':current.installation}</b></div><div><span>Public contact</span><b>{current.contact}</b></div><div><span>Pipeline</span><b>{current.stage}</b></div></div></section><details className="profile-accordion"><summary>Evidence and unknowns</summary><p><b>Source:</b> <a href={current.source} target="_blank" rel="noreferrer">View company page ↗</a></p><p><b>Reviewed:</b> {current.retrieved_on}</p><p><b>Still to verify:</b> {current.unknowns||'Partnership interest and current service details'}</p><p>Published packages do not establish customer retention or willingness to partner.</p></details><details className="profile-accordion"><summary>Why this match? · scoring settings</summary><p>Transparent weighted business rubric. Unknowns receive no points until verified.</p>{Object.keys(labels).map(k=><div className="weight-row" key={k}><span>{labels[k]}</span><b>{current.fit.present[k]?`${current.fit.contributions[k]} points`:'Unverified'}</b></div>)}<button className="inline-button" onClick={()=>setWeightsOpen(!weightsOpen)}>{weightsOpen?'Hide':'Edit'} scoring weights</button>{weightsOpen&&<div className="weights-panel">{Object.keys(labels).map(k=><label key={k}>{labels[k]} <input type="number" min="0" max="100" value={weights[k]} onChange={e=>setWeights({...weights,[k]:Number(e.target.value)})}/></label>)}<small>Total: {Object.values(weights).reduce((a,b)=>a+Number(b||0),0)}%. Save when total is 100%.</small><button className="ws-button secondary" disabled={busy||Object.values(weights).reduce((a,b)=>a+Number(b||0),0)!==100} onClick={()=>action(()=>api('/workspace/weights',{method:'PUT',body:JSON.stringify(weights)}),'Scoring weights saved.')}>Save weights</button></div>}</details><section className="profile-section"><h3>Next action and follow-up</h3><label className="small-label">Move to stage<select value={current.stage} onChange={e=>changeStage(current,e.target.value)}>{stages.map(s=><option key={s}>{s}</option>)}</select></label><label className="small-label">Internal note<textarea rows="3" value={pipelineNote} onChange={e=>setPipelineNote(e.target.value)}/></label><label className="small-label">Follow-up date<input type="date" value={followUp} onChange={e=>setFollowUp(e.target.value)}/></label><button className="ws-button secondary" onClick={()=>changeStage(current,current.stage,true)}>Save note and date</button></section><section className="profile-section"><h3>Saved drafts <span>{detail.drafts?.length||0}</span></h3>{detail.drafts?.map(d=><details className="saved-draft" key={d.id}><summary>{d.subject} <small>{d.updated_at.slice(0,10)}</small></summary><p className="draft-body-text">{d.body}</p><button className="inline-button" onClick={()=>{setPurpose(d.purpose);setTone(d.tone);setAngle(d.angle);setInstructions(d.instructions);setSubject(d.subject);setBody(d.body);setMode('composer');setDirty(false);}}>Open in composer</button></details>)}{!detail.drafts?.length&&<p className="muted">No draft yet. Generate one using the company facts above.</p>}</section><button className="inline-button" onClick={()=>openForm(current)}>Edit company details</button>{detail.events?.length>0&&<details className="profile-accordion"><summary>Stage history</summary>{detail.events.map(e=><p key={e.id}>{e.from_stage} → {e.to_stage} · {e.occurred_at.slice(0,10)}{e.note&&` · ${e.note}`}</p>)}</details>}</>:<div className="composer"><div className="composer-intro"><h2>Write to {current.name}</h2><p>Start with verified service details. Review and edit before using the draft.</p></div><div className="composer-grid"><div className="composer-controls"><span className="ws-eyebrow">01 / PERSONALISE</span><label>Purpose<select value={purpose} onChange={e=>setPurpose(e.target.value)}><option>Initial proposal</option><option>Follow-up</option><option>Meeting request</option></select></label><label>Tone<select value={tone} onChange={e=>setTone(e.target.value)}><option>Professional</option><option>Friendly</option><option>Concise</option></select></label><label>Partnership angle<select value={angle} onChange={e=>setAngle(e.target.value)}><option value="Potential referral commission">Potential referral commission · terms to agree</option><option value="Customer value">Additional customer value</option><option value="Installation collaboration">Installation collaboration · approval needed</option></select></label><label>Notes for your review<textarea value={instructions} onChange={e=>setInstructions(e.target.value)} rows="3" placeholder="Optional internal guidance"/></label><div className="facts-box"><b>Company facts available</b><p>{current.residential_evidence}</p><p>{current.maintenance}</p><a href={current.source} target="_blank" rel="noreferrer">Review source ↗</a></div><button className="ws-button primary full" onClick={generate} disabled={busy}>{busy?'Generating…':body?'Regenerate draft':'Generate tailored email'}</button></div><div className="composer-preview"><span className="ws-eyebrow">02 / YOUR DRAFT</span><div className="template-tag">Template-generated · never auto-sent</div><label>Subject<input value={subject} onChange={e=>{setSubject(e.target.value);setDirty(true)}} placeholder="Generate a draft to begin"/></label><label>Message<textarea rows="17" value={body} onChange={e=>{setBody(e.target.value);setDirty(true)}} placeholder="Your editable email appears here"/></label>{facts.length>0&&<p className="used-facts"><b>Personalised using:</b> {facts.join(' · ')}</p>}<div className="composer-actions"><button className="ws-button primary" disabled={!subject||!body||busy} onClick={saveDraft}>Save draft</button><button className="ws-button secondary" disabled={!body} onClick={async()=>{await navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`);setNotice('Draft copied. No outreach status changed.')}}>Copy</button><a className={`ws-button secondary ${!body?'disabled':''}`} href={body?`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`:undefined}>Open in email app</a></div><small>Opening an email app does not mark this company Contacted.</small></div></div></div>}{notice&&<p className="ws-feedback" role="status">{notice}</p>}</div>}
    </section></div>}
  </div>;
}
