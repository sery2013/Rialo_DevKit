const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../userscript/rialo-enhanced.user.js'), 'utf8');

class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.handlers = {}; this.attributes = {}; this.hidden = false; this.disabled = false; this.style = {}; this.value = ''; this.textContent = ''; }
  addEventListener(name, fn) { this.handlers[name] = fn; }
  dispatch(name, event = {}) { if (this.handlers[name]) this.handlers[name](event); }
  setAttribute(name, value) { this.attributes[name] = value; }
  appendChild(el) { this.children.push(el); return el; }
  replaceChildren() { this.children = []; }
  remove() {}
  click() { this.dispatch('click'); }
  focus() { this.focused = true; }
  attachShadow() { this.shadowRoot = new Shadow(); return this.shadowRoot; }
}
class Shadow extends Element {
  constructor() {
    super(); this.elements = {};
    for (const id of ['panel', 'toggle', 'scan', 'export', 'clear', 'list', 'status']) this.elements[id] = new Element();
    this.elements.panel.hidden = true;
    this.elements.export.disabled = true;
    this.elements.clear.disabled = true;
  }
  getElementById(id) { return this.elements[id]; }
}
function setup(anchors) {
  let root, blob, revoked;
  const doc = {
    readyState: 'complete',
    body: new Element(),
    getElementById: id => id === 'rialo-devkit-root' ? root : null,
    createElement: tag => { const e = new Element(tag); if (tag === 'div') root = e; return e; },
    querySelectorAll: () => anchors,
  };
  const FakeURL = class extends URL {};
  FakeURL.createObjectURL = value => { blob = value; return 'blob:test'; };
  FakeURL.revokeObjectURL = value => { revoked = value; };
  const context = { document: doc, location: {href: 'https://playground.rialo.io/'}, URL: FakeURL, Blob, Date,
    getComputedStyle: anchor => ({ visibility: anchor.visible ? 'visible' : 'hidden', display: 'block' }),
    setTimeout: fn => fn() };
  vm.runInNewContext(source, context);
  return {shadow: root.shadowRoot, getBlob: () => blob, getRevoked: () => revoked, context};
}
function anchor(href, visible = true) { return {href, visible, getClientRects: () => visible ? [{}] : []}; }

test('manual scan deduplicates visible trusted links and exports without sensitive query', async () => {
  const ctx = setup([
    anchor('https://explorer.rialo.io/tx/AbCd123456789xyz?secret=hidden#fragment'),
    anchor('https://explorer.rialo.io/tx/AbCd123456789xyz?other=1'),
    anchor('https://explorer.rialo.io/tx/Hidden123456789xyz', false),
    anchor('https://rialo.io.evil.test/tx/Rejected123456789xyz'),
    anchor('http://explorer.rialo.io/tx/Rejected123456789xyz'),
  ]);
  const s = ctx.shadow;
  s.getElementById('toggle').click();
  assert.equal(s.getElementById('panel').hidden, false);
  s.getElementById('scan').click();
  assert.match(s.getElementById('status').textContent, /^1 link\(s\)/);
  assert.equal(s.getElementById('list').children.length, 1);
  const link = s.getElementById('list').children[0].children[0];
  assert.equal(link.href, 'https://explorer.rialo.io/tx/AbCd123456789xyz');
  s.getElementById('export').click();
  const csv = await ctx.getBlob().text();
  assert.match(csv, /AbCd123456789xyz/);
  assert.doesNotMatch(csv, /secret|fragment|Rejected|Hidden/);
  assert.equal(ctx.getRevoked(), 'blob:test');
  s.getElementById('clear').click();
  assert.equal(s.getElementById('list').children.length, 0);
  assert.equal(s.getElementById('export').disabled, true);
  s.getElementById('panel').dispatch('keydown', {key: 'Escape'});
  assert.equal(s.getElementById('panel').hidden, true);
  assert.equal(s.getElementById('toggle').focused, true);
});
