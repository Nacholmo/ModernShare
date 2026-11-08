'use strict';
(() => {
  const data = window.KODAK_ATLAS;
  if (!data) return;
  const $ = id => document.getElementById(id);
  const node = (tag, text, cls) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (cls) el.className = cls; return el; };
  const number = value => Number(value).toLocaleString('en-US');
  const functions = data.functions;
  const byAddress = new Map(functions.map(f => [f.address, f]));
  const incoming = new Map();
  for (const edge of data.calls) { if (!incoming.has(edge.to)) incoming.set(edge.to, []); incoming.get(edge.to).push(edge); }
  let active = null, tab = 'c', page = 0, matches = [], detailSerial = 0;
  const pageSize = 100, sourceCache = new Map();
  const metrics = [[number(data.summary.function_count), 'Discovered functions'], [number(data.summary.decompiled), 'Generated decompilations'], [number(data.summary.annotation_count), 'Research annotations'], [number(data.reviewCount), 'Functions flagged for review']];
  for (const [value, label] of metrics) { const metric = node('div', undefined, 'metric'); metric.append(node('strong', value), node('span', label)); $('overview').append(metric); }
  $('firmware-hash').textContent = 'STOCK SHA256 ' + data.manifest.sha256.slice(0, 16) + '…';

  const normalizeAddress = input => {
    const str = input.trim().replace(/^(?:ram:|0x)/i, '');
    return /^[0-9a-f]{4,8}$/i.test(str) ? '0x' + str.toLowerCase().padStart(8, '0') : null;
  };
  function setSection(section) {
    for (const button of document.querySelectorAll('[data-section]')) {
      if (button.dataset.section === section) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
      $(button.dataset.section + '-section').hidden = button.dataset.section !== section;
    }
  }
  for (const button of document.querySelectorAll('[data-section]')) button.addEventListener('click', () => setSection(button.dataset.section));

  function filterFunctions() {
    const query = $('function-search').value.trim().toLowerCase(), mode = $('function-filter').value;
    const address = normalizeAddress(query);
    matches = functions.filter(f => {
      if (mode === 'annotated' && !f.seeded) return false;
      if (mode === 'review' && !f.needs_review) return false;
      if (!query) return true;
      if (address && f.body_ranges.some(r => parseInt(address, 16) >= parseInt(r.start, 16) && parseInt(address, 16) <= parseInt(r.end, 16))) return true;
      return [f.address, f.name, f.comment || ''].some(s => s.toLowerCase().includes(query));
    });
    page = 0; renderList();
  }
  function renderList() {
    const list = $('function-list'); list.replaceChildren();
    $('result-count').textContent = number(matches.length) + (matches.length === 1 ? ' match' : ' matches');
    for (const f of matches.slice(page * pageSize, (page + 1) * pageSize)) {
      const button = node('button', undefined, 'function-row'); button.type = 'button'; button.setAttribute('aria-current', String(active?.address === f.address));
      button.append(node('span', f.name, 'fn-name'));
      const meta = node('span', undefined, 'fn-meta'); meta.append(node('span', f.address));
      if (f.seeded) meta.append(node('span', '● annotated', 'dot-annotated')); else if (f.needs_review) meta.append(node('span', 'review'));
      button.append(meta); button.addEventListener('click', () => selectFunction(f.address)); list.append(button);
    }
    if (!matches.length) list.append(node('p', 'No functions match. Try a shorter name or an address.', 'empty-state'));
    const pages = Math.max(1, Math.ceil(matches.length / pageSize));
    $('page-number').textContent = (page + 1) + ' / ' + pages;
    $('previous-page').disabled = page === 0; $('next-page').disabled = page + 1 >= pages;
  }
  $('function-search').addEventListener('input', filterFunctions);
  $('function-filter').addEventListener('change', filterFunctions);
  $('previous-page').addEventListener('click', () => { page--; renderList(); $('function-list').scrollTop = 0; });
  $('next-page').addEventListener('click', () => { page++; renderList(); $('function-list').scrollTop = 0; });
  document.addEventListener('keydown', event => {
    if (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) { event.preventDefault(); setSection('functions'); $('function-search').focus(); }
    if (event.key === 'Escape' && document.activeElement === $('function-search')) { $('function-search').value = ''; filterFunctions(); }
  });
  const badge = (text, cls) => node('span', text, 'badge ' + (cls || ''));
  function selectFunction(address, preserveTab = false) {
    const f = byAddress.get(address); if (!f) return;
    active = f; if (!preserveTab) tab = 'c'; setSection('functions');
    history.replaceState(null, '', '#function/' + address.slice(2));
    $('function-address').textContent = f.address + ' · ' + number(f.body_bytes) + ' bytes · ' + number(f.instruction_count) + ' instructions';
    $('function-name').textContent = f.name; $('function-signature').textContent = f.signature;
    $('function-comment').textContent = f.comment || 'Automatically discovered function. Name, signature, and semantics have not been manually established.';
    const badges = $('function-badges'); badges.replaceChildren();
    badges.append(badge(f.seeded ? 'Research annotation' : 'Automatic discovery', f.seeded ? 'green' : ''));
    if (f.model_notes?.length) badges.append(badge('Compiler model applied'));
    if (f.call_fixup) badges.append(badge('Shared compiler helper · modeled call effects', 'warm'));
    if (f.warnings.length) badges.append(badge(f.warnings.length + ' decompiler warning' + (f.warnings.length === 1 ? '' : 's'), 'warm'));
    if (f.opaque_operations.length) badges.append(badge(f.opaque_operations.length + ' opaque operation' + (f.opaque_operations.length === 1 ? '' : 's'), 'warm'));
    if (f.computed_flows.length) badges.append(badge(f.computed_flows.length + ' computed control-flow site' + (f.computed_flows.length === 1 ? '' : 's')));
    if (f.status !== 'decompiled') badges.append(badge('Decompilation failed', 'warm'));
    $('copy-address').disabled = false;
    const matchIndex = matches.findIndex(row => row.address === f.address); if (matchIndex >= 0) page = Math.floor(matchIndex / pageSize);
    renderList(); const selectedRow = $('function-list').querySelector('[aria-current=true]');
    if (selectedRow) $('function-list').scrollTop = selectedRow.offsetTop - $('function-list').offsetTop;
    renderDetail();
  }
  async function copy(text, button, normal) {
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
      else { const field = node('textarea', text); document.body.append(field); field.select(); const ok = document.execCommand('copy'); field.remove(); if (!ok) throw new Error('Clipboard unavailable'); }
      button.textContent = 'Copied'; setTimeout(() => { button.textContent = normal; }, 1500);
    } catch { button.textContent = 'Select text to copy'; setTimeout(() => { button.textContent = normal; }, 2000); }
  }
  $('copy-address').addEventListener('click', () => active && copy(active.address, $('copy-address'), 'Copy address'));
  $('copy-source').addEventListener('click', () => active && copy(sourceCache.get(active.address)?.[tab] || '', $('copy-source'), 'Copy text'));
  for (const button of document.querySelectorAll('[data-tab]')) button.addEventListener('click', () => { tab = button.dataset.tab; renderDetail(); });
  // Arrow keys implement the tablist interaction expected by keyboard users.
  document.querySelector('.detail-tabs').addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    const buttons = [...document.querySelectorAll('[data-tab]')]; let i = buttons.indexOf(document.activeElement); if (i < 0) return;
    event.preventDefault(); i = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (i + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
    buttons[i].focus(); buttons[i].click();
  });
  const loadPromises = new Map();
  window.KodakAtlas = { register(detail) { sourceCache.set(detail.address, detail); } };
  function loadSource(address) {
    if (sourceCache.has(address)) return Promise.resolve(sourceCache.get(address));
    if (loadPromises.has(address)) return loadPromises.get(address);
    const promise = new Promise((resolve, reject) => {
      const script = document.createElement('script'); script.src = 'functions/' + address.slice(2) + '.js';
      script.onload = () => { script.remove(); const value = sourceCache.get(address); if (value) resolve(value); else reject(new Error('Source data missing')); };
      script.onerror = () => { script.remove(); loadPromises.delete(address); reject(new Error('Could not load local source data. Regenerate the report.')); };
      document.head.append(script);
    }); loadPromises.set(address, promise); return promise;
  }
  function highlightedCode(text, isAssembly) {
    const pre = node('pre'); pre.tabIndex = 0; pre.setAttribute('aria-label', isAssembly ? 'Assembly listing' : 'Generated pseudocode');
    const code = node('code'); pre.append(code);
    if (isAssembly || text.length > 180000) { code.textContent = text; return pre; }
    const pattern = /\/\*[\s\S]*?\*\/|\/\/[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:void|int|uint|char|uchar|short|ushort|long|float|double|undefined[1248]?|return|if|else|for|while|do|switch|case|default|break|continue|struct|const|unsigned|signed)\b|\b(?:0x[0-9a-fA-F]+|\d+)\b/g;
    let end = 0;
    for (const match of text.matchAll(pattern)) {
      code.append(document.createTextNode(text.slice(end, match.index)));
      const token = match[0], cls = token.startsWith('/') ? 'tok-comment' : /^['"]/.test(token) ? 'tok-string' : /^\d/.test(token) ? 'tok-number' : 'tok-keyword';
      code.append(node('span', token, cls)); end = match.index + token.length;
    }
    code.append(document.createTextNode(text.slice(end))); return pre;
  }
  const card = (title, text, warning = false) => { const el = node('div', undefined, 'note-card' + (warning ? ' warning-card' : '')); el.append(node('h3', title), node('p', text)); return el; };
  const functionLink = (address, subtitle) => {
    const target = byAddress.get(address); const el = node(target ? 'button' : 'div', undefined, 'call-link');
    if (target) { el.type = 'button'; el.addEventListener('click', () => selectFunction(address)); }
    el.append(node('span', target?.name || address), node('small', address + (subtitle ? ' · ' + subtitle : ''))); return el;
  };
  async function renderDetail() {
    if (!active) return; const f = active, serial = ++detailSerial;
    for (const button of document.querySelectorAll('[data-tab]')) { button.setAttribute('aria-selected', String(button.dataset.tab === tab)); button.tabIndex = button.dataset.tab === tab ? 0 : -1; }
    const content = $('detail-content'); content.replaceChildren(); content.setAttribute('aria-labelledby', 'tab-' + tab);
    $('raw-source').hidden = true; $('copy-source').hidden = true;
    if (tab === 'c' || tab === 'assembly') {
      $('content-status').textContent = 'Loading local source…';
      try {
        const source = await loadSource(f.address); if (serial !== detailSerial) return;
        const text = source[tab] || 'No pseudocode is available. Review the assembly and diagnostics.';
        content.replaceChildren(highlightedCode(text, tab === 'assembly'));
        $('content-status').textContent = (tab === 'c' ? 'Generated C-like pseudocode' : 'Address · bytes · instruction') + ' · ' + number(text.split('\n').length) + ' lines';
        const raw = $('raw-source'); raw.hidden = tab === 'c' && f.status !== 'decompiled'; raw.href = '../exports/functions/' + f.export_stem + (tab === 'c' ? '.c' : '.asm'); raw.target = '_blank'; raw.rel = 'noopener';
        $('copy-source').hidden = false;
      } catch (error) { if (serial === detailSerial) { content.append(node('p', error.message, 'empty-state')); $('content-status').textContent = 'Source unavailable'; } }
    } else if (tab === 'calls') {
      const callers = incoming.get(f.address) || []; $('content-status').textContent = 'Direct call references; computed calls may remain unresolved.';
      const grid = node('div', undefined, 'call-columns');
      for (const [title, edges, outgoing] of [['Calls from this function', f.calls, true], ['Callers of this function', callers, false]]) {
        const column = node('div'); column.append(node('h3', title + ' (' + edges.length + ')'));
        for (const edge of edges) column.append(functionLink(outgoing ? edge.to : edge.from, 'at ' + edge.site));
        if (!edges.length) column.append(node('p', 'No direct call references recorded.', 'muted')); grid.append(column);
      }
      content.append(grid);
      if (f.computed_flows.length) content.append(card('Computed control flow', f.computed_flows.map(x => x.site + ': ' + x.instruction).join('\n'), true));
    } else if (tab === 'references') {
      $('content-status').textContent = 'Unique outgoing data references recognized by Ghidra.';
      content.append(table(['Address / space', 'Symbol / data'], f.data_references.map(ref => [ref.address + (ref.space && ref.space !== 'ram' ? ' / ' + ref.space : ''), (ref.name || '(unnamed)') + (ref.type ? ' · ' + ref.type : '') + (ref.string ? '\n' + ref.string : '')])));
    } else {
      $('content-status').textContent = 'Evidence and limitations for this function.';
      if (f.seed) content.append(card('Annotation provenance', f.seed.source + '\n' + f.seed.status));
      if (f.call_fixup) content.append(card('Shared helper model', 'This function owns only its entry instruction because its suffix overlaps other entries. Its call-fixup (' + f.call_fixup + ') supplies complete save/restore effects to callers. Standalone pseudocode is incomplete; inspect the compiler-helper disassembly.', true));
      if (f.diagnostic) content.append(card('Decompiler diagnostic', f.diagnostic, true));
      for (const note of f.model_notes || []) content.append(card('Applied compiler model', note));
      for (const warning of f.warnings) content.append(card(warning.includes('replaced with injection') ? 'Applied compiler model' : 'Decompiler warning', warning, !warning.includes('replaced with injection')));
      if (f.opaque_operations.length) content.append(card('Opaque processor operations', f.opaque_operations.map(op => op.site + ': ' + op.operation).join('\n'), true));
      content.append(card('Validation boundary', 'A successful decompilation does not prove the inferred ABI, structure layout, function extent, or hardware behaviour. Compare the raw instructions and use camera/RAM evidence before patching.'));
    }
  }
  function table(headers, rows) {
    const wrapper = node('div', undefined, 'data-table-wrap'), element = node('table', undefined, 'data-table');
    const head = node('thead'), tr = node('tr'); for (const header of headers) tr.append(node('th', header)); head.append(tr); element.append(head);
    const body = node('tbody');
    for (const values of rows) { const row = node('tr'); for (const value of values) { const td = node('td'); if (value instanceof Node) td.append(value); else td.textContent = value; row.append(td); } body.append(row); }
    element.append(body); wrapper.append(element); return wrapper;
  }
  function renderSymbols() {
    const query = $('symbol-search').value.toLowerCase();
    const rows = data.annotations.filter(row => [row.address, row.name || '', row.comment].join(' ').toLowerCase().includes(query));
    const target = $('symbols-content'); target.replaceChildren(node('p', rows.length + ' matching annotations. References are direct references to the exact address.', 'table-count'));
    target.append(table(['Address', 'Annotation / evidence', 'References'], rows.map(row => {
      const info = node('div'); info.append(node('span', row.name || 'Code-location note', 'symbol-name'), node('p', row.comment), node('p', 'Source: ' + row.source));
      const refs = node('div'); for (const ref of row.references_to.slice(0, 10)) refs.append(functionLink(ref.function || ref.from, ref.type + ' at ' + ref.from));
      if (row.references_to.length > 10) refs.append(node('small', (row.references_to.length - 10) + ' more in exports/annotations.json'));
      if (!row.references_to.length) refs.append(node('small', 'No exact-address references'));
      return [row.address, info, refs];
    })));
  }
  $('symbol-search').addEventListener('input', renderSymbols);
  function renderStrings() {
    const query = $('string-search').value.toLowerCase(); const matches = data.strings.filter(row => (row.address + ' ' + row.value).toLowerCase().includes(query));
    const target = $('strings-content'); target.replaceChildren(node('p', number(matches.length) + ' matches · showing the first 500', 'table-count'));
    target.append(table(['Address', 'String'], matches.slice(0, 500).map(row => [row.address, row.value])));
  }
  $('string-search').addEventListener('input', renderStrings);
  function renderCoverage() {
    const coverage = data.summary.coverage, target = $('coverage-content');
    target.append(node('p', 'The 1 MiB code section also contains literal pools, tables, and padding. This measures byte classification, not the percentage of original source recovered.', 'muted'));
    const grid = node('div', undefined, 'coverage-grid'), left = node('div'), right = node('div');
    const bar = node('div', undefined, 'coverage-bar'); const legend = node('div', undefined, 'legend');
    for (const [label, key, cls, color] of [['Instructions', 'instruction_bytes', 'instructions', '#446a50'], ['Defined data', 'defined_data_bytes', 'data', '#d5a644'], ['Unclassified', 'unclassified_bytes', 'unknown', '#ccd0c2']]) {
      const segment = node('div', undefined, 'coverage-segment ' + cls); segment.style.width = 100 * coverage[key] / coverage.section_bytes + '%'; segment.title = label + ': ' + number(coverage[key]) + ' bytes'; bar.append(segment);
      const item = node('span'), swatch = node('i'); swatch.style.background = color; item.append(swatch, document.createTextNode(label)); legend.append(item);
      const row = node('div', undefined, 'coverage-number'); row.append(node('span', label), node('strong', number(coverage[key]) + ' B')); left.append(row);
    }
    left.prepend(bar, legend);
    right.append(card('Unclassified bytes', number(coverage.unclassified_nonzero_bytes) + ' nonzero bytes and ' + number(coverage.unclassified_zero_bytes) + ' zero bytes remain unclassified. Some may be code; others may be resources or data. They are retained as unknown.'));
    right.append(card('Known limits', 'The ARCompact model has opaque extension operations and imperfect hardware-loop recovery. Indirect calls, shared code, literal data, and MetaWare ABI details can still confuse analysis. Every function has a review-notes tab.', true));
    grid.append(left, right); target.append(grid);
    target.append(card('Verified invariants', 'The saved database retains byte-identical stock code, data, and graphics sections. Checks cover the language model, gp context, all 28 helper fixups, four repaired interior-function seeds, structure sizes, and the high auxiliary-register store.'));
    const links = node('p', undefined, 'footnote');
    for (const [title, href] of [['Project audit', '../diagnostics/project_audit.json'], ['Coverage data', '../exports/coverage.json'], ['Unclassified ranges', '../exports/unclassified_ranges.json'], ['Discovery evidence', '../diagnostics/function_discovery.json']]) { const link = node('a', title); link.href = href; links.append(link, document.createTextNode(' · ')); } target.append(links);
  }
  function renderGuide() {
    const target = $('findings-content'); target.append(node('p', 'A practical route through the known subsystems. Names describe observed behaviour; they are not recovered debug symbols.', 'muted'));
    const grid = node('div', undefined, 'guide-grid');
    for (const topic of data.topics) {
      const box = card(topic.title, topic.description);
      for (const link of topic.functions) box.append(functionLink(link.address, link.role));
      if (topic.note) box.append(node('p', topic.note, 'footnote')); grid.append(box);
    }target.append(grid);
  }
  renderSymbols(); renderStrings(); renderCoverage(); renderGuide(); filterFunctions();
  const hash = location.hash.match(/^#function\/([0-9a-f]{8})$/i); selectFunction(hash && byAddress.has('0x' + hash[1].toLowerCase()) ? '0x' + hash[1].toLowerCase() : '0x000af508');
})();
