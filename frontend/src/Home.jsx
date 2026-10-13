import React, { useEffect, useState } from 'react';
import { api } from './api.js';
import './home.css';

const initialForm = { property_type: '', area: '', ac_type: '', ac_units: '', daily_hours: '', enquiry_note: '', contact_name: '', contact_email: '', contact_phone: '', consent: false };
const internalDemo = import.meta.env.DEV || import.meta.env.VITE_INTERNAL_DEMO === 'true';

export default function Home({ partners, areas, navigate, onSubmitted }) {
  const ref = new URLSearchParams(window.location.search).get('ref');
  const partner = partners.find(item => item.referral_code === ref);
  const [form, setForm] = useState(initialForm);
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(null);

  useEffect(() => {
    if (!ref || !partner) return;
    const key = 'bizsu-referral-' + ref;
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
    setError('');
  };
  const continueToContact = event => {
    event.preventDefault();
    if (!form.property_type || !form.area || !form.ac_type || !form.ac_units || !form.daily_hours) {
      setError('Please complete all home details.');
      return;
    }
    setStep(2);
    setError('');
  };
  const submit = async event => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const lead = await api('/leads', { method: 'POST', body: JSON.stringify({
        ...form, referral_code: ref || null,
        ac_units: Number(form.ac_units), daily_hours: Number(form.daily_hours),
        contact_phone: form.contact_phone.trim() || null,
      }) });
      setSubmitted(lead);
      await onSubmitted();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return <div className="homeowner-page">
    <header className="homeowner-header"><a className="homeowner-brand" href={internalDemo ? '/' : '/demo/form'} aria-label={internalDemo ? 'Back to Bizsu main page' : 'Bizsu home'}><span>B</span><strong>Bizsu</strong></a>{internalDemo ? <a className="homeowner-return" href="/">← Back to main page</a> : <span>Home comfort enquiry</span>}</header>
    <main className="homeowner-hero">
      <div className="homeowner-hero-image" role="img" aria-label="Modern home living room with a wall-mounted air conditioner" />
      <div className="homeowner-hero-inner">
        <section className="homeowner-card" aria-label="Homeowner enquiry">
          {submitted ? <div className="homeowner-success" role="status">
            <div className="homeowner-success-icon" aria-hidden="true">✓</div>
            <span className="homeowner-kicker">ENQUIRY RECEIVED</span>
            <h1>Thank you! Your enquiry has been received.</h1>
            <p>Bizsu will review the information and contact you if the solution may be suitable for your home.</p>
            <div className="homeowner-reference">Enquiry reference <strong>#{submitted.id}</strong></div>
            <div className="homeowner-reference">Referral source <strong>{submitted.company_name ? submitted.company_name + ' (demo)' : 'Direct enquiry'}</strong></div>
            {internalDemo && <div className="homeowner-demo-link"><span>Internal demo only</span><button type="button" onClick={() => navigate('demo-sales', '?lead=' + submitted.id)}>View this enquiry in the Customer Pipeline →</button></div>}
            <button className="homeowner-text-button" type="button" onClick={() => { setSubmitted(null); setForm(initialForm); setStep(1); }}>Start another enquiry</button>
          </div> : <>
            <div className="homeowner-card-head"><span className="homeowner-kicker">EXPLORE YOUR OPTIONS</span><h2>Tell us a little about your home.</h2><p>Two quick steps. We’ll review your enquiry before any follow-up.</p></div>
            <div className="homeowner-source"><span>Referral source</span><strong>{partner ? partner.company_name + ' · demo referral' : ref ? 'Referral link needs checking' : 'Direct enquiry'}</strong></div>
            <div className="homeowner-progress" aria-label={'Step ' + step + ' of 2'}><div><span className={step === 1 ? 'active' : 'done'}>1</span><small>About your home</small></div><i /><div><span className={step === 2 ? 'active' : ''}>2</span><small>Contact information</small></div></div>
            <form onSubmit={step === 1 ? continueToContact : submit}>
              {step === 1 ? <div className="homeowner-fields">
                <label>Housing type<select name="property_type" value={form.property_type} onChange={change} required><option value="">Select housing type</option><option>HDB</option><option>Condo</option><option>Landed</option><option>Other</option></select></label>
                <label>Planning area<select name="area" value={form.area} onChange={change} required><option value="">Select your area</option>{areas.map(area=><option key={area.name} value={area.name}>{area.name}</option>)}</select></label>
                <label>AC system type<select name="ac_type" value={form.ac_type} onChange={change} required><option value="">Select system type</option><option value="split">Split unit</option><option value="multi_split">Multi-split</option><option value="window">Window unit</option><option value="central">Central system</option><option value="unknown">Not sure</option></select></label>
                <label>Number of air-conditioning units<input name="ac_units" type="number" min="1" max="12" step="1" inputMode="numeric" value={form.ac_units} onChange={change} placeholder="e.g. 3" required /></label>
                <label>Average daily usage (hours)<input name="daily_hours" type="number" min="0.5" max="24" step="0.5" inputMode="decimal" value={form.daily_hours} onChange={change} placeholder="e.g. 6" required /></label>
                <label>What would you like help with? <span className="optional">Optional</span><textarea name="enquiry_note" value={form.enquiry_note} onChange={change} maxLength="1000" placeholder="Tell us about your AC setup or questions" rows="3" /></label>
                <button className="homeowner-primary" type="submit">Continue <span>→</span></button>
              </div> : <div className="homeowner-fields">
                <label>Name<input name="contact_name" type="text" minLength="2" maxLength="80" autoComplete="name" value={form.contact_name} onChange={change} placeholder="Your name" required /></label>
                <label>Email<input name="contact_email" type="email" autoComplete="email" value={form.contact_email} onChange={change} placeholder="name@example.com" required /></label>
                <label>Phone number <span className="optional">Optional</span><input name="contact_phone" type="tel" autoComplete="tel" value={form.contact_phone} onChange={change} placeholder="Optional" /></label>
                <label className="homeowner-consent"><input name="consent" type="checkbox" checked={form.consent} onChange={change} required /><span>I agree to be contacted by Bizsu about this enquiry. In this local demo, no message is sent.</span></label>
                <div className="homeowner-actions"><button className="homeowner-back" type="button" onClick={() => { setStep(1); setError(''); }}>← Back</button><button className="homeowner-primary" type="submit" disabled={submitting}>{submitting ? 'Submitting…' : 'Submit enquiry'} <span>→</span></button></div>
              </div>}
              {error && <p className="homeowner-error" role="alert">{error}</p>}
            </form>
            <p className="homeowner-form-note">This local prototype stores your enquiry but does not send a message.</p>
            {ref && <p className="homeowner-referral">Referral attribution is captured from this link. No partnership is implied.</p>}
          </>}
        </section>
        <div className="homeowner-copy"><span>COMFORT AT HOME</span><h1>A Cooler Home.<br />Smarter Energy.</h1><p>Explore whether Bizsu’s air-conditioning energy-saving solution could be suitable for your home.</p><small>Suitability and potential outcomes require an individual assessment.</small></div>
      </div>
    </main>
    <div className="homeowner-footer"><span>Comfort begins with the right questions.</span><a href="https://www.pexels.com/photo/interior-of-modern-apartment-living-room-6588599/" target="_blank" rel="noreferrer">Photo: Max Vakhtbovych / Pexels</a></div>
  </div>;
}
