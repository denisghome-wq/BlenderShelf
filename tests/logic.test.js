const test = require('node:test');
const assert = require('node:assert/strict');
const { compareVersions, pickVersionForBlender } = require('../site/assets/logic.js');

test('compareVersions orders correctly', () => {
  assert.equal(compareVersions('4.1.0', '4.1.0'), 0);
  assert.ok(compareVersions('4.4.3', '4.1.0') > 0);
  assert.ok(compareVersions('3.6.0', '4.1.0') < 0);
});

test('pickVersionForBlender matches an open-ended range (blender_max: null)', () => {
  const versions = [
    { addon_version: '0.1.0', blender_min: '4.1.0', blender_max: null, url: 'a' },
  ];
  const result = pickVersionForBlender(versions, '4.4.3');
  assert.equal(result.exact, true);
  assert.equal(result.version.addon_version, '0.1.0');
});

test('pickVersionForBlender matches a closed range and prefers the newest matching entry', () => {
  const versions = [
    { addon_version: '0.2.0', blender_min: '4.2.0', blender_max: null, url: 'a' },
    { addon_version: '0.1.0', blender_min: '3.6.0', blender_max: '4.1.9', url: 'b' },
  ];
  const result = pickVersionForBlender(versions, '4.0.0');
  assert.equal(result.exact, true);
  assert.equal(result.version.addon_version, '0.1.0');
});

test('pickVersionForBlender falls back to the closest entry when nothing matches, flagged not-exact', () => {
  const versions = [
    { addon_version: '0.1.0', blender_min: '4.1.0', blender_max: null, url: 'a' },
  ];
  const result = pickVersionForBlender(versions, '3.0.0');
  assert.equal(result.exact, false);
  assert.equal(result.version.addon_version, '0.1.0');
});

test('pickVersionForBlender returns null for an empty version list', () => {
  assert.equal(pickVersionForBlender([], '4.1.0'), null);
});

test('pickVersionForBlender falls back to the OLDEST entry (not the one with the smallest single-component diff) when Blender is older than every range', () => {
  const versions = [
    { addon_version: '0.2.0', blender_min: '4.2.0', blender_max: null, url: 'a' },
    { addon_version: '0.1.0', blender_min: '3.6.0', blender_max: '4.1.9', url: 'b' },
  ];
  const result = pickVersionForBlender(versions, '3.0.0');
  assert.equal(result.exact, false);
  assert.equal(result.version.addon_version, '0.1.0');
});
