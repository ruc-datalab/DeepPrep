// Agent Console UI
// - Setup modal on entry (upload + target schema)
// - Collapse animation into top summary
// - Run button triggers backend + websocket stream
// - Bottom: left turn exploration, right operator tree

let uploadId = null;
let trialId = null;
let ws = null;

let latestTree = null;

// nodeId -> node object
let treeIndex = new Map();
// nodeId -> DOM element (span.node)
let nodeEls = new Map();
let seenNodeIds = new Set();

// turn (number) -> record
let turns = new Map();
let currentTurn = null;
let lastStatusText = 'idle';

const DEFAULT_MAX_EXPLORE_TURN = 10;

const el = (id) => document.getElementById(id);

function escapeHtml(s) {
  return String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

async function safeJson(resp) {
  try {
    return await resp.json();
  } catch {
    return null;
  }
}

function markUserEditedMaxTurn() {
  const maxTurnEl = el('maxExploreTurn');
  if (!maxTurnEl) return;
  maxTurnEl.dataset.userEdited = '1';
}

async function loadLlmConfigs() {
  const sel = el('llmSelect');
  if (!sel) return;
  try {
    const resp = await fetch('/ui/configs');
    const data = await safeJson(resp);
    if (!resp.ok || !data) return;

    const options = Array.isArray(data.options) ? data.options : [];

    sel.innerHTML = '';
    for (const opt of options) {
      const o = document.createElement('option');
      o.value = opt.configName;
      o.textContent = opt.label;
      sel.appendChild(o);
    }

    const findClaude4 = () => {
      for (const opt of options) {
        const label = String(opt && opt.label ? opt.label : '').toLowerCase();
        if (label.includes('claude-4')) return opt.configName;
      }
      return null;
    };

    // Default LLM: Claude-4.
    const desired = findClaude4();
    const active = data.activeConfigName ? String(data.activeConfigName) : '';
    if (desired && desired !== active) {
      sel.value = desired;
      // Keep UI/backend in sync so the run actually uses Claude-4.
      await setActiveConfig(desired, { updateMaxTurn: true });
    } else if (active) {
      sel.value = active;
    }

    // Default max_explore_turn: 10 (unless user has edited it).
    // Don't let backend defaults (often 5) override a non-empty user/UI value.
    const maxTurnEl = el('maxExploreTurn');
    if (maxTurnEl && !maxTurnEl.dataset.userEdited) {
      const current = String(maxTurnEl.value || '').trim();
      if (!current) {
        maxTurnEl.value = String(DEFAULT_MAX_EXPLORE_TURN);
      }
    }
  } catch {
    // best-effort
  }
}

async function setActiveConfig(configName, { updateMaxTurn = true } = {}) {
  setUiError('');
  try {
    const resp = await fetch('/ui/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ configName }),
    });
    const data = await safeJson(resp);
    if (!resp.ok || !data || !data.ok) {
      const msg = (data && data.error) || 'Failed to set config';
      setUiError(msg);
      return;
    }

    const sel = el('llmSelect');
    if (sel && data.activeConfigName) sel.value = data.activeConfigName;

    const maxTurnEl = el('maxExploreTurn');
    if (updateMaxTurn && maxTurnEl && !maxTurnEl.dataset.userEdited) {
      const current = String(maxTurnEl.value || '').trim();
      // Only fill from backend if user/UI hasn't set a value.
      if (!current && typeof data.maxExploreTurn !== 'undefined' && data.maxExploreTurn !== null) {
        maxTurnEl.value = String(data.maxExploreTurn);
      }
      if (!String(maxTurnEl.value || '').trim()) {
        maxTurnEl.value = String(DEFAULT_MAX_EXPLORE_TURN);
      }
    }
  } catch (e) {
    setUiError(String(e && e.message ? e.message : e));
  }
}

function setUiError(message) {
  const box = el('uiError');
  if (!box) return;
  const msg = String(message || '').trim();
  if (!msg) {
    box.classList.add('hidden');
    box.textContent = '';
    return;
  }
  box.textContent = msg;
  box.classList.remove('hidden');
}

function setStatus(text) {
  const s = el('status');
  if (!s) return;
  const t = String(text || '').trim() || 'idle';
  lastStatusText = t;
  s.textContent = t;
  s.dataset.status = t.toLowerCase();
  setTreeActivity(t);
  setTurnHintFromStatus(t);
  renderTurns();
}

function setTreeActivity(statusText) {
  const box = el('treeActivity');
  if (!box) return;
  const t = String(statusText || '').trim();
  const low = t.toLowerCase();

  const isWorking =
    low.startsWith('starting') ||
    low.startsWith('running') ||
    low.startsWith('thinking') ||
    low.startsWith('executing');

  if (!isWorking) {
    box.classList.add('hidden');
    box.textContent = '';
    return;
  }

  if (low.startsWith('thinking')) {
    box.textContent = 'LLM is thinking… generating next operator chain.';
  } else if (low.startsWith('executing')) {
    box.textContent = 'Executing final operator chain… materializing target table.';
  } else {
    box.textContent = 'Agent is running…';
  }
  box.classList.remove('hidden');
}

function parseTurnFromStatus(statusText) {
  const m = String(statusText || '').match(/turn\s+(\d+)/i);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isFinite(n) ? n : null;
}

function ensureTurn(turn) {
  if (!Number.isFinite(turn)) return null;
  if (!turns.has(turn)) {
    turns.set(turn, {
      turn,
      thinking: '',
      outputs: [],
      operatorCount: 0,
      tables: [],
      lastUpdatedAt: Date.now(),
    });
  }
  return turns.get(turn);
}

