import React, { useEffect, useState } from 'react';
import { api } from './api.js';
import './outreach.css';

const DEFAULTS = { reply_to: 'contact@bizsu.co', sender_name: 'Ella' };
const validEmail = value => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

export function PartnershipInsight({ company }) {
  const [analysis, setAnalysis] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setAnalysis(null); setError(''); }, [company.id]);
  const analyse = async () => {
    setBusy(true); setError('');
    try { setAnalysis(await api(`/workspace/companies/${company.id}/analyse`, { method: 'POST' })); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  return <section className="profile-section outreach-insight">
    <div className="outreach-heading"><div><h3>Partnership insight</h3><p>A possible referral angle based on the company record.</p></div><button className="ws-button secondary" disabled={busy} onClick={analyse}>{busy ? 'Analysing…' : analysis ? 'Refresh insight' : 'Analyse opportunity'}</button></div>
    {analysis && <><span className="outreach-method">{analysis.generation_method === 'llm' ? 'AI-generated' : 'Research-based suggestion'} · review required</span>{analysis.fallback_reason && <p className="outreach-hint">AI unavailable: {analysis.fallback_reason}</p>}<p><strong>Suggested opportunity:</strong> {analysis.opportunity}</p><p>{analysis.why_it_fits}</p><details><summary>Company facts and open questions</summary><ul>{analysis.verified_facts.map(fact => <li key={fact.id}><a href={fact.source_url} target="_blank" rel="noreferrer">{fact.fact} ↗</a></li>)}</ul><p><strong>Still to verify:</strong> {analysis.unknowns.join('; ')}</p></details></>}
    {error && <p className="ws-feedback" role="alert">{error}</p>}
  </section>;
}

export default function OutreachStudio({ company, detail, initialDraft, onSaved }) {
  const [contacts, setContacts] = useState(detail.contact_emails || []);
  const [toEmail, setToEmail] = useState('');
  const [contactId, setContactId] = useState('');
  const [recipientName, setRecipientName] = useState('');
  const [contactProvenance, setContactProvenance] = useState('unknown');
  const [settings, setSettings] = useState(DEFAULTS);
  const [senderName, setSenderName] = useState(DEFAULTS.sender_name);
  const [replyTo, setReplyTo] = useState(DEFAULTS.reply_to);
  const [purpose, setPurpose] = useState('Initial proposal');
  const [tone, setTone] = useState('Professional');
  const [angle, setAngle] = useState('AI recommended');
  const [style, setStyle] = useState('Short and direct');
  const [instructions, setInstructions] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [facts, setFacts] = useState([]);
  const [method, setMethod] = useState('');
  const [profileVersion, setProfileVersion] = useState(null);
  const [promptVersion, setPromptVersion] = useState(null);
  const [draftId, setDraftId] = useState(initialDraft?.id || null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState('');
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let active = true;
    api('/workspace/outreach-settings').then(value => {
      if (!active) return;
      setSettings(value);
      if (!initialDraft) { setSenderName(value.sender_name); setReplyTo(value.reply_to); }
    }).catch(error => { if (active) setNotice(error.message); });
    return () => { active = false; };
  }, [company.id]);
  useEffect(() => {
    setContacts(detail.contact_emails || []);
    if (initialDraft) {
      const meta = initialDraft.metadata || {};
      setPurpose(initialDraft.purpose); setTone(initialDraft.tone); setAngle(initialDraft.angle);
      setInstructions(initialDraft.instructions); setSubject(initialDraft.subject); setBody(initialDraft.body);
      setToEmail(meta.to_email || ''); setRecipientName(meta.recipient_name || '');
      setContactId(String((detail.contact_emails || []).find(item => item.email_address === meta.to_email)?.id || ''));
      setReplyTo(meta.reply_to || settings.reply_to); setSenderName(meta.sender_name || settings.sender_name);
      setFacts(meta.facts_used || []); setMethod(meta.generation_method || 'saved draft');
      setProfileVersion(meta.profile_version || null); setPromptVersion(meta.prompt_version || null);
      setStyle(meta.style || 'Short and direct'); setContactProvenance(meta.contact_provenance || 'staff-provided');
      setDraftId(initialDraft.id); setDirty(false);
    } else {
      const selected = detail.selected_contact;
      setToEmail(selected?.email_address || ''); setContactId(selected?.id ? String(selected.id) : '');
      setRecipientName(selected?.recipient_name || '');
      setContactProvenance(selected?.verification_status || 'unknown');
    }
  }, [company.id, initialDraft?.id]);

  const selectedContact = contacts.find(item => String(item.id) === contactId);
  const selectedLabel = selectedContact?.verification_status === 'source-confirmed' ? 'Found on company site'
    : selectedContact?.verification_status === 'unverified' ? 'Research-recorded · verify before sending'
      : contactProvenance === 'staff-provided' ? 'Staff-provided · syntax checked only' : 'No verified public email found';

  const discover = async () => {
    setBusy('discover'); setNotice('');
    try {
      const result = await api(`/workspace/companies/${company.id}/discover-contact`, { method: 'POST' });
      setContacts(result.candidates); setChecked(true);
      const current = result.candidates.find(item => item.selected);
      if (current && (!toEmail || contactProvenance === 'unverified')) {
        setToEmail(current.email_address); setContactId(String(current.id));
        setContactProvenance(current.verification_status);
      }
      setNotice(result.candidates.some(item => item.verification_status === 'source-confirmed')
        ? 'Public business email found. Check the source before use.'
        : 'No verified public email found. You can use the company website or enter an address supplied by staff.');
    } catch (error) { setNotice(error.message); }
    finally { setBusy(''); }
  };
  const chooseContact = async value => {
    if (!value) { setContactId(''); setToEmail(''); setContactProvenance('unknown'); return; }
    const item = contacts.find(contact => String(contact.id) === value);
    setBusy('contact'); setNotice('');
    try {
      const result = await api(`/workspace/companies/${company.id}/select-contact`, { method: 'POST',
        body: JSON.stringify({ contact_id: item.id, recipient_name: item.recipient_name || '' }) });
      setContacts(result.candidates); setContactId(value); setToEmail(item.email_address);
      setRecipientName(item.recipient_name || ''); setContactProvenance(item.verification_status);
      setNotice('Recipient selected. No message was sent.');
    } catch (error) { setNotice(error.message); }
    finally { setBusy(''); }
  };
  const saveRecipient = async () => {
    if (!validEmail(toEmail)) { setNotice('Enter a valid recipient address first.'); return; }
    setBusy('contact'); setNotice('');
    try {
      const existing = contacts.find(item => item.email_address === toEmail);
      const result = await api(`/workspace/companies/${company.id}/select-contact`, { method: 'POST',
        body: JSON.stringify(existing ? { contact_id: existing.id, recipient_name: recipientName }
          : { email_address: toEmail, recipient_name: recipientName }) });
      setContacts(result.candidates); setContactId(String(result.selected_contact_id));
      setContactProvenance(existing?.verification_status || 'staff-provided');
      setNotice(existing ? 'Recipient saved with its recorded source. No email was sent.'
        : 'Staff-provided recipient saved. This confirms syntax, not deliverability.');
    } catch (error) { setNotice(error.message); }
    finally { setBusy(''); }
  };
  const saveDefaults = async () => {
    if (!validEmail(replyTo) || senderName.trim().length < 2) { setNotice('Check sender name and reply-to address.'); return; }
    setBusy('settings'); setNotice('');
    try {
      const result = await api('/workspace/outreach-settings', { method: 'PUT',
        body: JSON.stringify({ ...settings, sender_name: senderName.trim(), reply_to: replyTo.trim() }) });
      setSettings(result); setNotice('Sender and reply-to defaults saved for future drafts.');
    } catch (error) { setNotice(error.message); }
    finally { setBusy(''); }
  };
  const generate = async () => {
    if (dirty && !window.confirm('Replace your unsaved edits with a new draft?')) return;
    setBusy('generate'); setNotice('');
    try {
      const result = await api(`/workspace/companies/${company.id}/generate`, { method: 'POST',
        body: JSON.stringify({ purpose, tone, angle, instructions, style, to_email: toEmail || null,
          recipient_name: recipientName, sender_name: senderName, reply_to: replyTo }) });
      setSubject(result.subject); setBody(result.body); setFacts(result.facts_used);
      setMethod(result.generation_method); setProfileVersion(result.profile_version);
      setPromptVersion(result.prompt_version); setContactProvenance(result.contact_provenance);
      setDraftId(null); setDirty(false);
      setNotice(`${result.label}.${result.fallback_reason ? ` ${result.fallback_reason}` : ''} Review the recipient, claims and company facts before use.`);
    } catch (error) { setNotice(error.message); }
    finally { setBusy(''); }
  };
  const draftPayload = () => ({ purpose, tone, angle, instructions, subject, body,
    to_email: toEmail || null, recipient_name: recipientName, reply_to: replyTo,
    sender_name: senderName, generation_method: method || 'manual', facts_used: facts,
    profile_version: profileVersion, prompt_version: promptVersion, style,
    contact_provenance: contactProvenance });
  const saveDraft = async () => {
    if (!subject.trim() || !body.trim() || !validEmail(replyTo)) { setNotice('Add a subject, message and valid reply-to address.'); return; }
    setBusy('save'); setNotice('');
    try {
      const endpoint = draftId ? `/workspace/companies/${company.id}/drafts/${draftId}` : `/workspace/companies/${company.id}/drafts`;
      const saved = await api(endpoint, { method: draftId ? 'PATCH' : 'POST', body: JSON.stringify(draftPayload()) });
      setDraftId(saved.id); setDirty(false); await onSaved();
      setNotice('Draft saved locally. No email was sent and the partner stage did not change.');
    } catch (error) { setNotice(error.message); }
    finally { setBusy(''); }
  };
  const copy = async value => {
    try { await navigator.clipboard.writeText(value); setNotice('Copied. No email was sent.'); }
    catch { setNotice('Clipboard unavailable. Select and copy the text manually.'); }
  };
  const mailto = toEmail && validEmail(toEmail) && subject && body
    ? `mailto:${encodeURIComponent(toEmail)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}` : undefined;

  return <div className="outreach-studio">
    <div className="composer-intro"><span className="ws-eyebrow">AI OUTREACH STUDIO</span><h2>Write to {company.name}</h2><p>Start with sourced work, keep the proposal short, and review every claim before sending.</p></div>
    <div className="outreach-layout">
      <div className="outreach-panel outreach-controls">
        <span className="ws-eyebrow">01 / RECIPIENT AND DIRECTION</span>
        <div className="outreach-heading"><strong>Public business email</strong><button className="ws-button secondary" disabled={!!busy} onClick={discover}>{busy === 'discover' ? 'Checking…' : 'Find contact email'}</button></div>
        <p className="outreach-hint">Checks the company’s public site on request. It never guesses an address.</p>
        {contacts.length > 0 && <label>Recorded addresses<select value={contactId} onChange={event => chooseContact(event.target.value)} disabled={!!busy}><option value="">Choose an address</option>{contacts.map(item => <option key={item.id} value={item.id}>{item.email_address} · {item.verification_status}</option>)}</select></label>}
        <label>To <span className="outreach-optional">editable</span><input type="email" value={toEmail} onChange={event => { setToEmail(event.target.value); setContactId(''); setContactProvenance('staff-provided'); }} placeholder="No verified public email found" /></label>
        <span className="outreach-provenance">{selectedLabel}{selectedContact?.source_url && <> · <a href={selectedContact.source_url} target="_blank" rel="noreferrer">Source ↗</a> · {selectedContact.retrieved_at.slice(0, 10)}</>}</span>
        {(!contacts.some(item => item.verification_status === 'source-confirmed') || checked) && !toEmail && <a className="outreach-site-link" href={company.website} target="_blank" rel="noreferrer">Use company website or contact form ↗</a>}
        <label>Recipient name <span className="outreach-optional">only if known</span><input value={recipientName} onChange={event => setRecipientName(event.target.value)} placeholder="Otherwise we’ll greet the company team" /></label>
        <button className="ws-button secondary" disabled={!!busy || !validEmail(toEmail)} onClick={saveRecipient}>Save recipient</button>
        <div className="outreach-divider" />
        <label>Purpose<select value={purpose} onChange={event => setPurpose(event.target.value)}><option>Initial proposal</option><option>Follow-up</option><option>Meeting request</option></select></label>
        <label>Tone<select value={tone} onChange={event => setTone(event.target.value)}><option>Professional</option><option>Friendly</option><option>Concise</option></select></label>
        <label>Partnership angle<select value={angle} onChange={event => setAngle(event.target.value)}><option>AI recommended</option><option>Potential referral commission</option><option>Customer value</option><option>Installation collaboration</option></select></label>
        <label>Style<select value={style} onChange={event => setStyle(event.target.value)}><option>Short and direct</option><option>Slightly detailed</option></select></label>
        <label>Optional instructions<textarea rows="3" maxLength="500" value={instructions} onChange={event => setInstructions(event.target.value)} placeholder="e.g. ask for a brief call" /></label>
        <button className="ws-button primary full" disabled={!!busy} onClick={generate}>{busy === 'generate' ? 'Generating…' : body ? 'Regenerate with AI' : 'Generate with AI'}</button>
      </div>
      <div className="outreach-panel outreach-preview">
        <span className="ws-eyebrow">02 / EMAIL READY TO REVIEW</span>
        <span className="outreach-method">{method === 'llm' ? 'AI-generated · review required' : method === 'template' ? 'Template draft — AI unavailable' : 'Editable draft · nothing sent'}</span>
        <div className="outreach-settings"><label>From name<input value={senderName} onChange={event => setSenderName(event.target.value)} /></label><label>Reply-To<input type="email" value={replyTo} onChange={event => setReplyTo(event.target.value)} /></label><button className="ws-button secondary" disabled={!!busy} onClick={saveDefaults}>Save defaults</button></div>
        <p className="outreach-hint">Your email account controls the actual sender and Reply-To header. Set Reply-To to {replyTo || 'contact@bizsu.co'} in the email client before sending.</p>
        <label>Subject<input value={subject} onChange={event => { setSubject(event.target.value); setDirty(true); }} placeholder="Generate or write a subject" /></label>
        <label>Body<textarea rows="15" value={body} onChange={event => { setBody(event.target.value); setDirty(true); }} placeholder="Generate or write an editable message" /></label>
        {facts.length > 0 && <details className="outreach-facts" open><summary>Why this email? Facts used</summary><ul>{facts.map(fact => <li key={fact.id}><a href={fact.source_url} target="_blank" rel="noreferrer">{fact.fact} ↗</a><small>{fact.provenance} · checked {fact.retrieved_on}</small></li>)}</ul></details>}
        <div className="outreach-actions"><button className="ws-button primary" disabled={!!busy || !subject.trim() || !body.trim()} onClick={saveDraft}>{busy === 'save' ? 'Saving…' : 'Save draft'}</button><button className="ws-button secondary" disabled={!toEmail} onClick={() => copy(toEmail)}>Copy recipient</button><button className="ws-button secondary" disabled={!body} onClick={() => copy(`To: ${toEmail || '(choose recipient)'}\nReply-To: ${replyTo}\nSubject: ${subject}\n\n${body}`)}>Copy draft</button><a className={`ws-button secondary ${mailto ? '' : 'disabled'}`} href={mailto}>Open email app</a></div>
        <small>Opening an email app does not send this draft or move the company to Contacted.</small>
      </div>
    </div>
    {notice && <p className="ws-feedback" role="status">{notice}</p>}
  </div>;
}
