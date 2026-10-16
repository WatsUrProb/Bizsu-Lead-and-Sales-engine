import test from 'node:test';
import assert from 'node:assert/strict';
import { stagePresentation, reviewPresentation } from '../frontend/src/stageTokens.js';

test('every backend sales stage has a distinct accessible presentation', () => {
  assert.deepEqual(Object.keys(stagePresentation), [
    'new', 'qualified', 'assessment_booked', 'assessed', 'quoted', 'won', 'lost',
  ]);
  for (const [stage, item] of Object.entries(stagePresentation)) {
    assert.ok(item.label && item.icon, `${stage} needs a visible label and icon`);
    assert.match(item.color, /^#[0-9A-F]{6}$/i);
    assert.match(item.tint, /^#[0-9A-F]{6}$/i);
  }
  assert.notEqual(stagePresentation.assessment_booked.icon, stagePresentation.assessed.icon);
});

test('screening decisions stay separate from sales stages', () => {
  assert.ok(reviewPresentation.needs_review);
  assert.ok(reviewPresentation.need_more_information);
  assert.ok(reviewPresentation.not_compatible);
  assert.equal(stagePresentation.needs_review, undefined);
});