function setTurnHintFromStatus(statusText) {
  const hint = el('turnHint');
  if (!hint) return;
  const t = String(statusText || '').trim();
  const low = t.toLowerCase();
  const turn = parseTurnFromStatus(t);
  if ((low.startsWith('thinking') || low.startsWith('running')) && turn) {
    hint.textContent = 'Exploring...';
  } else if (low.startsWith('executing')) {
    hint.textContent = 'executing final solution…';
  } else if (low === 'idle') {
    hint.textContent = 'waiting for input…';
  } else {
    hint.textContent = t ? t : '…';
  }
}

function isExploringNow() {
  const low = String(lastStatusText || '').toLowerCase();
  return low.startsWith('thinking') || low.startsWith('running') || low.startsWith('starting');
}

function openTurnModal(turn) {
  const modal = el('turnModal');
  const body = el('turnModalBody');
  const title = el('turnModalTitle');
  if (!modal || !body) return;

  const rec = turns.get(turn);
  const parts = rec && Array.isArray(rec.outputs) ? rec.outputs : [];

  const thinking = parts
    .filter((p) => p && p.kind === 'think')
    .map((p) => String(p.text || '').trim())
    .filter(Boolean)
    .join('\n\n');

  const operators = parts
    .filter((p) => p && p.kind === 'operator')
    .map((p) => String(p.text || '').trim())
    .filter(Boolean)
    .join('\n\n');

  if (title) title.textContent = `Turn ${turn}`;
  body.innerHTML = `
    <div class="turn-modal-block">
      <div class="turn-modal-title">Thinking</div>
      <pre class="turn-modal-pre">${escapeHtml(thinking || '…')}</pre>
    </div>
    <div class="turn-modal-block" style="margin-top: 12px;">
      <div class="turn-modal-title">Operator output</div>
      <pre class="turn-modal-pre">${escapeHtml(operators || '…')}</pre>
    </div>
  `;

  modal.classList.remove('hidden');
  modal.setAttribute('aria-hidden', 'false');
}

function closeTurnModal() {
  const modal = el('turnModal');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.setAttribute('aria-hidden', 'true');
}

function openOperatorModal(nodeId) {
  const modal = el('operatorModal');
  const body = el('operatorModalBody');
  const title = el('operatorModalTitle');
  if (!modal || !body) return;

  const node = treeIndex.get(nodeId);
  if (!node) return;

  const opFull = String(node.opFull || node.op_full || node.op || '').trim();
  const outTable = String(node.outTable || node.out_table || '').trim();
  const preview = node.outPreview || node.out_preview || null;
  const shape = preview && Array.isArray(preview.shape) ? preview.shape : null;

  if (title) title.textContent = String(node.label || node.opName || 'Operator');

  const previewHtml = preview
    ? renderTablePreview(preview, { maxRows: 20, maxCols: 20 })
    : '<div class="muted">No output preview.</div>';

  body.innerHTML = `
    <div class="turn-modal-block">
      <div class="turn-modal-title">Operator string</div>
      <pre class="turn-modal-pre">${escapeHtml(opFull || '…')}</pre>
    </div>
    <div class="turn-modal-block" style="margin-top: 12px;">
      <div class="turn-modal-title">Output table</div>
      <div class="muted">${escapeHtml(outTable || '—')}</div>
      ${shape ? `<div class="muted">shape: ${escapeHtml(String(shape[0]))} × ${escapeHtml(String(shape[1]))}</div>` : ''}
      <div style="margin-top: 8px;">${previewHtml}</div>
    </div>
  `;

  modal.classList.remove('hidden');
  modal.setAttribute('aria-hidden', 'false');
}

function closeOperatorModal() {
  const modal = el('operatorModal');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.setAttribute('aria-hidden', 'true');
}

function parseTaggedContent(content) {
  const t = String(content || '').trim();
  const tags = [
    { name: 'think', open: '<think>', close: '</think>' },
    { name: 'operator', open: '<operator>', close: '</operator>' },
    { name: 'solution', open: '<solution>', close: '</solution>' },
  ];
  for (const tag of tags) {
    if (t.startsWith(tag.open) && t.endsWith(tag.close)) {
      const inner = t.slice(tag.open.length, t.length - tag.close.length).trim();
      return { kind: tag.name, text: inner };
    }
  }
  return { kind: 'info', text: t };
}

function renderTablePreview(preview, { maxRows = 3, maxCols = 5 } = {}) {
  if (!preview) return '';
  const columns = Array.isArray(preview.columns) ? preview.columns : [];
  const rows = Array.isArray(preview.rows) ? preview.rows : [];

  const slicedCols = columns.slice(0, maxCols);
  const colOverflow = columns.length > maxCols;
  const displayCols = colOverflow ? [...slicedCols, '…'] : slicedCols;

  const slicedRows = rows.slice(0, maxRows).map((r) => {
    const rr = Array.isArray(r) ? r : [];
    const cells = rr.slice(0, maxCols);
    if (colOverflow) cells.push('…');
    return cells;
  });

  const thead = `<tr>${displayCols.map((c) => `<th>${escapeHtml(c)}</th>`).join('')}</tr>`;
  const tbody = slicedRows
    .map((r) => `<tr>${r.map((v) => `<td>${escapeHtml(v)}</td>`).join('')}</tr>`)
    .join('');
  return `<div class="table-preview"><table><thead>${thead}</thead><tbody>${tbody}</tbody></table></div>`;
}

