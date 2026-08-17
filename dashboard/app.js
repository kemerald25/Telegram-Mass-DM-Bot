/* ─────────────────────────────────────────────────────────
   TG DM Bot — Dashboard JS
   ───────────────────────────────────────────────────────── */

const API = '';  // same origin
let currentSection = 'overview';
let sseSource = null;
let statusPollInterval = null;

// ── API helper ─────────────────────────────────────────────
async function api(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
  };
  if (body !== null) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  return { status: res.status, data: await res.json() };
}

// ── Auth ───────────────────────────────────────────────────
async function checkAuth() {
  const { data } = await api('GET', '/auth/me');
  if (data.logged_in) {
    showApp();
  } else {
    showLogin();
  }
}

function showLogin() {
  document.getElementById('login-overlay').classList.remove('hidden');
  document.getElementById('app').classList.add('hidden');
}

function showApp() {
  document.getElementById('login-overlay').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
  loadSection(currentSection);
  startStatusPolling();
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const err = document.getElementById('login-error');
  const username = document.getElementById('login-user').value;
  const password = document.getElementById('login-pass').value;

  btn.disabled = true;
  btn.textContent = 'Signing in...';
  err.classList.add('hidden');

  const { status, data } = await api('POST', '/auth/login', { username, password });
  if (data.ok) {
    showApp();
  } else {
    err.textContent = data.error || 'Login failed';
    err.classList.remove('hidden');
  }
  btn.disabled = false;
  btn.textContent = 'Sign In →';
});

document.getElementById('logout-btn').addEventListener('click', async () => {
  await api('POST', '/auth/logout');
  stopSSE();
  stopStatusPolling();
  showLogin();
});

// ── Navigation ─────────────────────────────────────────────
function navigate(section) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));

  const navEl = document.querySelector(`.nav-item[data-section="${section}"]`);
  const secEl = document.getElementById(`section-${section}`);
  if (navEl) navEl.classList.add('active');
  if (secEl) secEl.classList.add('active');

  const titles = {
    overview: 'Overview', accounts: 'Accounts',
    proxy: 'Proxy Management', messages: 'Messages', campaign: 'Campaign',
    scraper: 'Scrape Members'
  };
  document.getElementById('page-title').textContent = titles[section] || section;
  currentSection = section;
  loadSection(section);
}

document.querySelectorAll('.nav-item').forEach(el => {
  el.addEventListener('click', (e) => {
    e.preventDefault();
    navigate(el.dataset.section);
  });
});

function loadSection(section) {
  if (section === 'overview')  loadOverview();
  if (section === 'accounts')  loadAccounts();
  if (section === 'proxy')     loadProxy();
  if (section === 'messages')  loadMessages();
  if (section === 'campaign')  loadCampaignStatus();
  if (section === 'scraper')   loadScraper();
}

// ── Overview ───────────────────────────────────────────────
async function loadOverview() {
  const [accRes, memRes, campRes] = await Promise.all([
    api('GET', '/api/accounts'),
    api('GET', '/api/members'),
    api('GET', '/api/campaign/status'),
  ]);

  document.getElementById('stat-accounts').textContent = accRes.data.accounts?.length ?? 0;
  document.getElementById('stat-members').textContent  = memRes.data.count ?? 0;
  document.getElementById('stat-sent').textContent     = campRes.data.sent ?? 0;
  document.getElementById('stat-status').textContent   = campRes.data.running ? 'Running' : 'Idle';
}

// ── Accounts ───────────────────────────────────────────────
async function loadAccounts() {
  const tbody = document.getElementById('accounts-tbody');
  tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Loading...</td></tr>';

  const { data } = await api('GET', '/api/accounts');
  const accounts = data.accounts || [];

  if (accounts.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">No accounts yet. Add one to get started.</td></tr>';
    return;
  }

  tbody.innerHTML = accounts.map(acc => `
    <tr>
      <td><strong>${esc(acc.phone)}</strong></td>
      <td style="color:var(--text-dim)">${esc(acc.api_id)}</td>
      <td>
        ${acc.proxy
          ? `<span class="badge badge-purple">🌐 ${esc(acc.proxy)}</span>`
          : `<span class="badge badge-gray">Direct</span>`}
      </td>
      <td>
        ${acc.has_session
          ? `<span class="badge badge-green">✓ Active</span>`
          : `<span class="badge badge-red">✗ No session</span>`}
      </td>
      <td>
        <button class="btn btn-danger btn-sm btn-icon" onclick="removeAccount('${esc(acc.phone)}')" title="Remove">✕</button>
      </td>
    </tr>
  `).join('');
}

