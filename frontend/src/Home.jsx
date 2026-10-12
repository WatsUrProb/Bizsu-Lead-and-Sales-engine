import React, { useEffect, useState } from 'react';
import { api } from './api.js';

const PROPERTY_TYPES = ['HDB 1–2 room', 'HDB 3 room', 'HDB 4 room', 'HDB 5 room/executive', 'Condo/apartment', 'Landed'];
const emptyForm = { area: 'Ang Mo Kio', property_type: 'HDB 4 room', ac_type: 'split', ac_units: 2, daily_hours: 6, estimated_ac_spend: '', contact_name: 'Demo Homeowner', contact_email: 'homeowner@example.test', consent: false };

export default function Home({ areas, partners, navigate, onSubmitted }) {
  const ref = new URLSearchParams(window.location.search).get('ref');
  const partner = partners.find(item => item.referral_code === ref);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(null);

  useEffect(() => {
    if (!ref || !partner) return;
    const key = `bizsu-referral-${ref}`;
    let sessionId = sessionStorage.getItem(key);
    if (!sessionId) {
      sessionId = crypto.randomUUID();
      sessionStorage.setItem(key, sessionId);
    }
    api('/referral-visits', { method: 'POST', body: JSON.stringify({ referral_code: ref, session_id: sessionId }) }).catch(() => {});
  }, [ref, partner?.id]);

  const change = event => {
    const { name, value, type, checked } = event.target;
    setForm(current => ({ ...current, [name]: type === 'checkbox' ? checked : value }));
  };
  const submit = async event => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const payload = {
        ...form,
        referral_code: ref || null,
        ac_units: Number(form.ac_units),
        daily_hours: Number(form.daily_hours),
        estimated_ac_spend: form.estimated_ac_spend === '' ? null : Number(form.estimated_ac_spend),
      };
      const lead = await api('/leads', { method: 'POST', body: JSON.stringify(payload) });
      setSubmitted(lead);
      await onSubmitted();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return <>
    <section className="page-intro home-intro"><span className="eyebrow">02 / Demo enquiry</span><h1>Try a referral.<br /><em>See what happens.</em></h1><p>Submit fictional AC details to see screening and company attribution. Nothing is sent to the company or a homeowner.</p>{ref && <div className="ref-banner">Simulated company scenario: <strong>{partner?.company_name || 'Unknown referral code'}</strong>. No partnership is implied.</div>}</section>
    <section className="section-block compact-top"><div className="home-grid"><div className="panel form-panel">{submitted ? <div className="confirmation"><div className="success-mark">✓</div><span className="eyebrow">Demo enquiry recorded</span><h2>Enquiry #{submitted.id} is ready.</h2><p>{partner ? `It appears under the simulated ${partner.company_name} pipeline.` : 'It appears as a direct demo enquiry.'}</p><div className="result-box"><strong>Initial screening: {submitted.qualification_status === 'qualified' ? 'Qualified for review' : 'Needs manual review'}</strong><ul>{submitted.qualification_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></div><p className="small-note">{submitted.ml_score == null ? submitted.score_warning : `Synthetic conversion score: ${submitted.ml_score}/100. ${submitted.score_warning}`}</p><div className="hero-actions"><button className="button primary" onClick={() => navigate('sales', partner?.company_id ? `?company=${partner.company_id}` : '')}>View this pipeline →</button><button className="button secondary" onClick={() => { setSubmitted(null); setForm({ ...emptyForm, consent: false }); }}>New demo enquiry</button></div></div> : <><div className="form-heading"><span className="card-kicker">Fictional details only</span><h2>Tell us about the AC setup</h2><p>Use a `.test` email address. This form stores a local demo record.</p></div><form onSubmit={submit}>
          <div className="form-grid"><label>Planning area<select name="area" value={form.area} onChange={change} required>{areas.map(area => <option key={area.name} value={area.name}>{area.name}</option>)}</select></label><label>Property type<select name="property_type" value={form.property_type} onChange={change}>{PROPERTY_TYPES.map(type => <option key={type}>{type}</option>)}</select></label><label>AC system type<select name="ac_type" value={form.ac_type} onChange={change}><option value="split">Split units</option><option value="multi_split">Multi-split</option><option value="window">Window unit</option><option value="central">Central system</option></select></label><label>Number of AC units<input name="ac_units" type="number" min="1" max="12" value={form.ac_units} onChange={change} required /></label><label>Estimated daily usage (hours)<input name="daily_hours" type="number" min="0.5" max="24" step="0.5" value={form.daily_hours} onChange={change} required /></label><label>Optional estimated AC spend (S$/month)<input name="estimated_ac_spend" type="number" min="0" step="1" placeholder="Your estimate only" value={form.estimated_ac_spend} onChange={change} /></label><label>Demo name<input name="contact_name" type="text" minLength="2" value={form.contact_name} onChange={change} required /></label><label>Demo email<input name="contact_email" type="email" value={form.contact_email} onChange={change} required /></label></div>
          <label className="consent-row"><input name="consent" type="checkbox" checked={form.consent} onChange={change} required /><span>I consent to simulated follow-up in this local demo. No message will be sent.</span></label>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button className="button primary submit-button" disabled={submitting}>{submitting ? 'Saving enquiry…' : 'Submit synthetic enquiry →'}</button>
        </form></>}</div><aside className="process-card"><span className="card-kicker">What would happen next</span><h3>A human-reviewed path</h3><div className="process-step"><b>01</b><div><strong>Initial screening</strong><span>Area, AC type and completeness are checked by stated rules.</span></div></div><div className="process-step"><b>02</b><div><strong>Assessment discussion</strong><span>A team member would confirm technical fit and arrange a visit.</span></div></div><div className="process-step"><b>03</b><div><strong>Quote, if appropriate</strong><span>Costs and expected outcomes require real assessment and validation.</span></div></div><p className="small-note">This hackathon does not contact homeowners, book assessments or establish residential energy savings.</p></aside></div></section>
  </>;
}
