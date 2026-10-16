import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import { api } from './api.js';
import './styles.css';
import './refreshed.css';
import './brand.css';

function StaffGate() {
  const publicForm = ['/demo/form', '/home'].includes(window.location.pathname);
  const publicFormAllowed = import.meta.env.VITE_PUBLIC_FORM === 'true';
  const needsKey = import.meta.env.PROD && import.meta.env.VITE_INTERNAL_DEMO === 'true' && !(publicForm && publicFormAllowed);
  const [verified, setVerified] = useState(!needsKey);
  const [checking, setChecking] = useState(needsKey);
  const [input, setInput] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!needsKey) return;
    if (!sessionStorage.getItem('bizsu-admin-key')) { setChecking(false); return; }
    api('/workspace').then(() => setVerified(true)).catch(() => {
      sessionStorage.removeItem('bizsu-admin-key');
      setError('Enter a valid staff access key.');
    }).finally(() => setChecking(false));
  }, [needsKey]);

  const unlock = async event => {
    event.preventDefault();
    setChecking(true); setError('');
    sessionStorage.setItem('bizsu-admin-key', input.trim());
    try { await api('/workspace'); setVerified(true); }
    catch (failure) { sessionStorage.removeItem('bizsu-admin-key'); setError(failure.message); }
    finally { setChecking(false); }
  };

  if (verified) return <App />;
  return <main className="staff-gate"><form onSubmit={unlock}>
    <span className="staff-gate-label">BIZSU PARTNER WORKSPACE</span>
    <h1>Staff access</h1>
    <p>Enter the workspace key to review partner outreach and customer enquiries.</p>
    <label>Access key<input type="password" autoComplete="off" value={input} onChange={event => setInput(event.target.value)} required /></label>
    {error && <p role="alert" className="staff-gate-error">{error}</p>}
    <button type="submit" disabled={checking}>{checking ? 'Checking…' : 'Open workspace'}</button>
  </form></main>;
}

createRoot(document.getElementById('root')).render(<React.StrictMode><StaffGate /></React.StrictMode>);
