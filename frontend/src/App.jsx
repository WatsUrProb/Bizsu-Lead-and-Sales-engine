import React, { useState } from 'react';
import Workspace from './Workspace.jsx';
import Home from './Home.jsx';
import Sales from './Sales.jsx';
import { api } from './api.js';
import './workspace.css';

const startPage = () => ({'/pipeline':'pipeline','/drafts':'drafts','/demo/form':'demo-form','/demo/sales':'demo-sales'}[location.pathname] || 'discover');
export default function App() {
  const [page, setPage] = useState(startPage);
  const [demo, setDemo] = useState(null);
  const [demoError, setDemoError] = useState('');
  const navigate = (next, query = '') => {
    const routes = {discover:'/',pipeline:'/pipeline',drafts:'/drafts','demo-form':'/demo/form','demo-sales':'/demo/sales'};
    history.pushState({}, '', (routes[next] || '/') + query);
    setPage(next);
    window.scrollTo({top:0,behavior:'smooth'});
  };
  React.useEffect(() => {
    const pop = () => setPage(startPage());
    window.addEventListener('popstate',pop);
    return () => window.removeEventListener('popstate',pop);
  }, []);
  React.useEffect(() => {
    if (!page.startsWith('demo') || demo) return;
    Promise.all([api('/areas'),api('/partners'),api('/leads'),api('/dashboard'),api('/candidates')])
      .then(([areas,partners,leads,dashboard,catalog]) => setDemo({areas:areas.areas,partners,leads,dashboard,catalog}))
      .catch(error => setDemoError(error.message));
  }, [page,demo]);
  const refreshDemo = async () => {
    const [leads,dashboard] = await Promise.all([api('/leads'),api('/dashboard')]);
    setDemo(current => ({...current,leads,dashboard}));
  };
  return <div className="workspace-shell">
    <aside className="workspace-sidebar">
      <button className="workspace-brand" onClick={() => navigate('discover')}><span className="brand-glyph">B</span><span><strong>Bizsu</strong><small>PARTNER WORKSPACE</small></span></button>
      <div className="nav-caption">PARTNER ACQUISITION</div>
      <nav aria-label="Main navigation" className="workspace-nav">
        {[["discover","◈","Discover"],["pipeline","▦","Pipeline"],["drafts","✉","Outreach drafts"]].map(([id,icon,label])=><button key={id} className={page===id?'current':''} onClick={()=>navigate(id)}><span aria-hidden="true">{icon}</span>{label}</button>)}
      </nav>
      <div className="sidebar-spacer" />
      <div className="nav-caption">SEPARATE DEMO</div>
      <nav aria-label="Simulated referral demo" className="workspace-nav">
        <button className={page==='demo-form'?'current':''} onClick={()=>navigate('demo-form')}><span aria-hidden="true">◇</span>Referral form <em>Demo</em></button>
        <button className={page==='demo-sales'?'current':''} onClick={()=>navigate('demo-sales')}><span aria-hidden="true">▤</span>Sales flow <em>Demo</em></button>
      </nav>
      <p className="sidebar-note">Public research supports discovery. No listed company is a confirmed Bizsu partner.</p>
    </aside>
    <div className="workspace-main">
      <header className="workspace-topbar"><span>Partner acquisition <span className="topbar-slash">/</span> {page.replace('demo-','Demo ')}</span><span className="topbar-status"><i/> Local prototype</span></header>
      {page.startsWith('demo') ? <div className="legacy-demo"><div className="demo-warning"><strong>Fictional referral demonstration</strong><span>All partner assignments, enquiries and sales outcomes in this section are simulated.</span></div>{demoError ? <div className="ws-state">{demoError}</div> : !demo ? <div className="ws-state">Loading demo…</div> : page==='demo-form' ? <Home areas={demo.areas} partners={demo.partners} navigate={target=>navigate(target==='sales'?'demo-sales':'demo-form')} onSubmitted={refreshDemo}/> : <Sales leads={demo.leads} catalog={demo.catalog} dashboard={demo.dashboard} refresh={refreshDemo}/>}</div> : <Workspace page={page} navigate={navigate}/>}
    </div>
  </div>;
}
