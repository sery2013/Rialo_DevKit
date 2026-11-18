// ==UserScript==
// @name         Rialo DevKit — Playground tools
// @namespace    https://github.com/sery2013/Rialo_DevKit
// @version      0.1.0
// @description  Manually collect visible Rialo transaction links and export them as CSV.
// @match        https://playground.rialo.io/*
// @noframes
// @grant        none
// ==/UserScript==

(() => {
  'use strict';

  // This collects only visible links after a deliberate click. No wallet data,
  // form values, background network requests or persistent storage are used.
  function mount() {
    if (!document.body || document.getElementById('rialo-devkit-root')) return;
    const root = document.createElement('div');
    root.id = 'rialo-devkit-root';
    const shadow = root.attachShadow({ mode: 'open' });
    shadow.innerHTML = `
      <style>
        :host { all: initial; position: fixed; z-index: 2147483000; bottom: 18px; left: 18px;
          font: 14px/1.5 system-ui, sans-serif; color: #f1f1f8; }
        * { box-sizing: border-box; }
        button { font: inherit; cursor: pointer; }
        .launcher { border: 1px solid #9f91ff; border-radius: 8px; padding: 10px 14px;
          background: #201b3e; color: #fff; box-shadow: 0 4px 20px #0005; }
        .panel { width: min(360px, calc(100vw - 36px)); max-height: min(520px, calc(100vh - 84px));
          overflow: auto; margin-bottom: 8px; padding: 16px; background: #171722;
          border: 1px solid #45445b; border-radius: 10px; box-shadow: 0 8px 32px #0007; }
        [hidden] { display: none !important; }
        h2 { margin: 0; font-size: 16px; }
        p { margin: 8px 0; color: #c2c2d0; font-size: 12px; }
        .row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
        .action { border: 1px solid #65617f; border-radius: 6px; background: #252435; color: #fff; padding: 7px 10px; }
        .action:disabled { opacity: .5; cursor: not-allowed; }
        button:focus-visible { outline: 2px solid #00cec9; outline-offset: 3px; }
        .status { color: #8de1d7; min-height: 1.5em; }
        .list { max-height: 150px; overflow: auto; margin: 12px 0 0; padding: 0; list-style: none; }
        .list li { padding: 6px 0; border-top: 1px solid #3b3a4b; overflow-wrap: anywhere; }
        .list a { color: #b7aaff; font-size: 12px; }
        @media (max-width: 480px) { :host { bottom: 10px; left: 10px; } }
      </style>
      <section class="panel" id="panel" aria-label="Rialo DevKit tools" hidden>
        <h2>Rialo DevKit</h2>
        <p>Collect transaction links currently visible on this page. This is not a complete wallet history.</p>
        <p>No keys or form values are read. The list stays in this tab until it is closed or reloaded.</p>
        <div class="row">
          <button class="action" id="scan" type="button">Scan visible links</button>
          <button class="action" id="export" type="button" disabled>Export CSV</button>
          <button class="action" id="clear" type="button" disabled>Clear</button>
        </div>
        <p class="status" id="status" role="status" aria-live="polite">No links collected.</p>
        <ul class="list" id="list" aria-label="Collected transaction links"></ul>
      </section>
      <button class="launcher" id="toggle" type="button" aria-expanded="false" aria-controls="panel">Rialo tools</button>`;
    document.body.appendChild(root);

    const panel = shadow.getElementById('panel');
    const toggle = shadow.getElementById('toggle');
    const list = shadow.getElementById('list');
    const status = shadow.getElementById('status');
    const exportButton = shadow.getElementById('export');
    const clearButton = shadow.getElementById('clear');
    const records = new Map();

    function render(message) {
      list.replaceChildren();
      for (const record of records.values()) {
        const item = document.createElement('li');
        const link = document.createElement('a');
        link.href = record.url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = record.id;
        item.appendChild(link);
        list.appendChild(item);
      }
      exportButton.disabled = records.size === 0;
      clearButton.disabled = records.size === 0;
      status.textContent = message;
    }

    function getTransaction(anchor) {
      if (!anchor.getClientRects().length) return null;
      const style = getComputedStyle(anchor);
      if (style.visibility === 'hidden' || style.display === 'none') return null;
      let url;
      try { url = new URL(anchor.href, location.href); } catch (_) { return null; }
      const hostname = url.hostname.toLowerCase();
      if (url.protocol !== 'https:' || url.username || url.password ||
          !(hostname === 'rialo.io' || hostname.endsWith('.rialo.io'))) return null;
      const match = url.pathname.match(/\/(?:tx|transaction|transactions)\/([a-zA-Z0-9_-]{16,128})\/?$/);
      if (!match) return null;
      url.search = '';
      url.hash = '';
      return { id: match[1], url: url.href, observedAt: new Date().toISOString() };
    }

    function csvCell(value) {
      const str = String(value);
      const safe = /^[=+@\-\t\r\n]/.test(str) ? "'" + str : str;
      return '"' + safe.replace(/"/g, '""') + '"';
    }

    toggle.addEventListener('click', () => {
      panel.hidden = !panel.hidden;
      toggle.setAttribute('aria-expanded', String(!panel.hidden));
      if (!panel.hidden) shadow.getElementById('scan').focus();
    });
    panel.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        panel.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
        toggle.focus();
      }
    });
    shadow.getElementById('scan').addEventListener('click', () => {
      let added = 0;
      document.querySelectorAll('a[href]').forEach(anchor => {
        const record = getTransaction(anchor);
        if (record && !records.has(record.url)) {
          records.set(record.url, record);
          added++;
        }
      });
      render(`${records.size} link(s) collected; ${added} added in this scan.`);
    });
    clearButton.addEventListener('click', () => {
      records.clear();
      render('List cleared.');
    });
    exportButton.addEventListener('click', () => {
      const rows = [['transaction_id', 'url', 'observed_at']];
      for (const record of records.values()) rows.push([record.id, record.url, record.observedAt]);
      const csv = rows.map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
      const download = document.createElement('a');
      download.href = url;
      download.download = 'rialo-visible-transactions.csv';
      document.body.appendChild(download);
      download.click();
      download.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      status.textContent = `Exported ${records.size} visible link(s).`;
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true });
  else mount();
})();
