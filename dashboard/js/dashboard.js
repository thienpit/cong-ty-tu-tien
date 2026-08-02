/* ==========================================================================
 * Công Ty Tu Tiên — Dashboard frontend logic
 * Polls backend JSON endpoints every 5s and updates the DOM.
 * Endpoints: /api/agents, /api/system, /api/tokens, /api/crew
 * ========================================================================== */

'use strict';

/* --------------------------------------------------------------------------
 * Configuration
 * ------------------------------------------------------------------------ */

/* API base URL — auto-detect: localhost = local, otherwise use tunnel */
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE = isLocal ? '' : 'https://spyware-photo-economic-creature.trycloudflare.com';

const POLL_INTERVAL_MS = 5000; // 5 giây
const API_ENDPOINTS = {
  agents: API_BASE + '/api/agents',
  system: API_BASE + '/api/system',
  tokens: API_BASE + '/api/tokens',
  crew:   API_BASE + '/api/crew',
};

/* Map API keys / agent ids to display names + icons.
 * Cards are now: hermes (main brain), agent1/agent2 (cloud), ollama (local).
 * Old keys are kept as aliases so legacy backend payloads still resolve. */
const AGENT_META = {
  hermes:        { name: 'Hermes',   icon: '🤖' },
  danphong:      { name: 'Hermes',   icon: '🤖' },
  dan_phong:     { name: 'Hermes',   icon: '🤖' },
  dphong:        { name: 'Hermes',   icon: '🤖' },
  agent1:        { name: 'Agent 1',  icon: '🤖' },
  khiphong:      { name: 'Agent 1',  icon: '🤖' },
  khi_phong:     { name: 'Agent 1',  icon: '🤖' },
  code:          { name: 'Agent 1',  icon: '🤖' },
  agent2:        { name: 'Agent 2',  icon: '🤖' },
  chapsuduong:   { name: 'Agent 2',  icon: '🤖' },
  chap_su_duong: { name: 'Agent 2',  icon: '🤖' },
  data:          { name: 'Agent 2',  icon: '🤖' },
  ollama:        { name: 'Ollama',   icon: '🤖' },
  giamsat:       { name: 'Ollama',   icon: '🤖' },
  giam_sat:      { name: 'Ollama',   icon: '🤖' },
  qa:            { name: 'Ollama',   icon: '🤖' },
};

/* Map model names from calls_by_model to agent cards (token usage source).
 * Patterns are tested in order per model; first match wins. */
