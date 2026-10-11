import React, { useEffect, useState } from 'react';
import { api } from './api.js';
import Partners from './Partners.jsx';
import Home from './Home.jsx';
import Sales from './Sales.jsx';
import './candidates.css';

const pageFromPath = path => ({ '/home': 'home', '/sales': 'sales' }[path] || 'partners');

export default function App() {
  const [page, setPage] = useState(pageFromPath(window.location.pathname));
  const [areas, setAreas] = useState([]);
  const [partners, setPartners] = useState([]);
  const [candidateCatalog, setCandidateCatalog] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refreshSales = async () => {
    const [nextDashboard, nextLeads] = await Promise.all([api('/dashboard'), api('/leads')]);
    if (!nextDashboard.company_breakdown) throw new Error('Restart the FastAPI server to load the company pipeline.');
    setDashboard(nextDashboard);
    setLeads(nextLeads);
  };

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [nextAreas, nextPartners, nextCandidates] = await Promise.all([api('/areas'), api('/partners'), api('/candidates')]);
      setAreas(nextAreas.areas);
      setPartners(nextPartners);
      setCandidateCatalog(nextCandidates);
      await refreshSales();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const onPop = () => setPage(pageFromPath(window.location.pathname));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const navigate = (target, query = '') => {
    const path = target === 'partners' ? '/' : `/${target}`;
    window.history.pushState({}, '', `${path}${query}`);
    setPage(target);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return <div className="app-shell">
    <header className="site-header">
      <div className="brand" onClick={() => navigate('partners')} role="button" tabIndex="0" onKeyDown={event => event.key === 'Enter' && navigate('partners')}>
        <span className="brand-mark">B</span><span><strong>Bizsu</strong><small>growth lab</small></span>
      </div>
      <nav aria-label="Main navigation">
        {[["partners", "Companies"], ["home", "Demo form"], ["sales", "Pipeline"]].map(([key, label]) =>
          <button key={key} className={page === key ? 'active' : ''} onClick={() => navigate(key)}>{label}</button>)}
      </nav>
      <div className="header-pill"><span className="pulse-dot" /> Local demo</div>
    </header>

    <main>
      {loading ? <div className="state-panel">Loading the local demo…</div> : error ?
        <div className="state-panel error-state"><h2>Could not load the demo</h2><p>{error}</p><p>Start the FastAPI server on port 8000, then retry.</p><button className="button primary" onClick={load}>Retry</button></div> : <>
          {page === 'partners' && <Partners partners={partners} catalog={candidateCatalog} dashboard={dashboard} navigate={navigate} />}
          {page === 'home' && <Home areas={areas} partners={partners} navigate={navigate} onSubmitted={refreshSales} />}
          {page === 'sales' && <Sales leads={leads} catalog={candidateCatalog} dashboard={dashboard} refresh={refreshSales} />}
        </>}
    </main>

    <footer className="site-footer">
      <span><strong>Bizsu growth lab</strong> · student hackathon proof of concept</span>
      <span>Company facts are sourced. Every company referral, enquiry, outcome and ML score shown here is simulated.</span>
    </footer>
  </div>;
}
