import React, { useState } from 'react';
import Workspace from './Workspace.jsx';
import Home from './Home.jsx';
import Sales from './Sales.jsx';
import { api } from './api.js';
import './workspace.css';

const internalDemo = import.meta.env.DEV || import.meta.env.VITE_INTERNAL_DEMO === 'true';
const startPage = () => internalDemo ? ({'/pipeline':'pipeline','/drafts':'drafts','/demo/form':'demo-form','/home':'demo-form','/demo/sales':'demo-sales'}[location.pathname] || 'discover') : 'demo-form';
export default function App() {
  const [page, setPage] = useState(startPage);
  const [demo, setDemo] = useState(null);
  const [demoError, setDemoError] = useState('');
  const navigate = (next, query = '') => {
    if (!internalDemo && next !== 'demo-form') return;
    const routes = {discover:'/',pipeline:'/pipeline',drafts:'/drafts','demo-form':'/demo/form','demo-sales':'/demo/sales'};
    if (next === 'demo-form' && query.includes('ref=')) setDemo(current => current ? {...current, partners: null} : current);
    if (next === 'demo-sales') setDemo(current => current ? {...current, leads: null, dashboard: null} : current);
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
    if (!page.startsWith('demo')) return;
    if (page === 'demo-form' && demo?.partners && demo?.areas) return;
    if (page === 'demo-sales' && demo?.leads) return;
    const request = page === 'demo-form'
      ? Promise.all([api('/partners'),api('/areas')]).then(([partners,areas]) => ({ partners, areas: areas.areas }))
      : Promise.all([api('/partners'),api('/areas'),api('/leads'),api('/dashboard')]).then(([partners,areas,leads,dashboard]) => ({partners,areas:areas.areas,leads,dashboard}));
    request.then(next => { setDemo(current => ({...current,...next})); setDemoError(''); }).catch(error => setDemoError(error.message));
  }, [page,demo]);
  const refreshDemo = async () => {
    setDemo(current => ({...current,leads:null}));
  };
  if (page === 'demo-form') return demoError ? <div className="ws-state">{demoError}</div> : !demo?.partners || !demo?.areas ? <div className="ws-state">Loading form…</div> : <Home partners={demo.partners} areas={demo.areas} navigate={navigate} onSubmitted={refreshDemo}/>;
  return <div className="workspace-shell">
    <aside className="workspace-sidebar">
      <button className="workspace-brand" onClick={() => navigate('discover')}><span className="brand-glyph">B</span><span><strong>Bizsu</strong><small>PARTNER WORKSPACE</small></span></button>
      <div className="nav-caption">PARTNER ACQUISITION</div>
      <nav aria-label="Main navigation" className="workspace-nav">
        {[["discover","◈","Discover"],["pipeline","▦","Partner Pipeline"],["drafts","✉","Outreach drafts"]].map(([id,icon,label])=><button key={id} className={page===id?'current':''} onClick={()=>navigate(id)}><span aria-hidden="true">{icon}</span>{label}</button>)}
      </nav>
      <div className="sidebar-spacer" />
      <div className="nav-caption">CUSTOMER ACQUISITION</div>
      <nav aria-label="Customer acquisition" className="workspace-nav">
        <button className={page==='demo-form'?'current':''} onClick={()=>navigate('demo-form')}><span aria-hidden="true">◇</span>Homeowner form</button>
        <button className={page==='demo-sales'?'current':''} onClick={()=>navigate('demo-sales')}><span aria-hidden="true">▤</span>Customer pipeline</button>
      </nav>
      <p className="sidebar-note">Public research supports discovery. No listed company is a confirmed Bizsu partner.</p>
    </aside>
    <div className="workspace-main">
      <header className="workspace-topbar"><span>{page==='demo-sales'?'Customer acquisition':'Partner acquisition'} <span className="topbar-slash">/</span> {page==='demo-sales'?'Customer pipeline':page}</span><span className="topbar-status"><i/> Local prototype</span></header>
      {page==='demo-sales' ? demoError ? <div className="ws-state">{demoError}</div> : !demo?.leads || !demo?.areas || !demo?.dashboard ? <div className="ws-state">Loading customer pipeline…</div> : <Sales leads={demo.leads} areas={demo.areas} dashboard={demo.dashboard} refresh={async()=>{const [leads,dashboard]=await Promise.all([api('/leads'),api('/dashboard')]);setDemo(current=>({...current,leads,dashboard}));}}/> : <Workspace page={page} navigate={navigate}/>}
    </div>
  </div>;
}
