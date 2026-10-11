import React, { useMemo, useState } from 'react';
import { number, percent } from './api.js';

const COLORS = ['#1b8478', '#e2a346', '#657ac5', '#aa76a4'];

export default function Market({ areas, meta, navigate }) {
  const [cluster, setCluster] = useState('all');
  const [minHouseholds, setMinHouseholds] = useState(0);
  const [minLargeHdb, setMinLargeHdb] = useState(0);
  const [selectedName, setSelectedName] = useState('Ang Mo Kio');
  const filtered = useMemo(() => areas.filter(area =>
    (cluster === 'all' || area.cluster_id === Number(cluster)) &&
    area.households >= minHouseholds &&
    (area.features.large_hdb_share || 0) >= minLargeHdb
  ), [areas, cluster, minHouseholds, minLargeHdb]);
  const selected = filtered.find(area => area.name === selectedName) || filtered[0];
  const clustered = areas.filter(area => area.cluster_id != null);
  const totalHouseholds = areas.reduce((sum, area) => sum + area.households, 0);
  const chartAreas = filtered.filter(area => area.cluster_id != null);
  const maxX = Math.max(0.55, ...clustered.map(area => area.features.condo_share || 0));
  const maxY = Math.max(0.55, ...clustered.map(area => area.features.large_hdb_share || 0));
  const x = value => 48 + (value / maxX) * 530;
  const y = value => 250 - (value / maxY) * 210;

  return <>
    <section className="hero market-hero">
      <div className="hero-copy"><span className="eyebrow">01 / Market opportunity</span>
        <h1>Understand the landscape.<br /><em>Then test the channel.</em></h1>
        <p>Explore Singapore’s observed planning-area housing patterns, then review sourced aircon service companies and a separate simulated referral journey.</p>
        <div className="hero-actions"><button className="button primary" onClick={() => navigate('partners')}>Review company candidates <span>→</span></button><a className="text-link" href="#method">See data method ↓</a></div>
      </div>
      <div className="hero-card">
        <span className="card-kicker">Data at a glance</span>
        <strong>{number(totalHouseholds)}</strong><span>resident households across {areas.length} named planning areas</span>
        <div className="hero-card-line"><span>{clustered.length} areas clustered</span><span>2020 Census</span></div>
        <small>“Others” is a non-geographic census category and is excluded here.</small>
      </div>
    </section>

    <section className="section-block" id="explore">
      <div className="section-heading"><div><span className="eyebrow">Observed aggregates</span><h2>Planning-area profiles</h2><p>Clusters describe areas with similar housing and household composition. They are not individual customer segments or proven sales opportunities.</p></div><span className="subtle-tag">K-Means · 5 standardised features</span></div>
      <div className="filter-bar">
        <label>Cluster<select value={cluster} onChange={event => setCluster(event.target.value)}><option value="all">All areas</option>{Object.entries(meta.clusters.cluster_labels).map(([id, label]) => <option key={id} value={id}>Cluster {Number(id) + 1}</option>)}</select></label>
        <label>Minimum households<select value={minHouseholds} onChange={event => setMinHouseholds(Number(event.target.value))}><option value="0">Any size</option><option value="20000">20,000+</option><option value="40000">40,000+</option><option value="60000">60,000+</option></select></label>
        <label>4/5-room HDB share<select value={minLargeHdb} onChange={event => setMinLargeHdb(Number(event.target.value))}><option value="0">Any share</option><option value="0.25">25%+</option><option value="0.4">40%+</option><option value="0.55">55%+</option></select></label>
        <span className="filter-result">{filtered.length} areas shown</span>
      </div>
      <div className="market-grid">
        <div className="panel chart-panel">
          <div className="panel-title"><h3>Housing mix by area</h3><span>Bubble size = household count</span></div>
          <svg className="scatter" viewBox="0 0 630 300" role="img" aria-label="Planning areas plotted by condominium and larger HDB household shares">
            {[0, 0.25, 0.5].map(value => <g key={value}><line x1={x(value)} x2={x(value)} y1="40" y2="250" className="grid-line" /><text x={x(value)} y="271" textAnchor="middle">{Math.round(value * 100)}%</text><line x1="48" x2="578" y1={y(value)} y2={y(value)} className="grid-line" /><text x="39" y={y(value) + 4} textAnchor="end">{Math.round(value * 100)}%</text></g>)}
            <text x="315" y="297" textAnchor="middle">Condo / apartment household share</text>
            <text transform="translate(12 156) rotate(-90)" textAnchor="middle">4/5-room HDB share</text>
            {chartAreas.map(area => <circle key={area.name} cx={x(area.features.condo_share)} cy={y(area.features.large_hdb_share)} r={Math.max(5, Math.min(17, Math.sqrt(area.households) / 18))} fill={COLORS[area.cluster_id % COLORS.length]} opacity={selected?.name === area.name ? 1 : 0.73} stroke={selected?.name === area.name ? '#17352f' : 'white'} strokeWidth={selected?.name === area.name ? 3 : 1.5} onClick={() => setSelectedName(area.name)} tabIndex="0" onKeyDown={event => event.key === 'Enter' && setSelectedName(area.name)}><title>{area.name}: {number(area.households)} households</title></circle>)}
          </svg>
          <div className="legend">{Object.entries(meta.clusters.cluster_labels).map(([id, label]) => <span key={id}><i style={{ background: COLORS[Number(id) % COLORS.length] }} />Cluster {Number(id) + 1}: {label}</span>)}</div>
        </div>
        <div className="panel area-detail">
          {selected ? <><span className="card-kicker">Selected planning area</span><h3>{selected.name}</h3><span className="cluster-chip" style={{ '--cluster-color': COLORS[(selected.cluster_id ?? 2) % COLORS.length] }}>{selected.cluster_id == null ? 'Not clustered' : `Cluster ${selected.cluster_id + 1}`}</span>
            <strong className="big-number">{number(selected.households)}</strong><span className="muted">resident households · Census 2020</span>
            <div className="metric-list"><div><span>HDB households</span><strong>{percent(selected.features.hdb_share)}</strong></div><div><span>4/5-room HDB</span><strong>{percent(selected.features.large_hdb_share)}</strong></div><div><span>Condo / apartments</span><strong>{percent(selected.features.condo_share)}</strong></div><div><span>4+ person households</span><strong>{percent(selected.features.large_household_share)}</strong></div></div>
            {selected.electricity_context && <div className="context-note"><b>Electricity context · 2013</b><span>{selected.electricity_context.average_monthly_kwh ?? '—'} kWh average monthly whole-home electricity. Historical area average; not AC usage or current demand.</span></div>}
            {selected.cluster_exclusion_reasons.length > 0 && <p className="small-note">Not clustered: {selected.cluster_exclusion_reasons.join('; ')}.</p>}
          </> : <div className="empty-state">No areas match these filters.</div>}
        </div>
      </div>
      <div className="area-list">{filtered.map(area => <button key={area.name} className={selected?.name === area.name ? 'area-row selected' : 'area-row'} onClick={() => setSelectedName(area.name)}><span>{area.name}</span><span>{area.cluster_id == null ? 'No cluster' : `Cluster ${area.cluster_id + 1}`}</span><strong>{number(area.households)}</strong></button>)}</div>
    </section>

    <section className="section-block method-section" id="method">
      <div className="section-heading"><div><span className="eyebrow">What the model can say</span><h2>Method & limits</h2></div></div>
      <div className="method-grid"><div className="panel"><h3>Area-level segmentation</h3><p>Five observed Census 2020 shares are standardised before K-Means. The pipeline compares 2–4 clusters using silhouette, repeated-subsample stability and minimum group size.</p><div className="mini-table">{meta.clusters.candidate_metrics.map(item => <div key={item.k}><span>k={item.k}{item.k === meta.clusters.chosen_k ? ' · selected' : ''}</span><span>silhouette {item.silhouette}</span><span>stability {item.stability_ari}</span></div>)}</div></div>
        <div className="panel"><h3>Business interpretation</h3><p>The filters reveal where certain household types are more common. They do not measure homeowner interest, Bizsu compatibility, installation economics or partner willingness.</p><p>Two named areas lack required published cells and remain visible without cluster labels. The 2013 EMA figures are historical whole-home electricity averages, excluded from clustering.</p></div></div>
      <div className="sources-line"><span>Official sources:</span>{meta.sources.sources.map(source => <a href={source.url} key={source.key} target="_blank" rel="noreferrer">{source.publisher} · {source.observation_year}</a>)}</div>
    </section>
  </>;
}
