import React from 'react';
import { stagePresentation, reviewPresentation } from './stageTokens.js';
export { stagePresentation, reviewPresentation } from './stageTokens.js';

const paths = {
  inbox: <><path d="M4 4h16v12l-3 4H7l-3-4V4Z"/><path d="M4 14h4l2 3h4l2-3h4"/></>,
  check: <><circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18m-13 6 2 2 5-5"/></>,
  clipboard: <><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4.5h6M8 10h8m-8 4h8"/></>,
  file: <><path d="M6 2h8l5 5v15H6V2Z"/><path d="M14 2v5h5M9 12h7m-7 4h7"/></>,
  close: <><circle cx="12" cy="12" r="9"/><path d="m9 9 6 6m0-6-6 6"/></>,
  alert: <><circle cx="12" cy="12" r="9"/><path d="M12 7v6m0 4h.01"/></>,
  help: <><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4 2c-1 .8-1.5 1.2-1.5 2.5M12 17h.01"/></>,
  ban: <><circle cx="12" cy="12" r="9"/><path d="M5.5 5.5 18.5 18.5"/></>,
};

export function StatusBadge({ value, kind = 'stage' }) {
  const item = (kind === 'review' ? reviewPresentation : stagePresentation)[value];
  if (!item) return <span className="cp-badge">{value?.replaceAll('_', ' ') || 'Unknown'}</span>;
  return <span className="cp-badge" style={{ '--badge-fg': item.color, '--badge-bg': item.tint, '--badge-border': item.border }} title={item.label}>
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[item.icon]}</svg>
    <span>{item.label}</span>
  </span>;
}