function renderSetupTables(previews) {
  const box = el('tables');
  if (!box) return;
  box.innerHTML = '';
  for (const p of previews || []) {
    const card = document.createElement('div');
    card.className = 'table-card';
    const meta = `${(p.rows || []).length} preview rows · ${(p.columns || []).length} cols`;
    card.innerHTML = `
      <div class="name">${escapeHtml(p.name || 'table')}</div>
      <div class="meta">${escapeHtml(meta)}</div>
      ${renderTablePreview(p)}
    `;
    box.appendChild(card);
  }
}

function renderMiniTop(previews, targetDesc) {
  const tablesMini = el('tablesMini');
  const targetMini = el('targetDescMini');
  if (tablesMini) {
    tablesMini.innerHTML = '';
    for (const p of previews || []) {
      const mini = document.createElement('div');
      mini.className = 'mini-table';
      mini.innerHTML = `
        <div class="mini-hdr">${escapeHtml(p.name || 'table')}</div>
        <div class="mini-body">${renderTablePreview(p)}</div>
      `;
      tablesMini.appendChild(mini);
    }
  }
  if (targetMini) targetMini.textContent = String(targetDesc || '').trim();
}

async function uploadFiles() {
  setUiError('');
  const input = el('fileInput');
  const hint = el('uploadHint');
  if (!input || !input.files || input.files.length === 0) {
    setUiError('Please choose one or more files.');
    return;
  }

  const fd = new FormData();
  for (const f of input.files) fd.append('files', f);

  if (hint) hint.textContent = 'Uploading…';
  try {
    const resp = await fetch('/ui/upload', { method: 'POST', body: fd });
    const data = await safeJson(resp);
    if (!resp.ok || !data) {
      throw new Error((data && data.error) || 'Upload failed');
    }

    uploadId = data.uploadId;
    window.__setupPreviews = data.tables || [];
    renderSetupTables(window.__setupPreviews);
    if (hint) hint.textContent = `Uploaded ${window.__setupPreviews.length} tables.`;
    updateStartEnabled();
  } catch (e) {
    setUiError(String(e && e.message ? e.message : e));
    if (hint) hint.textContent = 'Upload failed.';
  }
}

async function setTargetDescription() {
  setUiError('');
  if (!uploadId) {
    setUiError('Upload source tables first.');
    return;
  }
  const high = el('highLevel');
  const schema = el('schemaJson');
  const out = el('targetDesc');

  const fd = new FormData();
  fd.append('uploadId', uploadId);
  fd.append('highLevel', high ? high.value : '');
  fd.append('schemaJson', schema ? schema.value : '');

  try {
    const resp = await fetch('/ui/target_description', { method: 'POST', body: fd });
    const data = await safeJson(resp);
    if (!resp.ok || !data) {
      throw new Error((data && data.error) || 'Failed to set target description');
    }
    window.__targetDesc = data.targetDescription || '';
    if (out) out.textContent = window.__targetDesc;
    updateStartEnabled();
  } catch (e) {
    setUiError(String(e && e.message ? e.message : e));
  }
}

function updateStartEnabled() {
  const startBtn = el('startBtn');
  if (!startBtn) return;
  const ok = Boolean(uploadId) && Boolean(String(window.__targetDesc || '').trim());
  startBtn.disabled = !ok;
}

function collapseSetupToTop() {
  const modal = el('setupModal');
  const summary = el('setupSummary');
  const runBtn = el('runBtn');
  const dock = el('controlDock');
  if (!modal || !summary) return;

  // Render top summary before collapse completes.
  renderMiniTop(window.__setupPreviews || [], window.__targetDesc || '');

  modal.classList.add('collapsing');
  window.setTimeout(() => {
    modal.classList.add('hidden');
    modal.classList.remove('collapsing');
    summary.classList.remove('hidden');
    if (runBtn) runBtn.disabled = false;
		if (dock) dock.classList.remove('hidden');
  }, 520);
}

function resetRunUi() {
  latestTree = null;
  treeIndex = new Map();
  nodeEls = new Map();
  seenNodeIds = new Set();
  turns = new Map();
  currentTurn = null;

  const list = el('turnList');
  if (list) list.innerHTML = '';
  const treeBox = el('tree');
  if (treeBox) treeBox.innerHTML = '';
  clearTurnFocus();
}

async function runAgent() {
  setUiError('');
  if (!uploadId) {
    setUiError('Missing upload session.');
    return;
  }
  resetRunUi();
  setStatus('starting');

  const fd = new FormData();
  fd.append('uploadId', uploadId);

  // Optional runtime override
  const maxTurnEl = el('maxExploreTurn');
  if (maxTurnEl && String(maxTurnEl.value || '').trim() !== '') {
    fd.append('maxExploreTurn', String(maxTurnEl.value).trim());
  }

  try {
    const resp = await fetch('/ui/run', { method: 'POST', body: fd });
    const data = await safeJson(resp);
    if (!resp.ok || !data || !data.trialId) {
      throw new Error((data && data.error) || 'Failed to start run');
    }
    trialId = data.trialId;
    connectWs(trialId);
  } catch (e) {
    setStatus('failed');
    setUiError(String(e && e.message ? e.message : e));
  }
}

function connectWs(trialId) {
  if (ws) {
    try { ws.close(); } catch {}
    ws = null;
  }
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${proto}://${location.host}/ws/${trialId}`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    setStatus('running');
  };

  ws.onmessage = (evt) => {
    let msg = null;
    try {
      msg = JSON.parse(evt.data);
    } catch {
      return;
    }
    handleEvent(msg);
  };

  ws.onclose = () => {
    // Keep last status; UI stays.
  };

  ws.onerror = () => {
    setUiError('WebSocket error.');
  };
}