async function removeAccount(phone) {
  if (!confirm(`Remove account ${phone}? This will delete its session file.`)) return;
  const { data } = await api('DELETE', `/api/accounts/${encodeURIComponent(phone)}`);
  if (data.ok) {
    loadAccounts();
    loadOverview();
  } else {
    alert(data.error || 'Failed to remove account');
  }
}

document.getElementById('add-account-btn').addEventListener('click', () => openModal());

// ── Add Account Modal ──────────────────────────────────────
let modalPhone = '';

function openModal() {
  modalPhone = '';
  document.getElementById('acc-phone').value = '';
  document.getElementById('acc-api-id').value = '';
  document.getElementById('acc-api-hash').value = '';
  document.getElementById('acc-otp').value = '';
  document.getElementById('acc-2fa').value = '';
  ['s1-error','s2-error','s3-error'].forEach(id => {
    const el = document.getElementById(id);
    el.classList.add('hidden');
    el.textContent = '';
  });
  showModalStep(1);
  document.getElementById('add-modal').classList.remove('hidden');
  document.getElementById('acc-phone').focus();
}

function closeModal() {
  document.getElementById('add-modal').classList.add('hidden');
}

function showModalStep(step) {
  ['modal-s1','modal-s2','modal-s3','modal-done'].forEach(id =>
    document.getElementById(id).classList.add('hidden'));
  document.getElementById(`modal-s${step === 'done' ? 'done-hidden' : step}`)?.classList.remove('hidden');

  if (step === 'done') {
    document.getElementById('modal-done').classList.remove('hidden');
  } else {
    document.getElementById(`modal-s${step}`).classList.remove('hidden');
  }

  // Update step indicators
  for (let i = 1; i <= 3; i++) {
    const el = document.getElementById(`ind-${i}`);
    el.classList.remove('active', 'done');
    if (i < step) el.classList.add('done');
    else if (i === step) el.classList.add('active');
  }
  for (let i = 1; i <= 2; i++) {
    const line = document.getElementById(`line-${i}`);
    line.classList.toggle('done', step > i);
  }
}

document.getElementById('close-modal-btn').addEventListener('click', closeModal);
document.getElementById('modal-backdrop').addEventListener('click', closeModal);
document.getElementById('modal-done-btn').addEventListener('click', () => {
  closeModal();
  loadAccounts();
  loadOverview();
});

// Step 1 — Send OTP
document.getElementById('send-otp-btn').addEventListener('click', async () => {
  const phone   = document.getElementById('acc-phone').value.trim();
  const api_id  = document.getElementById('acc-api-id').value.trim();
  const api_hash= document.getElementById('acc-api-hash').value.trim();
  const errEl   = document.getElementById('s1-error');
  const btn     = document.getElementById('send-otp-btn');

  errEl.classList.add('hidden');
  if (!phone) {
    errEl.textContent = 'Phone number is required.';
    errEl.classList.remove('hidden');
    return;
  }
  if ((api_id && !api_hash) || (!api_id && api_hash)) {
    errEl.textContent = 'Provide both API ID and API Hash, or leave both blank to reuse default.';
    errEl.classList.remove('hidden');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Sending code...';
  const { status, data } = await api('POST', '/api/accounts/start-auth', { phone, api_id, api_hash });
  btn.disabled = false;
  btn.textContent = 'Send OTP Code →';

  if (data.ok) {
    modalPhone = phone;
    document.getElementById('otp-phone-label').textContent = phone;
    showModalStep(2);
    document.getElementById('acc-otp').focus();
  } else {
    errEl.textContent = data.error || 'Failed to send code.';
    errEl.classList.remove('hidden');
  }
});

// Step 2 — Verify OTP
document.getElementById('verify-otp-btn').addEventListener('click', async () => {
  const code  = document.getElementById('acc-otp').value.replace(/\s/g, '');
  const errEl = document.getElementById('s2-error');
  const btn   = document.getElementById('verify-otp-btn');

  errEl.classList.add('hidden');
  if (!code) { errEl.textContent = 'Enter the OTP code.'; errEl.classList.remove('hidden'); return; }

  btn.disabled = true;
  btn.textContent = 'Verifying...';
  const { data } = await api('POST', '/api/accounts/verify-otp', { phone: modalPhone, code });
  btn.disabled = false;
  btn.textContent = 'Verify Code →';

  if (data.ok) {
    document.getElementById('success-msg').textContent = data.message;
    showModalStep('done');
  } else if (data.needs_2fa) {
    showModalStep(3);
    document.getElementById('acc-2fa').focus();
  } else {
    errEl.textContent = data.error || 'Verification failed.';
    errEl.classList.remove('hidden');
  }
});

// Step 3 — 2FA
document.getElementById('verify-2fa-btn').addEventListener('click', async () => {
  const password = document.getElementById('acc-2fa').value;
  const errEl    = document.getElementById('s3-error');
  const btn      = document.getElementById('verify-2fa-btn');

  errEl.classList.add('hidden');
  if (!password) { errEl.textContent = 'Enter your 2FA password.'; errEl.classList.remove('hidden'); return; }

  btn.disabled = true;
  btn.textContent = 'Verifying...';
  const { data } = await api('POST', '/api/accounts/verify-2fa', { phone: modalPhone, password });
  btn.disabled = false;
  btn.textContent = 'Complete Setup →';

  if (data.ok) {
    document.getElementById('success-msg').textContent = data.message;
    showModalStep('done');
  } else {
    errEl.textContent = data.error || '2FA verification failed.';
    errEl.classList.remove('hidden');
  }
});

// Allow Enter key in OTP fields
document.getElementById('acc-otp').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('verify-otp-btn').click();
});
document.getElementById('acc-2fa').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('verify-2fa-btn').click();
});

