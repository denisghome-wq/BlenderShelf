import test from 'node:test';
import assert from 'node:assert/strict';
import { buildIssuePayload } from '../worker/src/issueBuilder.js';

test('bug report builds a title with type and severity, and the right labels', () => {
  const result = buildIssuePayload({
    type: 'bug',
    severity: 'critical',
    blenderVersion: '4.4.0',
    addonVersion: '0.1.0',
    description: 'The shelf disappears after switching workspace tabs and never comes back, has to restart Blender every time this happens which is extremely disruptive to my workflow',
    contact: '',
  });
  assert.equal(result.title, '[Bug][critical] The shelf disappears after switching workspace tabs and neve');
  assert.deepEqual(result.labels, ['type:bug', 'severity:critical']);
});

test('feature request builds a title with only the type, no severity label', () => {
  const result = buildIssuePayload({
    type: 'feature',
    severity: '',
    blenderVersion: '',
    addonVersion: '',
    description: 'Add a way to reorder pie menu items by drag and drop',
    contact: '',
  });
  assert.equal(result.title, '[Feature] Add a way to reorder pie menu items by drag and drop');
  assert.deepEqual(result.labels, ['type:feature']);
});

test('question and other types map to their own label with no severity', () => {
  assert.deepEqual(buildIssuePayload({ type: 'question', description: 'x' }).labels, ['type:question']);
  assert.deepEqual(buildIssuePayload({ type: 'other', description: 'x' }).labels, ['type:other']);
});

test('title truncates description to 60 characters', () => {
  const result = buildIssuePayload({ type: 'other', description: 'x'.repeat(200) });
  assert.equal(result.title, '[Other] ' + 'x'.repeat(60));
});

test('body fences the description so @mentions and #references do not go live', () => {
  const result = buildIssuePayload({
    type: 'bug',
    severity: 'minor',
    blenderVersion: '4.4.0',
    addonVersion: '0.1.0',
    description: 'Reported by @someone-unrelated, see also #123 for context',
    contact: '',
  });
  const fenced = '```\nReported by @someone-unrelated, see also #123 for context\n```';
  assert.ok(result.body.includes(fenced), 'description must be inside a fenced code block');
});

test('body fences the optional contact field too, and omits the line entirely when blank', () => {
  const withContact = buildIssuePayload({ type: 'question', description: 'x', contact: '@bob email@example.com' });
  assert.ok(withContact.body.includes('```\n@bob email@example.com\n```'));

  const withoutContact = buildIssuePayload({ type: 'question', description: 'x', contact: '' });
  assert.ok(!withoutContact.body.toLowerCase().includes('contact'));
});

test('body includes Blender and addon version when provided, omits the fields when blank', () => {
  const withVersions = buildIssuePayload({ type: 'bug', severity: 'major', blenderVersion: '4.4.0', addonVersion: '0.1.0', description: 'x' });
  assert.ok(withVersions.body.includes('4.4.0'));
  assert.ok(withVersions.body.includes('0.1.0'));

  const withoutVersions = buildIssuePayload({ type: 'question', description: 'x' });
  assert.ok(!withoutVersions.body.includes('Blender version'));
});