function handleEvent(event) {
  const type = event && event.type;
  if (!type) return;

  if (type === 'status') {
    const status = String(event.status || '').trim();
    setStatus(status);
    const t = parseTurnFromStatus(status);
    if (t) {
      currentTurn = t;
      ensureTurn(t);
      renderTurns();
    }
    return;
  }

  if (type === 'chat') {
    // Capture per-turn model output so the turn chip can expand to show it.
    const { kind, text } = parseTaggedContent(event.content);
    if (currentTurn) {
      const rec = ensureTurn(currentTurn);
      if (!Array.isArray(rec.outputs)) rec.outputs = [];
      rec.outputs.push({ kind, text, ts: Date.now() });
      if (kind === 'think') rec.thinking = text;
      rec.lastUpdatedAt = Date.now();
      renderTurns();
    }
    return;
  }

  if (type === 'tree') {
    latestTree = event.tree;
    renderTree(latestTree);
    refreshTurnStatsFromTree(latestTree);
    renderTurns();
    return;
  }

  if (type === 'highlight') {
    const path = Array.isArray(event.path) ? event.path : [];
    highlightPath(path);
    return;
  }

  if (type === 'result') {
    // event.preview is already a df_preview
    openResultModal(event);
    return;
  }
}

function refreshTurnStatsFromTree(tree) {
  const stats = new Map();
  treeIndex = new Map();

  function walk(node) {
    if (!node || typeof node !== 'object') return;
    treeIndex.set(node.id, node);

    const t = Number(node.createdTurn);
    if (Number.isFinite(t) && t > 0 && node.op !== 'ROOT' && !node.isSolution) {
      if (!stats.has(t)) stats.set(t, { operatorCount: 0, tables: new Set() });
      const s = stats.get(t);
      s.operatorCount += 1;
      for (const tb of node.tables || []) s.tables.add(tb);
    }

    for (const ch of node.children || []) walk(ch);
  }

  walk(tree);

  // Merge into existing turn records
  for (const [turn, s] of stats.entries()) {
    const rec = ensureTurn(turn);
    rec.operatorCount = s.operatorCount;
    rec.tables = Array.from(s.tables.values()).sort();
    rec.lastUpdatedAt = Date.now();
  }
}

function renderTurns() {
  const list = el('turnList');
  if (!list) return;

  const items = Array.from(turns.values()).sort((a, b) => a.turn - b.turn);
  list.innerHTML = '';

  for (const rec of items) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'turn-chip';

    const opCnt = Number(rec.operatorCount || 0);
    if (rec.turn === currentTurn && isExploringNow()) {
      btn.textContent = `Turn ${rec.turn} · Exploring...`;
    } else {
      btn.textContent = `Turn ${rec.turn} · ${opCnt} Op`;
    }

    btn.addEventListener('mouseenter', () => focusTurn(rec.turn));
    btn.addEventListener('mouseleave', () => clearTurnFocus());
    btn.addEventListener('click', () => openTurnModal(rec.turn));

    list.appendChild(btn);
  }
}

function focusTurn(turn) {
  const treeBox = el('tree');
  if (!treeBox) return;
  treeBox.classList.add('turn-focus');

  for (const [id, nodeEl] of nodeEls.entries()) {
    nodeEl.classList.remove('turn-hit');
    const node = treeIndex.get(id);
    if (!node) continue;
    if (Number(node.createdTurn) === Number(turn)) nodeEl.classList.add('turn-hit');
  }
}

function clearTurnFocus() {
  const treeBox = el('tree');
  if (!treeBox) return;
  treeBox.classList.remove('turn-focus');
  for (const nodeEl of nodeEls.values()) nodeEl.classList.remove('turn-hit');
}

function renderTree(tree) {
  const box = el('tree');
  if (!box) return;

  nodeEls = new Map();

  // Start node (always)
  const start = document.createElement('div');
  const startNode = document.createElement('span');
  startNode.className = 'node';
  startNode.textContent = 'Start';
  start.appendChild(startNode);
  box.innerHTML = '';
  box.appendChild(start);

  const rootChildren = (tree && tree.children) || [];
  const ul = document.createElement('ul');
  for (const child of rootChildren) {
    ul.appendChild(renderTreeNode(child));
  }
  box.appendChild(ul);
}

function isErrorNode(node) {
  const out = String(node && node.outTable ? node.outTable : '').toLowerCase();
  return out === 'error' || out.includes('error');
}

function renderTreeNode(node) {
  const li = document.createElement('li');
  const span = document.createElement('span');
  span.className = 'node';

  if (node.isSolution) span.classList.add('solution');
  if (isErrorNode(node)) span.classList.add('error');

  span.textContent = String(node.label || node.op || 'op');

  span.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    openOperatorModal(node.id);
  });

  if (!seenNodeIds.has(node.id)) {
    span.classList.add('new-node');
    seenNodeIds.add(node.id);
  }

  li.appendChild(span);
  nodeEls.set(node.id, span);

  const children = Array.isArray(node.children) ? [...node.children] : [];
  if (children.length) {
    // Keep newly expanded branches on the far right (i.e., last among siblings).
    children.sort((a, b) => {
      const aSeen = seenNodeIds.has(a && a.id);
      const bSeen = seenNodeIds.has(b && b.id);
      if (aSeen !== bSeen) return aSeen ? -1 : 1;
      return 0;
    });
    const ul = document.createElement('ul');
    for (const ch of children) ul.appendChild(renderTreeNode(ch));
    li.appendChild(ul);
  }
  return li;
}