// ── Proxy ──────────────────────────────────────────────────
async function loadProxy() {
  const [defRes, accRes] = await Promise.all([
    api('GET', '/api/proxy/default'),
    api('GET', '/api/accounts'),
  ]);

  // Pre-fill form with current default
  const def = defRes.data.proxy;
  if (def) {
    document.getElementById('px-type').value = def.proxy_type || 'socks5';
    document.getElementById('px-host').value = def.proxy_host || '';
    document.getElementById('px-port').value = def.proxy_port || '';
    document.getElementById('px-user').value = def.proxy_user || '';
    document.getElementById('px-pass').value = '';
  }

  // Per-account list
  const list   = document.getElementById('proxy-accounts-list');
  const accs   = accRes.data.accounts || [];
  if (accs.length === 0) {
    list.innerHTML = '<div class="loading-cell">No accounts registered.</div>';
    return;
  }

  list.innerHTML = accs.map(acc => `
    <div class="proxy-item">
      <div class="proxy-item-left">
        <div class="proxy-item-phone">${esc(acc.phone)}</div>
        <div class="proxy-item-info">
          ${acc.proxy
            ? `<span class="badge badge-purple">🌐 ${esc(acc.proxy)}</span>`
            : '<span class="badge badge-gray">No proxy</span>'}
        </div>
      </div>
      <div class="proxy-item-actions">
        <button class="btn btn-danger btn-sm" onclick="removeProxyOne('${esc(acc.phone)}')">Remove</button>
      </div>
    </div>
  `).join('');
}

document.getElementById('proxy-all-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errEl = document.getElementById('proxy-form-error');
  errEl.classList.add('hidden');

  const body = {
    proxy_type: document.getElementById('px-type').value,
    proxy_host: document.getElementById('px-host').value.trim(),
    proxy_port: document.getElementById('px-port').value,
    proxy_user: document.getElementById('px-user').value.trim(),
    proxy_pass: document.getElementById('px-pass').value,
  };

  const { data } = await api('POST', '/api/proxy/set-all', body);
  if (data.ok) {
    showToast(data.message, 'success');
    loadProxy();
  } else {
    errEl.textContent = data.error;
    errEl.classList.remove('hidden');
  }
});

async function removeProxyOne(phone) {
  const { data } = await api('DELETE', `/api/proxy/${encodeURIComponent(phone)}`);
  if (data.ok) { showToast(`Proxy removed from ${phone}`, 'success'); loadProxy(); }
  else alert(data.error);
}

// ── Messages ───────────────────────────────────────────────
async function loadMessages() {
  const { data } = await api('GET', '/api/message');
  const editor   = document.getElementById('msg-editor');
  editor.value   = data.raw || '';
  updateTemplateCount(data.raw || '');
}

document.getElementById('msg-editor').addEventListener('input', (e) => {
  updateTemplateCount(e.target.value);
});