const AGENT_MODEL_PATTERNS = [
  { id: 'hermes', patterns: [/auto\/best-chat/i, /^auto$/i, /auto\//i] },
  { id: 'agent1', patterns: [/gemini\//i, /opencode\//i] },
  { id: 'agent2', patterns: [/nvidia\//i, /deepseek\//i, /groq\//i] },
  { id: 'ollama', patterns: [/qwen3/i, /ollama/i] },
];

/* Vietnamese labels for status values */
const STATUS_LABELS = {
  working:   'working',
  active:    'working',
  running:   'working',
  completed: 'idle',
  done:      'idle',
  idle:      'idle',
  error:     'error',
  offline:   'error',
  failed:    'error',
};

/* Element id suffix per agent card (matches index.html ids) */
const AGENT_IDS = ['hermes', 'agent1', 'agent2', 'ollama'];

let refreshTimer = null;
let refreshCountdown = POLL_INTERVAL_MS / 1000;

// Token time range filter
let currentTokenRange = '1d'; // default: today

function updateTokenRange(range) {
  currentTokenRange = range;
  // Update active button styling using IDs
  document.querySelectorAll('.token-filter button').forEach(btn => {
    btn.classList.toggle('active', btn.id === `btn-${range}`);
  });
  // Re-fetch tokens immediately
  fetchJson(API_ENDPOINTS.tokens + '?range=' + range)
    .then(renderTokens)
    .catch(() => {});
}

/* --------------------------------------------------------------------------
 * Utilities
 * ------------------------------------------------------------------------ */

/** Format number with comma thousands separators: 1234567 -> "1,234,567" */
function formatNumber(value) {
  const num = Number(value);
  if (value === null || value === undefined || Number.isNaN(num)) {
    return '0';
  }
  return Math.round(num).toLocaleString('en-US');
}

/** Clamp a percentage into 0..100 */
function clampPercent(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return 0;
  return Math.max(0, Math.min(100, num));
}

/**
 * Convert a timestamp / date string / epoch ms into a Vietnamese
 * relative time string: 'vừa xong', '12 giây trước', '2 phút trước', ...
 */
function relativeTime(value) {
  if (value === null || value === undefined || value === '') {
    return '--';
  }

  let timeMs;
  if (typeof value === 'number') {
    // Heuristic: If it's a huge epoch (like 1785566767.27), it's seconds.
    // If it's even bigger (1e12+), it's milliseconds.
    timeMs = value > 1e12 ? value : value * 1000;
  } else if (typeof value === 'string') {
    const parsed = Date.parse(value);
    if (Number.isNaN(parsed)) {
      // Not parseable — show raw value rather than garbage
      return value;
    }
    timeMs = parsed;
  } else {
    return '--';
  }

    const nowMs = Date.now();
    const diffSec = Math.max(0, Math.floor((nowMs - timeMs) / 1000));

    // Debugging: If diff is too large (like years), the timestamp is likely wrong/future.
    // Epoch 1.7e9 is 2023-2024. If we see 1785570109, that's Year 2026.
    // Our Date.now() should be around there too.
    if (diffSec > 31536000 * 5) return 'rất lâu trước'; // > 5 years

  if (diffSec < 5) return 'vừa xong';
  if (diffSec < 60) return `${diffSec} giây trước`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} phút trước`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} giờ trước`;
  const diffDay = Math.floor(diffHour / 24);
  return `${diffDay} ngày trước`;
}

/** Escape user-supplied strings before injecting into innerHTML */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Set a section (by element) into an error state */
function markSectionError(element, message) {
  if (!element) return;
  element.classList.add('error-state');
  let errBox = element.querySelector('.error-message');
  if (!errBox) {
    errBox = document.createElement('div');
    errBox.className = 'error-message';
    element.appendChild(errBox);
  }
  errBox.textContent = message;
}

/** Clear a section error state */
function clearSectionError(element) {
  if (!element) return;
  element.classList.remove('error-state');
  const errBox = element.querySelector('.error-message');
  if (errBox) errBox.remove();
}

/* --------------------------------------------------------------------------
 * Connection indicator
 * ------------------------------------------------------------------------ */

function setConnected(connected) {
  const dot = document.getElementById('connection-dot');
  const label = document.getElementById('connection-label');
  if (!dot || !label) return;

  if (connected) {
    dot.className = 'status-dot status-dot--connected';
    label.textContent = 'Đã kết nối';
  } else {
    dot.className = 'status-dot status-dot--disconnected';
    label.textContent = 'Mất kết nối';
  }
}

/* --------------------------------------------------------------------------
 * Section renderers
 * ------------------------------------------------------------------------ */

/**
 * Render agent cards from /api/agents.
 * Accepts: array of {id/name, status, last_activity/lastActivity, tokens},
 * or object keyed by agent id, or object with .agents key.
 * Token usage bars are driven by calls_total / calls_by_model:
 * model names are matched against AGENT_MODEL_PATTERNS and each agent's
 * bar shows its share of the total calls as a percentage.
 */
function renderAgents(payload) {
  const data = (payload && typeof payload === 'object' && !Array.isArray(payload) && payload.agents)
    ? payload.agents
    : payload;
  const crewData = payload?.crew ?? {};

  // Token usage: agents already carry per-agent token counts from backend
  const totalTokens = Object.values(data).reduce((sum, a) => sum + Number(a?.tokens ?? 0), 0);

  const agents = {};
  if (Array.isArray(data)) {
    data.forEach((a) => {
      if (a && typeof a === 'object') {
        const key = String(a.id || a.name || a.agent || '').toLowerCase();
        if (key) agents[key] = a;
      }
    });
  } else if (data && typeof data === 'object') {
    Object.entries(data).forEach(([key, a]) => {
      if (a && typeof a === 'object') agents[String(key).toLowerCase()] = a;
    });
  }

  AGENT_IDS.forEach((id) => {
    const meta = AGENT_META[id];
    let info = agents[id];

    // Fall back to alternate keys (e.g. "code" -> agent1)
    if (!info) {
      for (const [key, val] of Object.entries(agents)) {
        if (AGENT_META[key] && AGENT_META[key].name === meta.name) {
          info = val;
          break;
        }
      }
    }

    const card = document.getElementById(`agent-${id}`);
    if (!card) return;
    clearSectionError(card);

    if (!info) {
      setAgentStatus(id, 'idle', '--', info?.tokens ?? 0, totalTokens);
      return;
    }

    const rawStatus = String(info.status || info.state || 'idle').toLowerCase();
    const status = STATUS_LABELS[rawStatus] || (rawStatus === 'idle' ? 'idle' : rawStatus);
    // Prefer crew status/last_active (has real timestamps from OmniRoute logs)
    const crew = crewData[id] || {};
    const lastActivity = crew.last_active ?? info.last_activity ?? info.lastActivity ?? info.updated_at ?? null;
    // Prefer per-agent token count from backend
    const tokenCount = Number(info.tokens ?? 0) || 0;

    setAgentStatus(id, status, lastActivity, tokenCount, totalTokens);
  });
}

/** Count API calls per agent by matching model names (calls_by_model). */
function countCallsByAgent(callsByModel) {
  const counts = {};
  AGENT_IDS.forEach((id) => { counts[id] = 0; });

  if (!callsByModel || typeof callsByModel !== 'object') return counts;

  const entries = Array.isArray(callsByModel)
    ? callsByModel
        .filter((b) => b && typeof b === 'object')
        .map((b) => [String(b.model ?? b.name ?? b.id ?? ''), Number(b.count ?? b.calls ?? 1)])
    : Object.entries(callsByModel).map(([model, count]) => [String(model), Number(count)]);

  entries.forEach(([model, count]) => {
    if (!model) return;
    const n = Number.isFinite(count) ? count : 0;
    if (n <= 0) return;
    for (const rule of AGENT_MODEL_PATTERNS) {
      if (rule.patterns.some((re) => re.test(model))) {
        counts[rule.id] += n;
        break;
      }
    }
  });

  return counts;
}

/** Update a single agent card's status dot, text, last activity & token bar */
function setAgentStatus(id, status, lastActivity, tokenCount, totalTokensArg) {
  const validStatus = ['working', 'idle', 'error'].includes(status) ? status : 'idle';

  const card = document.getElementById(`agent-${id}`);
  const dot = document.getElementById(`agent-${id}-status-dot`);
  const text = document.getElementById(`agent-${id}-status`);
  const activity = document.getElementById(`agent-${id}-last-activity`);
  const tokensEl = document.getElementById(`agent-${id}-tokens`);
  const tokenBar = document.getElementById(`agent-${id}-token-bar`);

  if (card) {
    card.classList.toggle('agent-card--error', validStatus === 'error');
  }
  if (dot) {
    dot.className = `status-dot status-dot--${validStatus}`;
  }
  if (text) {
    text.textContent = STATUS_LABELS[status] || status;
    text.className = `agent-status-text agent-status-text--${validStatus}`;
  }
    if (activity) {
    if (status === 'completed') {
      activity.textContent = 'Xong';
    } else {
      activity.textContent = relativeTime(lastActivity);
    }
  }

  const count = Number(tokenCount) || 0;
  if (tokensEl) {
    tokensEl.textContent = `${formatNumber(count)} tokens`;
  }
  if (tokenBar) {
    const total = Number(totalTokensArg) || 0;
    const pct = total > 0 ? clampPercent((count / total) * 100) : 0;
    tokenBar.style.width = `${pct}%`;
  }
}

/** Render system metrics from /api/system */
function renderSystem(payload) {
  const section = document.getElementById('metrics-bar');
  if (!section) return;

  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    markSectionError(section, 'Không có dữ liệu hệ thống');
    return;
  }
  clearSectionError(section);

  const s = payload;
  const cpu = s.cpu ?? s.cpu_percent ?? 0;
  const memRaw = s.memory ?? s.ram ?? 0;
  const ram = typeof memRaw === 'object' && memRaw !== null ? (memRaw.percent ?? 0) : Number(memRaw) || 0;
  const diskRaw = s.disk ?? 0;
  const disk = typeof diskRaw === 'object' && diskRaw !== null ? (diskRaw.percent ?? 0) : Number(diskRaw) || 0;
  const vramRaw = s.vram ?? null;

  const setMetric = (barId, valueId, value) => {
    const bar = document.getElementById(barId);
    const val = document.getElementById(valueId);
    const pct = clampPercent(value);
    if (bar) bar.style.width = `${pct}%`;
    if (val) val.textContent = `${pct.toFixed(0)}%`;
  };

  setMetric('cpu-bar', 'cpu-value', cpu);
  setMetric('ram-bar', 'ram-value', ram);
  setMetric('disk-bar', 'disk-value', disk);

  const vramBar = document.getElementById('vram-bar');
  const vramVal = document.getElementById('vram-value');
  if (vramRaw === null || vramRaw === undefined) {
    if (vramBar) vramBar.style.width = '0%';
    if (vramVal) vramVal.textContent = 'n/a';
  } else {
    const pct = clampPercent(Number(vramRaw));
    if (vramBar) vramBar.style.width = `${pct}%`;
    if (vramVal) vramVal.textContent = `${pct.toFixed(0)}%`;
  }
}

/** Render token summary from /api/tokens */
function renderTokens(payload) {
  const section = document.getElementById('token-summary');
  const breakdown = document.getElementById('token-breakdown');
  const totalEl = document.getElementById('tokens-total');
  if (!section) return;

  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    markSectionError(section, 'Không có dữ liệu token');
    return;
  }
  clearSectionError(section);

  // Total: payload.total || sum of breakdown || payload.tokens
  const total = Number(payload.total ?? payload.total_tokens ?? payload.tokens ?? 0);

  // Breakdown: payload.by_model || payload.models || payload.breakdown
  let breakdownData = payload.by_model ?? payload.models ?? payload.breakdown ?? null;
  if (breakdownData && typeof breakdownData === 'object' && breakdownData.total !== undefined) {
    // Sometimes breakdown objects carry their own total — drop it
    const { total: _t, ...rest } = breakdownData;
    breakdownData = rest;
  }

  if (totalEl) {
    totalEl.textContent = formatNumber(
      Number.isFinite(total) ? total : sumBreakdown(breakdownData)
    );
  }

  if (!breakdown) return;

  if (!breakdownData || (Array.isArray(breakdownData) && breakdownData.length === 0)
      || (typeof breakdownData === 'object' && Object.keys(breakdownData).length === 0)) {
    breakdown.innerHTML = '<div class="token-model-item"><span class="token-model-name skeleton">Chưa có dữ liệu</span></div>';
    return;
  }

  // Normalize: array of {model, tokens} OR object {model: tokens}
  let entries = [];
  if (Array.isArray(breakdownData)) {
    entries = breakdownData
      .filter((b) => b && typeof b === 'object')
      .map((b) => ({
        model: String(b.model ?? b.name ?? b.id ?? 'unknown'),
        tokens: Number(b.tokens ?? b.count ?? b.value ?? 0),
      }));
  } else if (typeof breakdownData === 'object') {
    entries = Object.entries(breakdownData).map(([model, tokens]) => ({
      model,
      tokens: Number(tokens),
    }));
  }

  const maxTokens = Math.max(1, ...entries.map((e) => e.tokens));

  breakdown.innerHTML = entries.map((entry) => {
    const pct = (entry.tokens / maxTokens) * 100;
    return `
      <div class="token-model-item">
        <span class="token-model-name" title="${escapeHtml(entry.model)}">${escapeHtml(entry.model)}</span>
        <div class="token-model-track">
          <div class="token-model-fill" style="width: ${pct.toFixed(1)}%"></div>
        </div>
        <span class="token-model-value">${formatNumber(entry.tokens)}</span>
      </div>`;
  }).join('');
}

function sumBreakdown(breakdownData) {
  if (!breakdownData) return 0;
  if (Array.isArray(breakdownData)) {
    return breakdownData.reduce((acc, b) => acc + Number(b?.tokens ?? b?.count ?? 0), 0);
  }
  if (typeof breakdownData === 'object') {
    return Object.values(breakdownData).reduce((acc, v) => acc + Number(v ?? 0), 0);
  }
  return 0;
}

/** Render recent API calls from /api/crew */
function renderCrew(payload) {
  const tbody = document.getElementById('api-table-body');
  const table = document.getElementById('api-table');
  if (!tbody) return;

  const section = table ? table.closest('.table-wrapper') : null;
  if (!payload || (Array.isArray(payload) && payload.length === 0)) {
    tbody.innerHTML = '<tr class="table-empty"><td colspan="4">Chưa có dữ liệu</td></tr>';
    return;
  }
  if (section) clearSectionError(section);

  let calls = Array.isArray(payload) ? payload : (payload.recent_calls ?? payload.calls ?? payload.logs ?? payload.recent ?? []);

  if (!Array.isArray(calls) || calls.length === 0) {
    tbody.innerHTML = '<tr class="table-empty"><td colspan="4">Chưa có dữ liệu</td></tr>';
    return;
  }

  // Show most recent first, cap at 20 rows
  const rows = calls
    .slice()
    .sort((a, b) => (Number(b.timestamp ?? b.time ?? 0) - Number(a.timestamp ?? a.time ?? 0)))
    .slice(0, 20);

  tbody.innerHTML = rows.map((call) => {
    const time = call.timestamp ?? call.time ?? call.created_at ?? null;
    const model = String(call.model ?? call.model_name ?? 'unknown');
    const rawStatus = String(call.status ?? call.result ?? 'success').toLowerCase();
    const ok = rawStatus === 'success' || rawStatus === 'ok' || rawStatus === 'done'
      || rawStatus === 'completed' || rawStatus === '200';
    const pending = rawStatus === 'pending' || rawStatus === 'running' || rawStatus === 'processing';
    const badgeClass = ok ? 'badge--success' : (pending ? 'badge--pending' : 'badge--error');
    const statusLabel = ok ? 'Thành công' : (pending ? 'Đang chạy' : 'Thất bại');

    let duration = call.duration ?? call.duration_ms ?? call.latency ?? null;
    let durationText = '--';
    if (duration !== null && duration !== undefined) {
      const d = Number(duration);
      if (Number.isFinite(d)) {
        durationText = d >= 1000 ? `${(d / 1000).toFixed(2)}s` : `${d.toFixed(0)}ms`;
      }
    }

    return `
      <tr>
        <td class="mono" title="${escapeHtml(time ? String(time) : '')}">${escapeHtml(relativeTime(time))}</td>
        <td class="mono">${escapeHtml(model)}</td>
        <td><span class="badge ${badgeClass}">${statusLabel}</span></td>
        <td class="mono">${durationText}</td>
      </tr>`;
  }).join('');
}

/* --------------------------------------------------------------------------
 * Fetch + polling
 * ------------------------------------------------------------------------ */

/** Fetch one endpoint with a timeout, log to console, throw on failure */
async function fetchJson(endpoint) {
  console.log(`[dashboard] Fetching ${endpoint}...`);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const res = await fetch(endpoint, {
      signal: controller.signal,
      headers: { 'Accept': 'application/json' },
      cache: 'no-store',
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status} for ${endpoint}`);
    }
    const json = await res.json();
    console.log(`[dashboard] ${endpoint} ->`, json);
    return json;
  } finally {
    clearTimeout(timer);
  }
}

/** Poll all endpoints; each failure is isolated so one bad API doesn't break the page */
async function pollAll() {
  console.log(`[dashboard] Poll cycle @ ${new Date().toISOString()}`);

  const results = await Promise.allSettled([
    fetchJson(API_ENDPOINTS.agents),
    fetchJson(API_ENDPOINTS.system),
    fetchJson(API_ENDPOINTS.tokens + '?range=' + currentTokenRange),
    fetchJson(API_ENDPOINTS.crew),
  ]);

  const [agentsRes, systemRes, tokensRes, crewRes] = results;
  let anyOk = false;

  if (agentsRes.status === 'fulfilled') {
    anyOk = true;
    renderAgents(agentsRes.value);
  } else {
    console.warn('[dashboard] /api/agents failed:', agentsRes.reason);
    const grid = document.getElementById('agent-grid');
    if (grid) markSectionError(grid, `Không tải được tác tử: ${agentsRes.reason.message || 'lỗi mạng'}`);
  }

  if (systemRes.status === 'fulfilled') {
    anyOk = true;
    renderSystem(systemRes.value);
  } else {
    console.warn('[dashboard] /api/system failed:', systemRes.reason);
    const bar = document.getElementById('metrics-bar');
    if (bar) markSectionError(bar, `Không tải được chỉ số hệ thống: ${systemRes.reason.message || 'lỗi mạng'}`);
  }

  if (tokensRes.status === 'fulfilled') {
    anyOk = true;
    renderTokens(tokensRes.value);
  } else {
    console.warn('[dashboard] /api/tokens failed:', tokensRes.reason);
    const summary = document.getElementById('token-summary');
    if (summary) markSectionError(summary, `Không tải được dữ liệu token: ${tokensRes.reason.message || 'lỗi mạng'}`);
  }

  if (crewRes.status === 'fulfilled') {
    anyOk = true;
    renderCrew(crewRes.value);
  } else {
    console.warn('[dashboard] /api/crew failed:', crewRes.reason);
    const wrapper = document.querySelector('.table-wrapper');
    if (wrapper) markSectionError(wrapper, `Không tải được lịch sử API: ${crewRes.reason.message || 'lỗi mạng'}`);
  }

  setConnected(anyOk);

  const lastUpdate = document.getElementById('last-update-time');
  if (lastUpdate) {
    lastUpdate.textContent = new Date().toLocaleTimeString('vi-VN');
  }
}

/* --------------------------------------------------------------------------
 * Refresh countdown indicator
 * ------------------------------------------------------------------------ */

function startCountdown() {
  refreshCountdown = POLL_INTERVAL_MS / 1000;
  const el = document.getElementById('refresh-countdown');
  if (!el) return;

  refreshTimer = setInterval(() => {
    refreshCountdown -= 1;
    if (refreshCountdown <= 0) refreshCountdown = POLL_INTERVAL_MS / 1000;
    if (el) el.textContent = `${refreshCountdown}s`;
  }, 1000);
}

/* --------------------------------------------------------------------------
 * Boot
 * ------------------------------------------------------------------------ */

async function init() {
  console.log('[dashboard] Initializing Công Ty Tu Tiên dashboard');

  // First paint immediately, then poll on the interval
  await pollAll();
  startCountdown();
  setInterval(pollAll, POLL_INTERVAL_MS);
}

// Run once the DOM is ready (script is loaded at end of body, but be safe)
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