function highlightPath(pathIds) {
  // Subtle flash on nodes in path
  for (const eln of nodeEls.values()) eln.classList.remove('highlight');
  for (const id of pathIds || []) {
    const nodeEl = nodeEls.get(id);
    if (nodeEl) nodeEl.classList.add('highlight');
  }
  window.setTimeout(() => {
    for (const id of pathIds || []) {
      const nodeEl = nodeEls.get(id);
      if (nodeEl) nodeEl.classList.remove('highlight');
    }
  }, 850);
}

function openResultModal(resultEvent) {
  const modal = el('resultModal');
  const body = el('modalBody');
  const download = el('modalDownloadBtn');
  const title = el('modalTitle');
  if (!modal || !body) return;

  const tableName = resultEvent.tableName || 'Target Table';
  if (title) title.textContent = tableName;
  body.innerHTML = `
    <div class="table-card">
      <div class="name">${escapeHtml(tableName)}</div>
      ${renderTablePreview(resultEvent.preview || {})}
    </div>
  `;

  if (download && trialId) {
    download.href = `/ui/trials/${trialId}/download`;
  }

  modal.classList.remove('hidden');
  modal.setAttribute('aria-hidden', 'false');
}

function closeResultModal() {
  const modal = el('resultModal');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.setAttribute('aria-hidden', 'true');
}

function wireEvents() {
  const uploadBtn = el('uploadBtn');
  if (uploadBtn) uploadBtn.addEventListener('click', uploadFiles);

  const setSchemaBtn = el('setSchemaBtn');
  if (setSchemaBtn) setSchemaBtn.addEventListener('click', setTargetDescription);

  const startBtn = el('startBtn');
  if (startBtn) startBtn.addEventListener('click', collapseSetupToTop);

  const runBtn = el('runBtn');
  if (runBtn) runBtn.addEventListener('click', runAgent);

  const llmSelect = el('llmSelect');
  if (llmSelect) {
    llmSelect.addEventListener('change', async () => {
      const v = String(llmSelect.value || '').trim();
      if (!v) return;
      await setActiveConfig(v, { updateMaxTurn: true });
    });
  }

  const maxTurnEl = el('maxExploreTurn');
  if (maxTurnEl) {
    maxTurnEl.addEventListener('input', () => {
      markUserEditedMaxTurn();
    });
  }

  const modalCloseBtn = el('modalCloseBtn');
  if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeResultModal);

  const modalBackdrop = el('modalBackdrop');
  if (modalBackdrop) modalBackdrop.addEventListener('click', closeResultModal);

  const turnModalCloseBtn = el('turnModalCloseBtn');
  if (turnModalCloseBtn) turnModalCloseBtn.addEventListener('click', closeTurnModal);

  const turnModalBackdrop = el('turnModalBackdrop');
  if (turnModalBackdrop) turnModalBackdrop.addEventListener('click', closeTurnModal);

  const operatorModalCloseBtn = el('operatorModalCloseBtn');
  if (operatorModalCloseBtn) operatorModalCloseBtn.addEventListener('click', closeOperatorModal);

  const operatorModalBackdrop = el('operatorModalBackdrop');
  if (operatorModalBackdrop) operatorModalBackdrop.addEventListener('click', closeOperatorModal);
}

function init() {
  window.__setupPreviews = [];
  window.__targetDesc = '';
  setStatus('idle');
  setUiError('');
  const maxTurnEl = el('maxExploreTurn');
  if (maxTurnEl && !maxTurnEl.dataset.userEdited && !String(maxTurnEl.value || '').trim()) {
    maxTurnEl.value = String(DEFAULT_MAX_EXPLORE_TURN);
  }
  wireEvents();
	loadLlmConfigs();
}

document.addEventListener('DOMContentLoaded', init);