function updateTemplateCount(raw) {
  const count = raw.split('---').filter(t => t.trim()).length;
  document.getElementById('template-count').textContent = `${count} template${count !== 1 ? 's' : ''}`;
}

document.getElementById('save-msg-btn').addEventListener('click', async () => {
  const raw  = document.getElementById('msg-editor').value;
  const { data } = await api('POST', '/api/message', { raw });
  if (data.ok) showToast(`Saved ${data.count} template(s)`, 'success');
  else showToast(data.error || 'Save failed', 'error');
});

// ── Campaign ───────────────────────────────────────────────
async function loadCampaignStatus() {
  const { data } = await api('GET', '/api/campaign/status');
  updateCampaignUI(data);
}

function updateCampaignUI(status) {
  document.getElementById('cs-sent').textContent    = status.sent ?? 0;
  document.getElementById('cs-total').textContent   = status.total || '—';
  document.getElementById('cs-account').textContent = status.current_account || '—';

  const badge   = document.getElementById('campaign-badge');
  const badgeT  = document.getElementById('campaign-badge-text');
  const startBtn= document.getElementById('start-btn');
  const stopBtn = document.getElementById('stop-btn');
  const statEl  = document.getElementById('stat-status');
  const statSent= document.getElementById('stat-sent');

  if (status.running) {
    badge.className  = 'status-badge status-running';
    badgeT.textContent = 'Running';
    startBtn.disabled = true;
    stopBtn.disabled  = false;
    if (statEl) statEl.textContent = 'Running';
    if (statSent) statSent.textContent = status.sent ?? 0;
  } else {
    badge.className  = 'status-badge status-stopped';
    badgeT.textContent = 'Stopped';
    startBtn.disabled = false;
    stopBtn.disabled  = true;
    if (statEl) statEl.textContent = 'Idle';
  }
}

document.getElementById('campaign-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const mode = document.querySelector('input[name="camp-mode"]:checked')?.value ?? '1';
  const body = {
    sleep_time: parseInt(document.getElementById('camp-delay').value) || 60,
    max_dms:    parseInt(document.getElementById('camp-max-dms').value) || 2,
    mode:       parseInt(mode),
  };
  const { data } = await api('POST', '/api/campaign/start', body);
  if (data.ok) {
    showToast('Campaign started!', 'success');
    startSSE();
    loadCampaignStatus();
  } else {
    showToast(data.error || 'Failed to start', 'error');
  }
});

document.getElementById('stop-btn').addEventListener('click', async () => {
  const { data } = await api('POST', '/api/campaign/stop');
  if (data.ok) {
    showToast('Stop signal sent', 'success');
    stopSSE();
    loadCampaignStatus();
  }
});

document.getElementById('clear-logs-btn').addEventListener('click', () => {
  document.getElementById('log-viewer').innerHTML =
    '<span class="log-line log-dim">Logs cleared.</span>';
});

// ── SSE Log Streaming ──────────────────────────────────────
function startSSE() {
  stopSSE();
  sseSource = new EventSource('/api/campaign/logs', { withCredentials: true });
  sseSource.onmessage = (e) => {
    try {
      const payload = JSON.parse(e.data);
      if (payload.heartbeat) return;
      if (payload.msg) appendLog(payload.msg);
    } catch {}
  };
  sseSource.onerror = () => {
    // Auto-reconnects, just stop if campaign ended
    if (!campaign_status_running) stopSSE();
  };
}

let campaign_status_running = false;

function stopSSE() {
  if (sseSource) { sseSource.close(); sseSource = null; }
}

function appendLog(msg) {
  const viewer = document.getElementById('log-viewer');
  const line   = document.createElement('span');
  line.className = `log-line ${getLogClass(msg)}`;
  line.textContent = msg;
  viewer.appendChild(line);
  // Auto-scroll to bottom
  viewer.scrollTop = viewer.scrollHeight;
}

function getLogClass(msg) {
  if (msg.startsWith('═'))          return 'log-separator';
  if (msg.includes('[Error]'))       return 'log-error';
  if (msg.includes('[Send]'))        return 'log-success';
  if (msg.includes('[Rotation]') ||
      msg.includes('[Rotate]'))      return 'log-rotation';
  if (msg.includes('[Human Pause]') ||
      msg.includes('[Skip]'))        return 'log-warning';
  if (msg.includes('[Campaign]') ||
      msg.includes('[Proactive]'))   return 'log-info';
  if (msg.includes('[Wait]') ||
      msg.includes('[Jitter]'))      return 'log-dim';
  return 'log-default';
}

