const test = require('node:test');
const assert = require('node:assert/strict');

// main.js runs in the browser where `window` is the global object; simulate
// that here (Node has no `window`) so we can assert currentLanguage is
// exposed on it for other scripts (feedback.js) to call as a bare global.
global.window = {};
const { renderDownloadResult } = require('../site/assets/main.js');

function fakeContainer() {
  const children = [];
  return {
    innerHTML: '',
    appendChild(el) { children.push(el); },
    get children() { return children; },
  };
}

function fakeElement() {
  return { textContent: '', className: '', href: '' };
}

test('renderDownloadResult shows an unavailable message plus a direct link to the latest release when match is null', () => {
  const container = fakeContainer();
  renderDownloadResult(container, 'ru', null, fakeElement);
  assert.equal(container.children.length, 2);
  assert.match(container.children[0].textContent, /недоступен/);
  assert.match(container.children[1].href, /releases\/latest$/);
});

test('renderDownloadResult shows a download link with the version number for an exact match', () => {
  const container = fakeContainer();
  const match = { exact: true, version: { addon_version: '0.1.0', url: 'https://example.com/x.zip' } };
  renderDownloadResult(container, 'en', match, fakeElement);
  assert.equal(container.children[0].href, 'https://example.com/x.zip');
  assert.match(container.children[0].textContent, /0\.1\.0/);
});

test('renderDownloadResult adds a warning element for a non-exact match', () => {
  const container = fakeContainer();
  const match = { exact: false, version: { addon_version: '0.1.0', url: 'https://example.com/x.zip' } };
  renderDownloadResult(container, 'ru', match, fakeElement);
  assert.equal(container.children.length, 2);
  assert.equal(container.children[1].className, 'warning');
});

test('currentLanguage is exposed on window so other scripts (feedback.js) can call it as a bare global', () => {
  assert.equal(typeof global.window.currentLanguage, 'function');
});