// --- Legacy UI code (disabled) ---
// This repository previously had a different UI implementation appended below.
// Keep it wrapped to avoid running it and to avoid variable redeclarations.
function __legacy_disabled__() {
let uploadId = null;
let trialId = null;
let ws = null;
let treeIndex = new Map();
let parentIndex = new Map();

const el = (id) => document.getElementById(id);

const TURN_COLORS = [
  '#284bff',
  '#0ea5e9',
  '#10b981',
  '#f59e0b',
  '#a855f7',
  '#ef4444',
  '#14b8a6',
  '#64748b',
];

function turnColor(turn) {
  const n = Number(turn);
  if (!Number.isFinite(n) || n <= 0) return null;
  return TURN_COLORS[(n - 1) % TURN_COLORS.length];
}

function setTreeActivity(statusText) {
  const box = el('treeActivity');
  if (!box) return;
  const t = String(statusText || '').trim().toLowerCase();

  const isWorking =
    t.startsWith('starting') ||
    t.startsWith('running') ||
    t.startsWith('thinking') ||
    t.startsWith('executing');

  if (!isWorking) {
    box.classList.add('hidden');
    box.textContent = '';
    return;
  }

  if (t.startsWith('thinking')) {
    box.textContent = 'LLM is thinking… generating the next operator chain. (This may take a while.)';
  } else if (t.startsWith('executing')) {
    box.textContent = 'Executing final operator chain to materialize the target table…';
  } else {
    box.textContent = 'Agent is running…';
  }
  box.classList.remove('hidden');
}

function clearChat() {
  const chat = el('chat');
  if (chat) chat.innerHTML = '';
}

function parseTaggedContent(content) {
  const t = String(content || '').trim();
  const tags = [
    { name: 'think', open: '<think>', close: '</think>' },
    { name: 'operator', open: '<operator>', close: '</operator>' },
    { name: 'solution', open: '<solution>', close: '</solution>' },
  ];
  for (const tag of tags) {
    if (t.startsWith(tag.open) && t.endsWith(tag.close)) {
      const inner = t.slice(tag.open.length, t.length - tag.close.length).trim();
      return { kind: tag.name, text: inner };
    }
  }
  return { kind: 'info', text: t };
}

function appendChatMessage({ role, content }) {
  const chat = el('chat');
  if (!chat) return;

  const { kind, text } = parseTaggedContent(content);

  const wrap = document.createElement('div');
  wrap.className = `msg ${kind}`;

  const hdr = document.createElement('div');
  hdr.className = 'hdr';

  const tag = document.createElement('div');
  tag.className = 'tag';
  tag.textContent = kind.toUpperCase();

  const r = document.createElement('div');
  r.className = 'role';
  r.textContent = role ? String(role) : 'assistant';

  hdr.appendChild(tag);
  hdr.appendChild(r);
  wrap.appendChild(hdr);

  if (kind === 'think') {
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = 'Thought process (click to expand)';
    const body = document.createElement('div');
    body.className = 'body';
    body.textContent = text;
    details.appendChild(summary);
    details.appendChild(body);
    wrap.appendChild(details);
  } else {
    const body = document.createElement('div');
    body.className = 'body';
    body.textContent = text;
    wrap.appendChild(body);
  }

  chat.appendChild(wrap);
  // Keep the latest info visible (no fancy animation).
  chat.scrollTop = chat.scrollHeight;
}

function renderTablePreview(preview) {
  const { columns, rows } = preview;
  const thead = `<tr>${columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr>`;
  const tbody = rows.map(r => `<tr>${r.map(v => `<td>${escapeHtml(v)}</td>`).join('')}</tr>`).join('');
  return `<div class="table-preview"><table><thead>${thead}</thead><tbody>${tbody}</tbody></table></div>`;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function ensureBackticks(s) {
  const t = String(s || '');
  if (!t) return '``';
  if (t.startsWith('`') && t.endsWith('`')) return t;
  // Avoid double-leading/back trailing; keep it simple.
  return '`' + t.replace(/^`+/, '').replace(/`+$/, '') + '`';
}

function truncateOpDisplay(text, maxChars = 40) {
  // Display rule: default each operator length <= maxChars; if exceeded use ellipsis,
  // and ensure it ends with a backtick.
  const wrapped = ensureBackticks(text);
  // Work on inner content (without surrounding backticks)
  const inner = wrapped.slice(1, -1);
  if (inner.length <= maxChars) return wrapped;
  const truncatedInner = inner.slice(0, Math.max(0, maxChars - 3)) + '...';
  return '`' + truncatedInner + '`';
}

function setStatus(text) {
  const s = el('status');
  if (!s) return;
  const t = String(text || '').trim() || 'idle';
  s.textContent = t;
  s.dataset.status = t.toLowerCase();

  // Also reflect progress in the operator tree area.
  setTreeActivity(t);
}

function setUiError(message) {
  const box = el('uiError');
  if (!box) return;
  const msg = String(message || '').trim();
  if (!msg) {
    box.classList.add('hidden');
    box.textContent = '';
    return;
  }
  box.textContent = msg;
  box.classList.remove('hidden');
}

function setControlsEnabled({ canUpload, canSetSchema, canRun }) {
  const uploadBtn = el('uploadBtn');
  const setSchemaBtn = el('setSchemaBtn');
  const runBtn = el('runBtn');
  if (uploadBtn) uploadBtn.disabled = !canUpload;
  if (setSchemaBtn) setSchemaBtn.disabled = !canSetSchema;
  if (runBtn) runBtn.disabled = !canRun;
}

function markUserEditedMaxTurn() {
  const maxTurnEl = el('maxExploreTurn');
  if (!maxTurnEl) return;
  maxTurnEl.dataset.userEdited = '1';
}

async function safeJson(resp) {
  try {
    return await resp.json();
  } catch {
    return null;
  }
}

async function loadLlmConfigs() {
  try {
    const resp = await fetch('/ui/configs');
    const data = await safeJson(resp);

    const sel = el('llmSelect');
    if (!sel) return;

    sel.innerHTML = '';
    for (const opt of (data.options || [])) {
      const o = document.createElement('option');
      o.value = opt.configName;
      o.textContent = opt.label;
      sel.appendChild(o);
    }

    if (data.activeConfigName) sel.value = data.activeConfigName;
    updateActiveLlmText(data.activeLabel, data.activeConfigName);

    const maxTurnEl = el('maxExploreTurn');
    if (
      maxTurnEl &&
      !maxTurnEl.dataset.userEdited &&
      typeof data.maxExploreTurn !== 'undefined' &&
      data.maxExploreTurn !== null
    ) {
      maxTurnEl.value = String(data.maxExploreTurn);
    }
  } catch (e) {
    // best-effort
  }
}

function updateActiveLlmText(activeLabel, activeConfigName) {
  const box = el('activeLlm');
  if (!box) return;
  if (activeLabel && activeConfigName) {
    box.textContent = `active: ${activeLabel}  (${activeConfigName})`;
  } else if (activeConfigName) {
    box.textContent = `active: ${activeConfigName}`;
  } else {
    box.textContent = '';
  }
}

async function setActiveConfig(configName, { updateMaxTurn = true } = {}) {
  setUiError('');
  const resp = await fetch('/ui/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ configName }),
  });
  const data = await safeJson(resp);
  if (!resp.ok || !data || !data.ok) {
    setStatus('failed');
    const msg = data && data.error ? data.error : 'Failed to set config';
    setUiError(msg);
    return;
  }
  updateActiveLlmText(data.activeLabel, data.activeConfigName);
  const maxTurnEl = el('maxExploreTurn');
  if (
    updateMaxTurn &&
    maxTurnEl &&
    !maxTurnEl.dataset.userEdited &&
    typeof data.maxExploreTurn !== 'undefined' &&
    data.maxExploreTurn !== null
  ) {
    maxTurnEl.value = String(data.maxExploreTurn);
  }
  setStatus('config switched');
}

function showResultModal({ tableName, preview, downloadUrl }) {
  const modal = el('resultModal');
  const body = el('modalBody');
  const dl = el('modalDownloadBtn');
  const title = el('modalTitle');

  if (title) title.textContent = tableName ? `Target Table: ${tableName}` : 'Target Table';
  if (body) {
    const r = preview;
    body.innerHTML = `
      <div class="meta">shape: ${r.shape[0]} x ${r.shape[1]}</div>
      ${renderTablePreview(r)}
    `;
  }
  if (dl) dl.href = downloadUrl;

  modal.classList.remove('hidden');
  modal.setAttribute('aria-hidden', 'false');
}

function hideResultModal() {
  const modal = el('resultModal');
  modal.classList.add('hidden');
  modal.setAttribute('aria-hidden', 'true');
}

function wsBaseUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}`;
}

function renderTree(node, container) {
  container.innerHTML = '';
  const ul = document.createElement('ul');
  treeIndex = new Map();
  parentIndex = new Map();
  ul.appendChild(renderTreeNode(node, null));
  container.appendChild(ul);
}

function renderTreeNode(node, parentId) {
  const li = document.createElement('li');

  if (node.op !== 'ROOT') {
    const span = document.createElement('span');
    const isError = (node.execStatus === 'error') || (node.outTable === 'Error');
    span.className = 'node'
      + (node.isSolution ? ' solution' : '')
      + (isError ? ' error' : '');
    const displayText = node.label || node.op;
    span.textContent = truncateOpDisplay(displayText, 40);
    span.dataset.nodeId = node.id;

    // Color by turn/round (same turn => same border color). Keep solution/error styling.
    const c = (!node.isSolution && !isError) ? turnColor(node.createdTurn) : null;
    if (c) {
      span.style.borderColor = c;
      span.style.borderWidth = '2px';
    }
    li.appendChild(span);

    treeIndex.set(node.id, node);
    parentIndex.set(node.id, parentId);
  }

  if (node.children && node.children.length) {
    const ul = document.createElement('ul');
    for (const c of node.children) {
      ul.appendChild(renderTreeNode(c, node.op === 'ROOT' ? null : node.id));
    }
    li.appendChild(ul);
  }

  return li;
}

function showOpDetails(node) {
  const box = el('opDetails');
  const meta = el('opDetailsMeta');
  const full = el('opDetailsFull');
  const preview = el('opDetailsPreview');

  if (!node) return;
  box.classList.remove('hidden');

  // Build full operator sequence (root -> this node) by walking parent pointers.
  const chain = [];
  let cur = node;
  while (cur && cur.id) {
    chain.push(cur.opFull || cur.op || '');
    const pid = parentIndex.get(cur.id);
    if (!pid) break;
    cur = treeIndex.get(pid);
  }
  chain.reverse();

  const tables = (node.tables || []).join(', ');
  const outTable = node.outTable || '(unknown)';
  meta.textContent = `tables: ${tables || '(none)'}    output_table: ${outTable}`;

  full.textContent = chain.filter(Boolean).join('\n--> ');

  if (node.outPreview && node.outPreview.columns) {
    preview.innerHTML = renderTablePreview(node.outPreview);
  } else {
    preview.innerHTML = '<div class="muted">No output preview available for this operator.</div>';
  }
}

function clearOpDetails() {
  el('opDetails').classList.add('hidden');
  el('opDetailsMeta').textContent = '';
  el('opDetailsFull').textContent = '';
  el('opDetailsPreview').innerHTML = '';
}

async function highlightPath(path) {
  // Clear any existing highlight
  document.querySelectorAll('.tree .node.highlight').forEach(n => n.classList.remove('highlight'));

  for (const id of path) {
    const node = document.querySelector(`.tree .node[data-node-id="${CSS.escape(id)}"]`);
    if (node) {
      node.classList.add('highlight');
      await new Promise(r => setTimeout(r, 300));
    }
  }
}

el('uploadBtn').addEventListener('click', async () => {
  const fileEl = el('fileInput');
  const files = fileEl ? fileEl.files : null;
  if (!files || files.length === 0) {
    setUiError('Please choose one or more CSV files first.');
    return;
  }

  setUiError('');
  setStatus('uploading');
  setControlsEnabled({ canUpload: false, canSetSchema: false, canRun: false });

  try {
    const fd = new FormData();
    for (const f of files) fd.append('files', f);

    const resp = await fetch('/ui/upload', { method: 'POST', body: fd });
    const data = await safeJson(resp);
    if (!resp.ok || !data || !data.uploadId) {
      throw new Error((data && data.error) ? data.error : 'Upload failed');
    }

    uploadId = data.uploadId;
    const tablesDiv = el('tables');
    if (tablesDiv) {
      tablesDiv.innerHTML = '';
      for (const t of (data.tables || [])) {
        const card = document.createElement('div');
        card.className = 'table-card';
        card.innerHTML = `
          <div class="name">${escapeHtml(t.name)}</div>
          <div class="meta">shape: ${t.shape[0]} x ${t.shape[1]}</div>
          ${renderTablePreview(t)}
        `;
        tablesDiv.appendChild(card);
      }
    }

    const hint = el('uploadHint');
    if (hint) hint.textContent = `Uploaded ${files.length} file(s).`;

    setStatus('tables uploaded');
    setControlsEnabled({ canUpload: true, canSetSchema: true, canRun: true });
  } catch (err) {
    setStatus('failed');
    setUiError(err instanceof Error ? err.message : String(err));
    setControlsEnabled({ canUpload: true, canSetSchema: Boolean(uploadId), canRun: Boolean(uploadId) });
  }
});

// LLM select wiring
if (el('llmSelect')) {
  el('llmSelect').addEventListener('change', async (e) => {
    const target = e.target;
    if (!(target instanceof HTMLSelectElement)) return;
    const configName = target.value;
    if (!configName) return;
    await setActiveConfig(configName, { updateMaxTurn: true });
  });
}

// Track user edits to max_explore_turn so we don't overwrite it.
if (el('maxExploreTurn')) {
  el('maxExploreTurn').addEventListener('input', () => markUserEditedMaxTurn());
}

el('setSchemaBtn').addEventListener('click', async () => {
  if (!uploadId) {
    setUiError('Please upload tables first.');
    return;
  }

  setUiError('');
  setStatus('saving');
  setControlsEnabled({ canUpload: true, canSetSchema: false, canRun: true });

  const fd = new FormData();
  fd.append('uploadId', uploadId);
  fd.append('highLevel', el('highLevel').value);
  fd.append('schemaJson', el('schemaJson').value);

  try {
    const resp = await fetch('/ui/target_description', { method: 'POST', body: fd });
    const data = await safeJson(resp);
    if (!resp.ok || !data) {
      throw new Error((data && data.error) ? data.error : 'Failed to set target description');
    }
    el('targetDesc').textContent = data.targetDescription || '';
    setStatus('target description set');
  } catch (err) {
    setStatus('failed');
    setUiError(err instanceof Error ? err.message : String(err));
  } finally {
    setControlsEnabled({ canUpload: true, canSetSchema: true, canRun: true });
  }
});

el('runBtn').addEventListener('click', async () => {
  if (!uploadId) {
    setUiError('Please upload tables first.');
    return;
  }

  setUiError('');

  // Ensure backend config matches current selection.
  const llmSel = el('llmSelect');
  if (llmSel && llmSel.value) {
    // Do NOT override the user's maxExploreTurn input when starting a run.
    try { await setActiveConfig(llmSel.value, { updateMaxTurn: false }); } catch (_) {}
  }

  setControlsEnabled({ canUpload: true, canSetSchema: true, canRun: false });
  setStatus('starting');
  hideResultModal();
  clearChat();

  const fd = new FormData();
  fd.append('uploadId', uploadId);

  const maxTurnEl = el('maxExploreTurn');
  if (maxTurnEl && String(maxTurnEl.value || '').trim() !== '') {
    fd.append('maxExploreTurn', String(maxTurnEl.value));
  }

  try {
    const resp = await fetch('/ui/run', { method: 'POST', body: fd });
    const data = await safeJson(resp);
    if (!resp.ok || !data || !data.trialId) {
      throw new Error((data && data.error) ? data.error : 'Failed to start run');
    }
    trialId = data.trialId;

    if (ws) ws.close();
    ws = new WebSocket(`${wsBaseUrl()}/ws/${encodeURIComponent(trialId)}`);
  } catch (err) {
    setStatus('failed');
    setUiError(err instanceof Error ? err.message : String(err));
    setControlsEnabled({ canUpload: true, canSetSchema: true, canRun: true });
    return;
  }

  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);

    if (msg.type === 'status') {
      setStatus(msg.status);
      if (msg.status === 'done' || msg.status === 'failed') {
        setControlsEnabled({ canUpload: true, canSetSchema: true, canRun: true });
      }
      return;
    }

    if (msg.type === 'chat') {
      appendChatMessage({ role: msg.role, content: msg.content });
      return;
    }

    if (msg.type === 'tree') {
      renderTree(msg.tree, el('tree'));
      return;
    }

    if (msg.type === 'highlight') {
      highlightPath(msg.path);
      return;
    }

    if (msg.type === 'result') {
      showResultModal({
        tableName: msg.tableName || '',
        preview: msg.preview,
        downloadUrl: `/ui/trials/${trialId}/download`,
      });
      return;
    }
  };

  ws.onopen = () => {
    setStatus('running');
  };

  ws.onerror = () => {
    setStatus('error');
    setUiError('WebSocket error. Please retry Run Agent.');
    setControlsEnabled({ canUpload: true, canSetSchema: true, canRun: true });
  };

  ws.onclose = () => {
    // If it closes while still running, surface it.
    const s = el('status');
    const cur = s ? String(s.textContent || '').toLowerCase() : '';
    if (cur && cur !== 'done' && cur !== 'failed') {
      setStatus('disconnected');
      setUiError('Connection closed before completion. You can retry Run Agent.');
      setControlsEnabled({ canUpload: true, canSetSchema: true, canRun: true });
    }
  };
});

// Modal wiring
el('modalCloseBtn').addEventListener('click', () => hideResultModal());
el('modalBackdrop').addEventListener('click', () => hideResultModal());
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') hideResultModal();
});

// Operator details wiring
el('opDetailsClear').addEventListener('click', () => clearOpDetails());
el('tree').addEventListener('click', (e) => {
  const target = e.target;
  if (!(target instanceof HTMLElement)) return;
  if (!target.classList.contains('node')) return;
  const id = target.dataset.nodeId;
  if (!id) return;
  const node = treeIndex.get(id);
  if (node) showOpDetails(node);
});

// Initial load
loadLlmConfigs();

// Initial UI state
setControlsEnabled({ canUpload: true, canSetSchema: false, canRun: false });

}