// ── Status polling ─────────────────────────────────────────
function startStatusPolling() {
  stopStatusPolling();
  statusPollInterval = setInterval(async () => {
    const { data } = await api('GET', '/api/campaign/status');
    campaign_status_running = data.running;
    updateCampaignUI(data);
    // Update overview stats live if visible
    if (currentSection === 'overview') {
      document.getElementById('stat-sent').textContent = data.sent ?? 0;
      document.getElementById('stat-status').textContent = data.running ? 'Running' : 'Idle';
    }
    // Auto-start SSE if campaign started from elsewhere
    if (data.running && !sseSource) startSSE();
    if (!data.running && sseSource)  stopSSE();
  }, 3000);
}

function stopStatusPolling() {
  if (statusPollInterval) { clearInterval(statusPollInterval); statusPollInterval = null; }
}

// ── Scraper ────────────────────────────────────────────────
async function loadScraper() {
  const select = document.getElementById('scrape-account-select');
  select.innerHTML = '<option value="">Choose an authorized account...</option>';
  document.getElementById('scrape-groups-container').classList.add('hidden');
  document.getElementById('scrape-status').classList.add('hidden');

  const { data } = await api('GET', '/api/accounts');
  const accounts = data.accounts || [];
  
  const authorized = accounts.filter(a => a.has_session);
  if (authorized.length === 0) {
    select.innerHTML = '<option value="">No authorized accounts available. Add/login an account first.</option>';
    return;
  }
  
  select.innerHTML += authorized.map(acc => 
    `<option value="${esc(acc.phone)}">${esc(acc.phone)}</option>`
  ).join('');
}

document.getElementById('load-groups-btn').addEventListener('click', async () => {
  const phone = document.getElementById('scrape-account-select').value;
  const btn = document.getElementById('load-groups-btn');
  const container = document.getElementById('scrape-groups-container');
  const groupSelect = document.getElementById('scrape-group-select');

  if (!phone) {
    showToast('Please select an account first.', 'error');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Loading groups from Telegram...';
  container.classList.add('hidden');

  const { data } = await api('GET', `/api/scraper/groups?phone=${encodeURIComponent(phone)}`);
  btn.disabled = false;
  btn.textContent = 'Load Groups from Account';

  if (data.error) {
    showToast(data.error, 'error');
    return;
  }

  const groups = data.groups || [];
  if (groups.length === 0) {
    showToast('No megagroups found for this account.', 'error');
    return;
  }

  groupSelect.innerHTML = '<option value="">Choose a group...</option>' + 
    groups.map(g => `<option value="${g.id}">${esc(g.title)}</option>`).join('');
  
  container.classList.remove('hidden');
});

document.getElementById('start-scrape-btn').addEventListener('click', async () => {
  const phone = document.getElementById('scrape-account-select').value;
  const group_id = document.getElementById('scrape-group-select').value;
  const btn = document.getElementById('start-scrape-btn');
  const statusDiv = document.getElementById('scrape-status');
  const statusText = document.getElementById('scrape-status-text');

  if (!phone || !group_id) {
    showToast('Please select both an account and a group.', 'error');
    return;
  }

  btn.disabled = true;
  statusText.textContent = 'Connecting and scraping participants...';
  statusDiv.classList.remove('hidden');

  const { data } = await api('POST', '/api/scraper/scrape', { phone, group_id });
  btn.disabled = false;
  statusDiv.classList.add('hidden');

  if (data.error) {
    showToast(data.error, 'error');
  } else {
    showToast(`Scraped ${data.count} members successfully and saved to members.csv!`, 'success');
    loadOverview();
  }
});

// ── Toast notifications ────────────────────────────────────
function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.style.cssText = `
    position: fixed; bottom: 24px; right: 24px; z-index: 9999;
    background: ${type === 'success' ? 'var(--success)' : type === 'error' ? 'var(--danger)' : 'var(--primary)'};
    color: #fff; padding: 12px 20px; border-radius: 10px;
    font-size: 13px; font-weight: 500; font-family: inherit;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    animation: fadeSlideUp 0.3s ease;
    max-width: 320px;
  `;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// ── Utility ────────────────────────────────────────────────
function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Boot ───────────────────────────────────────────────────
checkAuth();
