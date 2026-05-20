/* ══════════════════════════════════════════════════════
   StudyFlow v2  —  Frontend JavaScript
   Features: modal control · star selector · toggle topics
             count-up animation · progress bar entrance
             auto-dismiss flashes · focus trap
══════════════════════════════════════════════════════ */

'use strict';

/* ─── Modal helpers ──────────────────────────────────── */
function openModal(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.add('open');
  // Focus first interactive element inside
  const first = el.querySelector('input:not([type=hidden]),button,select');
  if (first) setTimeout(() => first.focus(), 60);
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('open');
}

function closeModalOutside(e, id) {
  if (e.target.id === id) closeModal(id);
}

// Escape key closes any open modal
document.addEventListener('keydown', e => {
  if (e.key === 'Escape')
    document.querySelectorAll('.modal-overlay.open')
            .forEach(m => m.classList.remove('open'));
});

/* ─── Star difficulty selector ────────────────────────── */
function setDifficulty(val) {
  document.querySelectorAll('.star-sel').forEach((s, i) => {
    s.classList.toggle('active', i < val);
    s.style.color = i < val ? 'var(--amber)' : '';
  });
  const inp = document.getElementById('difficultyInput');
  if (inp) inp.value = val;
}

// Hover preview
document.addEventListener('mouseover', e => {
  const star = e.target.closest('.star-sel');
  if (!star) return;
  const hoverVal = parseInt(star.dataset.val);
  document.querySelectorAll('.star-sel').forEach((s, i) => {
    s.style.color = i < hoverVal ? 'var(--amber)' : '';
  });
});

document.addEventListener('mouseleave', e => {
  if (!e.target.closest('.star-selector')) return;
  const cur = parseInt(document.getElementById('difficultyInput')?.value || 3);
  document.querySelectorAll('.star-sel').forEach((s, i) => {
    s.style.color = i < cur ? 'var(--amber)' : '';
  });
}, true);

/* ─── Toggle topic complete (AJAX) ───────────────────── */
function toggleTopic(topicId) {
  const btn    = document.getElementById(`toggle-btn-${topicId}`);
  const row    = document.getElementById(`topic-row-${topicId}`);
  const badge  = document.getElementById(`status-${topicId}`);
  const name   = document.getElementById(`topic-name-${topicId}`);
  if (!btn || !row) return;

  const completing = btn.textContent.trim() === 'Complete';

  // Optimistic flash
  row.style.transition = 'opacity .2s';
  row.style.opacity = '.4';

  fetch(`/topics/${topicId}/toggle`, { method: 'POST' })
    .then(r => {
      if (!r.ok) throw new Error('Network error');
      return r.json();
    })
    .then(() => {
      row.style.opacity = '1';
      if (completing) {
        btn.textContent = 'Undo';
        btn.className = 'btn btn-sm btn-undo';
        if (badge) { badge.textContent = '✓ Done'; badge.className = 'status-badge status-done'; }
        if (name)  name.classList.add('strikethrough');
        row.classList.add('row-done');
        showToast('✅ Topic marked as complete!', 'success');
      } else {
        btn.textContent = 'Complete';
        btn.className = 'btn btn-sm btn-toggle';
        if (badge) { badge.textContent = 'Pending'; badge.className = 'status-badge status-pending'; }
        if (name)  name.classList.remove('strikethrough');
        row.classList.remove('row-done');
        showToast('↩️ Topic moved back to pending', 'info');
      }
    })
    .catch(() => {
      row.style.opacity = '1';
      showToast('❌ Update failed. Please refresh.', 'error');
    });
}

/* ─── Toast notification ──────────────────────────────── */
function showToast(msg, type = 'info') {
  const container = document.querySelector('.flash-container')
    || (() => {
      const c = document.createElement('div');
      c.className = 'flash-container';
      document.querySelector('.main-content').prepend(c);
      return c;
    })();

  const el = document.createElement('div');
  el.className = `flash flash-${type === 'success' ? 'success' : type === 'error' ? 'error' : 'info'}`;
  el.innerHTML = `<span>${msg}</span><button class="flash-close" onclick="this.parentElement.remove()">✕</button>`;
  container.appendChild(el);

  setTimeout(() => {
    el.style.transition = 'opacity .4s, transform .4s';
    el.style.opacity = '0';
    el.style.transform = 'translateX(10px)';
    setTimeout(() => el.remove(), 420);
  }, 3000);
}

/* ─── Count-up animation for stat numbers ────────────── */
function animateCount(el) {
  const target = parseInt(el.dataset.count || el.textContent, 10);
  if (isNaN(target) || target === 0) return;
  let current = 0;
  const duration = 900; // ms
  const steps    = 30;
  const increment = Math.max(1, Math.round(target / steps));
  const interval  = duration / steps;

  const timer = setInterval(() => {
    current = Math.min(current + increment, target);
    el.textContent = current;
    if (current >= target) clearInterval(timer);
  }, interval);
}

/* ─── Progress bar entrance ───────────────────────────── */
function animateBars() {
  document.querySelectorAll('[data-width]').forEach(el => {
    const target = el.dataset.width + '%';
    el.style.width = '0%';
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        el.style.transition = 'width 1.5s cubic-bezier(.22,1,.36,1)';
        el.style.width = target;
      })
    );
  });
}

/* ─── DOMContentLoaded ────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {

  // Init star selector to saved value
  const diffInp = document.getElementById('difficultyInput');
  if (diffInp) setDifficulty(parseInt(diffInp.value) || 3);

  // Animate stat counters
  document.querySelectorAll('.stat-number[data-count]').forEach(animateCount);

  // Animate all progress bars
  animateBars();

  // Auto-dismiss flash messages after 4 s
  document.querySelectorAll('.flash').forEach(f => {
    setTimeout(() => {
      f.style.transition = 'opacity .45s, transform .45s';
      f.style.opacity    = '0';
      f.style.transform  = 'translateX(10px)';
      setTimeout(() => f.remove(), 460);
    }, 4000);
  });

});

/* ═══════════════════════════════════════════════════════
   OLLAMA AI FEATURES
   1. Floating Chat  2. Topic Tips  3. Schedule Insights
   4. Dashboard Advisor
═══════════════════════════════════════════════════════ */

/* ─── Markdown-lite renderer ──────────────────────────── */
function renderMarkdown(text) {
  // Bold
  text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Numbered list lines → li
  const lines = text.split('\n');
  let inList = false, html = '';
  lines.forEach(line => {
    const numMatch = line.match(/^\s*(\d+)\.\s+(.+)/);
    const bulletMatch = line.match(/^\s*[-•*]\s+(.+)/);
    if (numMatch || bulletMatch) {
      if (!inList) { html += '<ol style="padding-left:18px;margin:6px 0">'; inList = true; }
      html += `<li>${numMatch ? numMatch[2] : bulletMatch[1]}</li>`;
    } else {
      if (inList) { html += '</ol>'; inList = false; }
      if (line.trim()) html += `<p style="margin:4px 0">${line}</p>`;
    }
  });
  if (inList) html += '</ol>';
  return html || `<p>${text}</p>`;
}

/* ══════════════════════════════════════════════════════
   1. FLOATING AI CHAT
═══════════════════════════════════════════════════════ */

(function initFloatingChat() {
  // Inject FAB + panel into body
  const fab = document.createElement('button');
  fab.className = 'ai-fab';
  fab.title = 'StudyFlow AI Chat';
  fab.innerHTML = '🤖';

  const panel = document.createElement('div');
  panel.className = 'ai-chat-panel';
  panel.innerHTML = `
    <div class="ai-chat-header">
      <div class="ai-dot"></div>
      <div>
        <div>StudyFlow AI</div>
        <div class="ai-chat-header-sub">Powered by Groq · cloud AI</div>
      </div>
    </div>
    <div class="ai-chat-messages" id="aiChatMessages">
      <div class="ai-msg ai-msg-ai">👋 Hi! I'm your AI study assistant powered by Groq. Ask me anything — study tips, exam strategies, concept explanations, or motivation!</div>
    </div>
    <div class="ai-chat-input-row">
      <input type="text" class="ai-chat-input" id="aiChatInput" placeholder="Ask anything…" />
      <button class="ai-chat-send" id="aiChatSend">➤</button>
    </div>`;

  document.body.appendChild(fab);
  document.body.appendChild(panel);

  let chatOpen = false;
  let chatBusy = false;
  const chatHistory = [];  // {role, content} pairs for context

  fab.addEventListener('click', () => {
    chatOpen = !chatOpen;
    panel.classList.toggle('open', chatOpen);
    fab.classList.toggle('chat-open', chatOpen);
    fab.innerHTML = chatOpen ? '✕' : '🤖';
    if (chatOpen) document.getElementById('aiChatInput').focus();
  });

  async function sendChat() {
    if (chatBusy) return;
    const input = document.getElementById('aiChatInput');
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';

    const msgBox = document.getElementById('aiChatMessages');
    const sendBtn = document.getElementById('aiChatSend');

    // User message
    const userEl = document.createElement('div');
    userEl.className = 'ai-msg ai-msg-user';
    userEl.textContent = msg;
    msgBox.appendChild(userEl);

    // Streaming AI bubble
    const aiEl = document.createElement('div');
    aiEl.className = 'ai-msg ai-msg-ai';
    aiEl.innerHTML = '<span class="ai-thinking"><span></span><span></span><span></span></span>';
    msgBox.appendChild(aiEl);
    msgBox.scrollTop = msgBox.scrollHeight;

    chatBusy = true;
    sendBtn.disabled = true;

    try {
      const res = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ message: msg, history: chatHistory })
      });

      const data = await res.json();

      if (data.error) {
        aiEl.innerHTML = `❌ ${data.error}`;
      } else {
        aiEl.innerHTML = renderMarkdown(data.reply);
        // Store exchange in history
        chatHistory.push({ role: 'user', content: msg });
        chatHistory.push({ role: 'assistant', content: data.reply });
        if (chatHistory.length > 20) chatHistory.splice(0, 2);
      }
    } catch (e) {
      aiEl.innerHTML = '❌ Could not reach the server.';
    }

    msgBox.scrollTop = msgBox.scrollHeight;
    chatBusy = false;
    sendBtn.disabled = false;
    input.focus();
  }

  document.getElementById('aiChatSend').addEventListener('click', sendChat);
  document.addEventListener('keydown', e => {
    if (e.key === 'Enter' && chatOpen) sendChat();
  });
})();

/* ══════════════════════════════════════════════════════
   2. TOPIC AI TIPS
   Called from topics.html via data-topic-id buttons
═══════════════════════════════════════════════════════ */

async function loadTopicTips(topicId, btn) {
  const drawerId = `aiTipsDrawer-${topicId}`;
  let drawer = document.getElementById(drawerId);

  if (!drawer) {
    // Create drawer and inject after the button's parent row
    drawer = document.createElement('div');
    drawer.id = drawerId;
    drawer.className = 'ai-tips-drawer';
    drawer.innerHTML = `
      <div class="ai-tips-box">
        <div class="ai-tips-box-header">✨ AI Study Tips</div>
        <div class="ai-tips-loading">
          <div class="ai-thinking" style="display:inline-flex">
            <span></span><span></span><span></span>
          </div>
          Asking Groq AI for tips…
        </div>
      </div>`;
    btn.closest('td').appendChild(drawer);

    // Animate open
    requestAnimationFrame(() => requestAnimationFrame(() => drawer.classList.add('open')));

    try {
      const res = await fetch(`/api/ai/topic-tips/${topicId}`);
      const data = await res.json();
      const box = drawer.querySelector('.ai-tips-box');
      if (data.error) {
        box.innerHTML = `<div class="ai-tips-box-header">⚠️ Error</div>
          <p style="font-size:13px;color:var(--rose)">${data.error}</p>`;
      } else {
        box.innerHTML = `<div class="ai-tips-box-header">✨ AI Tips for <em>${data.topic}</em></div>
          ${renderMarkdown(data.tips)}`;
      }
    } catch (e) {
      drawer.querySelector('.ai-tips-box').innerHTML = '<p style="color:var(--rose)">❌ Network error</p>';
    }
    btn.textContent = '✕ Close';
  } else {
    // Toggle existing drawer
    const isOpen = drawer.classList.toggle('open');
    btn.textContent = isOpen ? '✕ Close' : '✨ AI Tips';
  }
}

/* ══════════════════════════════════════════════════════
   3. SCHEDULE AI INSIGHTS
   Auto-injects if #ai-insights-mount exists
═══════════════════════════════════════════════════════ */

async function loadScheduleInsights(btn) {
  const mount = document.getElementById('ai-insights-mount');
  if (!mount) return;
  if (btn) btn.disabled = true;

  mount.innerHTML = `
    <div class="ai-insights-card anim">
      <div class="ai-insights-header">
        <div class="ai-insights-title">🧠 AI Schedule Analysis</div>
        <span style="font-size:12px;color:var(--t3)">Analysing…</span>
      </div>
      <div class="ai-loading-row" style="display:flex;gap:6px;align-items:center;color:var(--t2);font-size:13px">
        <div class="ai-thinking" style="display:inline-flex"><span></span><span></span><span></span></div>
        Asking Groq AI to review your schedule…
      </div>
    </div>`;

  try {
    const res = await fetch('/api/ai/schedule-insights');
    const data = await res.json();
    if (data.error) {
      mount.innerHTML = `
        <div class="ai-insights-card">
          <div class="ai-insights-header">
            <div class="ai-insights-title">🧠 AI Schedule Analysis</div>
            <button class="btn-ai-refresh" onclick="loadScheduleInsights(this)">↻ Retry</button>
          </div>
          <div style="color:var(--rose);font-size:13px">${data.error}</div>
        </div>`;
    } else {
      mount.innerHTML = `
        <div class="ai-insights-card anim">
          <div class="ai-insights-header">
            <div class="ai-insights-title">🧠 AI Schedule Analysis</div>
            <button class="btn-ai-refresh" onclick="loadScheduleInsights(this)">↻ Refresh</button>
          </div>
          <div class="ai-insights-body">${renderMarkdown(data.insights)}</div>
        </div>`;
    }
  } catch (e) {
    mount.innerHTML = `<div class="ai-insights-card"><p style="color:var(--rose)">❌ Network error</p></div>`;
  }
}

/* ══════════════════════════════════════════════════════
   4. DASHBOARD AI ADVISOR
   Auto-injects if #ai-advisor-mount exists
═══════════════════════════════════════════════════════ */

async function loadDashboardAdvice(btn) {
  const mount = document.getElementById('ai-advisor-mount');
  if (!mount) return;
  if (btn) btn.disabled = true;

  mount.innerHTML = `
    <div class="ai-advisor-card">
      <div class="ai-advisor-header">
        <div class="ai-advisor-title">🎯 Today's AI Focus Plan</div>
        <div class="ai-advisor-badge">Groq Cloud AI</div>
      </div>
      <div class="ai-advisor-loading">
        <div class="ai-advisor-dots"><span></span><span></span><span></span></div>
        Building your personalised plan…
      </div>
    </div>`;

  try {
    const res = await fetch('/api/ai/dashboard-advice');
    const data = await res.json();
    if (data.error) {
      mount.innerHTML = `
        <div class="ai-advisor-card">
          <div class="ai-advisor-header">
            <div class="ai-advisor-title">🎯 Today's AI Focus Plan</div>
            <button class="btn-ai-refresh-white" onclick="loadDashboardAdvice(this)">↻ Retry</button>
          </div>
          <div style="opacity:.8;font-size:13.5px">${data.error}</div>
        </div>`;
    } else {
      mount.innerHTML = `
        <div class="ai-advisor-card anim">
          <div class="ai-advisor-header">
            <div class="ai-advisor-title">🎯 Today's AI Focus Plan</div>
            <div style="display:flex;align-items:center;gap:10px">
              <div class="ai-advisor-badge">Groq Cloud AI</div>
              <button class="btn-ai-refresh-white" onclick="loadDashboardAdvice(this)">↻ Refresh</button>
            </div>
          </div>
          <div class="ai-advisor-body">${renderMarkdown(data.advice)}</div>
        </div>`;
    }
  } catch (e) {
    mount.innerHTML = `<div class="ai-advisor-card"><p style="opacity:.8">❌ Network error</p></div>`;
  }
}

/* ── Auto-boot on page load ────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('ai-advisor-mount')) loadDashboardAdvice();
  if (document.getElementById('ai-insights-mount')) loadScheduleInsights();
});

/* ═══════════════════════════════════════════════════════
   PHASE 1 FEATURES
   Step 1: Deadline Countdown
   Step 2: Dark Mode
   Step 3: Search & Filter
═══════════════════════════════════════════════════════ */

/* ──────────────────────────────────────────────────────
   STEP 1 — DEADLINE COUNTDOWN
   Finds all [data-deadline] elements and injects chips
────────────────────────────────────────────────────── */
function renderCountdowns() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  document.querySelectorAll('.deadline-countdown[data-deadline]').forEach(el => {
    const raw = el.dataset.deadline; // "YYYY-MM-DD"
    if (!raw) return;

    const [y, m, d] = raw.split('-').map(Number);
    const target = new Date(y, m - 1, d);
    target.setHours(0, 0, 0, 0);

    const diffMs   = target - today;
    const diffDays = Math.round(diffMs / 86400000);

    let label, cls;
    if (diffDays < 0) {
      label = `${Math.abs(diffDays)}d overdue`;
      cls   = 'countdown-overdue';
    } else if (diffDays === 0) {
      label = '📅 Due today!';
      cls   = 'countdown-today';
    } else if (diffDays <= 3) {
      label = `🔴 ${diffDays}d left`;
      cls   = 'countdown-urgent';
    } else if (diffDays <= 7) {
      label = `🟡 ${diffDays}d left`;
      cls   = 'countdown-warning';
    } else {
      label = `🟢 ${diffDays}d left`;
      cls   = 'countdown-ok';
    }

    el.textContent  = label;
    el.className    = `deadline-countdown ${cls}`;
  });
}

/* ──────────────────────────────────────────────────────
   STEP 2 — DARK MODE TOGGLE
────────────────────────────────────────────────────── */
function initDarkMode() {
  const toggle = document.getElementById('darkModeToggle');
  if (!toggle) return;

  const label  = toggle.querySelector('.dm-label');
  const sunIcon = toggle.querySelector('.dm-icon-sun');

  function applyTheme(dark) {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    localStorage.setItem('sfDarkMode', dark ? '1' : '0');
    if (label)   label.textContent = dark ? 'Dark Mode' : 'Light Mode';
    if (sunIcon) sunIcon.textContent = dark ? '🌙' : '☀️';
  }

  // Read saved pref (already applied in <head>, just sync the label)
  const saved = localStorage.getItem('sfDarkMode') === '1';
  applyTheme(saved);

  toggle.addEventListener('click', () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    applyTheme(!isDark);
  });
}

/* ──────────────────────────────────────────────────────
   STEP 3a — TOPIC SEARCH & FILTER
────────────────────────────────────────────────────── */
let _topicFilter = 'all';

function filterTopics() {
  const query    = (document.getElementById('topicSearch')?.value || '').toLowerCase().trim();
  const clearBtn = document.getElementById('topicSearchClear');
  if (clearBtn) clearBtn.style.display = query ? 'block' : 'none';

  const rows   = document.querySelectorAll('tr.topic-row');
  let visible  = 0;

  rows.forEach(row => {
    const name     = (row.dataset.name || '');
    const status   = (row.dataset.status || '');
    const deadline = (row.dataset.deadline || '');
    const todayStr = (row.dataset.today || '');

    // Filter match
    const matchFilter = _topicFilter === 'all'
      || (_topicFilter === 'pending' && status === 'pending')
      || (_topicFilter === 'done'    && status === 'done')
      || (_topicFilter === 'overdue' && status === 'pending' && deadline < todayStr);

    // Search match
    const matchSearch = !query || name.includes(query);

    const show = matchFilter && matchSearch;
    row.style.display = show ? '' : 'none';
    if (show) visible++;

    // Also hide the AI tips drawer when row is hidden
    const drawerId = row.id?.replace('topic-row-', '');
    if (drawerId) {
      const drawer = document.getElementById(`aiTipsDrawer-${drawerId}`);
      if (drawer) drawer.style.display = show ? '' : 'none';
    }
  });

  // Update count
  const countEl = document.getElementById('topicCount');
  if (countEl) countEl.textContent = `${visible} of ${rows.length} topic${rows.length !== 1 ? 's' : ''}`;

  // No results row
  const tbody  = document.querySelector('.topics-table tbody');
  const noResId = 'topics-no-results';
  let noRes    = document.getElementById(noResId);
  if (visible === 0 && tbody) {
    if (!noRes) {
      noRes = document.createElement('tr');
      noRes.id = noResId;
      const cols = document.querySelector('.topics-table thead tr')?.children?.length || 7;
      noRes.innerHTML = `<td colspan="${cols}" class="sf-no-results">🔍 No topics match your search or filter.</td>`;
      tbody.appendChild(noRes);
    }
    noRes.style.display = '';
  } else if (noRes) {
    noRes.style.display = 'none';
  }
}

function setTopicFilter(filter, btn) {
  _topicFilter = filter;
  document.querySelectorAll('.sf-filter-btn[data-filter]').forEach(b => {
    b.classList.toggle('active', b === btn);
  });
  filterTopics();
}

function clearTopicSearch() {
  const inp = document.getElementById('topicSearch');
  if (inp) { inp.value = ''; inp.focus(); }
  filterTopics();
}

/* ──────────────────────────────────────────────────────
   STEP 3b — SCHEDULE SEARCH & FILTER
────────────────────────────────────────────────────── */
let _schedFilter = 'all';

function filterSchedule() {
  const query    = (document.getElementById('schedSearch')?.value || '').toLowerCase().trim();
  const clearBtn = document.getElementById('schedSearchClear');
  if (clearBtn) clearBtn.style.display = query ? 'block' : 'none';

  const rows   = document.querySelectorAll('tr.sched-row');
  let visible  = 0;

  rows.forEach(row => {
    const topic   = (row.dataset.topic   || '');
    const subject = (row.dataset.subject || '');
    const type    = (row.dataset.type    || '');
    const date    = (row.dataset.date    || '');
    const todayStr= (row.dataset.today   || '');

    const matchFilter = _schedFilter === 'all'
      || (_schedFilter === 'today'    && date === todayStr)
      || (_schedFilter === 'study'    && type === 'study')
      || (_schedFilter === 'revision' && type === 'revision')
      || (_schedFilter === 'upcoming' && date >= todayStr);

    const matchSearch = !query || topic.includes(query) || subject.includes(query);

    const show = matchFilter && matchSearch;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  const countEl = document.getElementById('schedCount');
  if (countEl) countEl.textContent = `${visible} of ${rows.length} session${rows.length !== 1 ? 's' : ''}`;

  const tbody  = document.querySelector('.schedule-table tbody');
  const noResId = 'sched-no-results';
  let noRes    = document.getElementById(noResId);
  if (visible === 0 && tbody) {
    if (!noRes) {
      noRes = document.createElement('tr');
      noRes.id = noResId;
      noRes.innerHTML = `<td colspan="7" class="sf-no-results">🔍 No sessions match your search or filter.</td>`;
      tbody.appendChild(noRes);
    }
    noRes.style.display = '';
  } else if (noRes) {
    noRes.style.display = 'none';
  }
}

function setSchedFilter(filter, btn) {
  _schedFilter = filter;
  document.querySelectorAll('#schedSearch').forEach(() => {}); // noop, just a hook
  document.querySelectorAll('.sf-filter-btn[data-filter]').forEach(b => {
    b.classList.toggle('active', b === btn);
  });
  filterSchedule();
}

function clearSchedSearch() {
  const inp = document.getElementById('schedSearch');
  if (inp) { inp.value = ''; inp.focus(); }
  filterSchedule();
}

/* ── Wire everything up on DOMContentLoaded ────────────── */
// Extend existing DOMContentLoaded — safe to add another listener
document.addEventListener('DOMContentLoaded', () => {
  renderCountdowns();

  // Init search counts on pages that have search toolbars
  if (document.getElementById('topicCount'))  filterTopics();
  if (document.getElementById('schedCount'))  filterSchedule();
});

/* ═══════════════════════════════════════════════════════
   PHASE 2 FEATURES
   Step 4+5: Notes & Resource Links
   Step 6:   Pomodoro Timer
   Step 7:   Export Schedule to PDF
═══════════════════════════════════════════════════════ */

/* ──────────────────────────────────────────────────────
   STEP 4+5 — NOTES & RESOURCE LINKS MODAL
────────────────────────────────────────────────────── */
let _notesTopicId = null;

async function openNotesModal(topicId, topicName) {
  _notesTopicId = topicId;
  document.getElementById('notesModalTitle').textContent = topicName;
  document.getElementById('notesTextarea').value = '';
  document.getElementById('linksList').innerHTML = '';
  openModal('notesModal');

  try {
    const res = await fetch(`/topics/${topicId}/notes`);
    const data = await res.json();
    document.getElementById('notesTextarea').value = data.notes || '';
    const links = Array.isArray(data.links) ? data.links : [];
    if (links.length === 0) {
      addLinkRow('');
    } else {
      links.forEach(url => addLinkRow(url));
    }
  } catch (e) {
    addLinkRow('');
  }
}

function addLinkRow(value = '') {
  const list = document.getElementById('linksList');
  const row = document.createElement('div');
  row.className = 'link-row';
  row.innerHTML = `
    <input type="url" placeholder="https://youtube.com/watch?v=…  or any URL"
           value="${escapeHtml(value)}" />
    <button class="link-row-del" onclick="this.closest('.link-row').remove()" title="Remove">✕</button>`;
  list.appendChild(row);
  row.querySelector('input').focus();
}

function escapeHtml(str) {
  return (str || '').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
}

async function saveNotes() {
  if (!_notesTopicId) return;
  const btn = document.getElementById('notesSaveBtn');
  btn.disabled = true;
  btn.textContent = 'Saving…';

  const notes = document.getElementById('notesTextarea').value.trim();
  const links = Array.from(document.querySelectorAll('#linksList .link-row input'))
                     .map(i => i.value.trim())
                     .filter(Boolean);

  try {
    const res = await fetch(`/topics/${_notesTopicId}/notes`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ notes, links })
    });
    const data = await res.json();
    if (data.status === 'saved') {
      // Update preview cell
      updateNotesPreviewCell(_notesTopicId, notes, links);
      closeModal('notesModal');
    }
  } catch (e) {
    alert('Save failed — check the server is running.');
  } finally {
    btn.disabled = false;
    btn.textContent = '💾 Save';
  }
}

function updateNotesPreviewCell(topicId, notes, links) {
  const cell = document.getElementById(`notes-cell-${topicId}`);
  if (!cell) return;
  let html = '';
  if (notes) {
    const snippet = notes.length > 60 ? notes.slice(0, 60) + '…' : notes;
    html += `<span class="notes-snippet">${escapeHtml(snippet)}</span>`;
  }
  if (links.length > 0) {
    html += `<span class="links-badge" title="${links.length} link(s)">🔗 ${links.length}</span>`;
  }
  if (!notes && links.length === 0) {
    html = '<span class="notes-empty">—</span>';
  }
  cell.innerHTML = html;
}

/* ──────────────────────────────────────────────────────
   STEP 6 — POMODORO TIMER
────────────────────────────────────────────────────── */
const POMO_CIRCUMFERENCE = 2 * Math.PI * 52; // r=52 → 326.7

let _pomoTimer     = null;
let _pomoRunning   = false;
let _pomoTotal     = 25 * 60;
let _pomoRemaining = 25 * 60;
let _pomoMode      = 'Focus';
let _pomoSessions  = 0;

function pomoSetMode(mins, label, btn) {
  if (_pomoRunning) pomoStop();
  document.querySelectorAll('.pomo-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _pomoMode      = label;
  _pomoTotal     = mins * 60;
  _pomoRemaining = mins * 60;
  pomoUpdateDisplay();
  pomoUpdateRing(1);

  // Ring colour by mode
  const ring = document.getElementById('pomoRingFill');
  if (ring) {
    ring.style.stroke = label === 'Focus' ? 'var(--p1)'
                      : label === 'Short Break' ? '#10b981'
                      : '#f59e0b';
  }
  document.getElementById('pomoModeLabel').textContent = label;
}

function pomoUpdateDisplay() {
  const m = String(Math.floor(_pomoRemaining / 60)).padStart(2, '0');
  const s = String(_pomoRemaining % 60).padStart(2, '0');
  const el = document.getElementById('pomoDisplay');
  if (el) el.textContent = `${m}:${s}`;
  document.title = _pomoRunning ? `🍅 ${m}:${s} — StudyFlow` : 'StudyFlow';
}

function pomoUpdateRing(fraction) {
  const ring = document.getElementById('pomoRingFill');
  if (!ring) return;
  const offset = POMO_CIRCUMFERENCE * (1 - fraction);
  ring.style.strokeDashoffset = offset;
}

function pomoToggle() {
  _pomoRunning ? pomoStop() : pomoStart();
}

function pomoStart() {
  if (_pomoRemaining <= 0) pomoReset();
  _pomoRunning = true;
  const btn = document.getElementById('pomoStartBtn');
  if (btn) { btn.textContent = '⏸ Pause'; btn.classList.add('running'); }

  _pomoTimer = setInterval(() => {
    _pomoRemaining--;
    pomoUpdateDisplay();
    pomoUpdateRing(_pomoRemaining / _pomoTotal);

    if (_pomoRemaining <= 0) {
      clearInterval(_pomoTimer);
      _pomoRunning = false;
      pomoComplete();
    }
  }, 1000);
}

function pomoStop() {
  clearInterval(_pomoTimer);
  _pomoRunning = false;
  const btn = document.getElementById('pomoStartBtn');
  if (btn) { btn.textContent = '▶ Start'; btn.classList.remove('running'); }
  document.title = 'StudyFlow';
}

function pomoReset() {
  pomoStop();
  _pomoRemaining = _pomoTotal;
  pomoUpdateDisplay();
  pomoUpdateRing(1);
}

function pomodoroStop() { pomoStop(); } // alias for modal close button

function pomoComplete() {
  document.title = 'StudyFlow';
  const btn = document.getElementById('pomoStartBtn');
  if (btn) { btn.textContent = '▶ Start'; btn.classList.remove('running'); }

  // Play a gentle beep
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 200, 400].forEach(delay => {
      setTimeout(() => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 880;
        gain.gain.setValueAtTime(.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(.001, ctx.currentTime + .4);
        osc.start();
        osc.stop(ctx.currentTime + .4);
      }, delay);
    });
  } catch (e) {}

  if (_pomoMode === 'Focus') _pomoSessions++;
  const topic = document.getElementById('pomoTopicSelect')?.value || '—';
  logPomoSession(_pomoMode, topic);

  // Suggest next mode
  setTimeout(() => {
    if (_pomoMode === 'Focus') {
      const nextLabel = _pomoSessions % 4 === 0 ? 'Long Break 15m' : 'Short Break 5m';
      const msg = `✅ Focus session done! ${_pomoSessions} session(s) today. Take a ${nextLabel}?`;
      if (confirm(msg)) {
        const mins = _pomoSessions % 4 === 0 ? 15 : 5;
        const lbl  = _pomoSessions % 4 === 0 ? 'Long Break' : 'Short Break';
        const tab  = Array.from(document.querySelectorAll('.pomo-tab'))
                       .find(b => parseInt(b.dataset.mins) === mins);
        if (tab) pomoSetMode(mins, lbl, tab);
        pomoStart();
      }
    } else {
      if (confirm('Break over! Start another focus session?')) {
        const focusTab = document.querySelector('.pomo-tab[data-mins="25"]');
        if (focusTab) pomoSetMode(25, 'Focus', focusTab);
        pomoStart();
      }
    }
  }, 300);
}

function logPomoSession(mode, topic) {
  const log = document.getElementById('pomoLog');
  if (!log) return;
  const now = new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
  const entry = document.createElement('div');
  entry.className = 'pomo-log-entry';
  entry.textContent = `${now} · ${mode} complete${topic && topic !== '—' ? ` · ${topic}` : ''}`;
  log.prepend(entry);
}

/* ──────────────────────────────────────────────────────
   STEP 7 — EXPORT SCHEDULE TO PDF
────────────────────────────────────────────────────── */
function exportSchedulePDF() {
  if (typeof window.jspdf === 'undefined') {
    alert('PDF library not loaded yet — please wait a moment and try again.');
    return;
  }

  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });

  // Title + date
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(18);
  doc.setTextColor(99, 102, 241);
  doc.text('StudyFlow — Study Schedule', 14, 16);

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(120, 120, 140);
  doc.text(`Generated: ${new Date().toLocaleDateString('en-IN', {day:'numeric',month:'long',year:'numeric'})}`, 14, 23);

  // Collect visible rows from table
  const rows = [];
  document.querySelectorAll('tr.sched-row').forEach(tr => {
    if (tr.style.display === 'none') return;
    const cells = tr.querySelectorAll('td');
    if (cells.length < 7) return;

    // Date (first cell may span multiple rows — get its text)
    const dateTd = tr.querySelector('.date-cell') || cells[0];
    const dateText = (dateTd.textContent || '').replace(/\s+/g, ' ').trim().split(' ').slice(0,3).join(' ');
    const subject  = (cells[1]?.textContent || '').trim();
    const topic    = (cells[2]?.textContent || '').trim().replace(/\s+/g,' ');
    const hours    = (cells[3]?.textContent || '').trim();
    const type     = (cells[4]?.textContent || '').trim().replace(/\s+/g,' ');
    const deadline = (cells[5]?.textContent || '').trim().split('\n')[0].trim();
    const diff     = (cells[6]?.textContent || '').trim();

    rows.push([dateText || '—', subject, topic, hours, type, deadline, diff]);
  });

  doc.autoTable({
    startY: 28,
    head: [['Date', 'Subject', 'Topic', 'Hours', 'Type', 'Deadline', 'Difficulty']],
    body: rows,
    styles: { fontSize: 9, cellPadding: 3, overflow: 'linebreak' },
    headStyles: {
      fillColor: [99, 102, 241],
      textColor: 255,
      fontStyle: 'bold',
      fontSize: 9,
    },
    alternateRowStyles: { fillColor: [248, 248, 255] },
    columnStyles: {
      0: { cellWidth: 28 },
      1: { cellWidth: 38 },
      2: { cellWidth: 60 },
      3: { cellWidth: 18, halign: 'center' },
      4: { cellWidth: 24, halign: 'center' },
      5: { cellWidth: 28, halign: 'center' },
      6: { cellWidth: 22, halign: 'center' },
    },
    didDrawPage: (data) => {
      // Footer
      doc.setFontSize(8);
      doc.setTextColor(160, 160, 180);
      doc.text('StudyFlow — Smart Study Planner', 14, doc.internal.pageSize.height - 6);
      doc.text(
        `Page ${data.pageNumber}`,
        doc.internal.pageSize.width - 20,
        doc.internal.pageSize.height - 6
      );
    }
  });

  const filename = `study_schedule_${new Date().toISOString().slice(0,10)}.pdf`;
  doc.save(filename);
}

/* ═══════════════════════════════════════════════════════
   PHASE 6 — AI UPGRADES
   Step 16: Difficulty Auto-Rating
   Step 17: Readiness Score (loaded in subjects.html)
   Step 18: Quiz Modal
   Step 19: Chat with Memory
   Step 20: Voice Input
═══════════════════════════════════════════════════════ */

/* ──────────────────────────────────────────────────────
   STEP 19 — UPGRADE FLOATING CHAT WITH MEMORY
   Replaces the sendChat() function defined earlier.
   We store message history in a JS array and send it
   with every request for conversation context.
────────────────────────────────────────────────────── */

// Override the original sendChat with a memory-aware version
// _chatHistory persists for the session (cleared on page refresh)
window._chatHistory = [];

async function sendChat() {
  if (window._chatBusy) return;
  const input  = document.getElementById('aiChatInput');
  const msg    = input.value.trim();
  if (!msg) return;
  input.value = '';

  const msgBox  = document.getElementById('aiChatMessages');
  const sendBtn = document.getElementById('aiChatSend');

  // User bubble
  const userEl = document.createElement('div');
  userEl.className = 'ai-msg ai-msg-user';
  userEl.textContent = msg;
  msgBox.appendChild(userEl);

  // Thinking dots
  const thinkEl = document.createElement('div');
  thinkEl.className = 'ai-thinking';
  thinkEl.innerHTML = '<span></span><span></span><span></span>';
  msgBox.appendChild(thinkEl);
  msgBox.scrollTop = msgBox.scrollHeight;

  window._chatBusy = true;
  sendBtn.disabled = true;

  try {
    const res  = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: msg,
        history: window._chatHistory   // Step 19: send history
      })
    });
    const data = await res.json();
    thinkEl.remove();

    const aiEl = document.createElement('div');
    aiEl.className = 'ai-msg ai-msg-ai';

    if (data.error) {
      aiEl.innerHTML = false
        ? data.error
        : `❌ ${data.error}`;
    } else {
      aiEl.innerHTML = renderMarkdown(data.reply);
      // Store exchange in history (last 10 pairs = 20 messages)
      window._chatHistory.push({ role: 'user',      content: msg });
      window._chatHistory.push({ role: 'assistant', content: data.reply });
      if (window._chatHistory.length > 20) {
        window._chatHistory = window._chatHistory.slice(-20);
      }
    }
    msgBox.appendChild(aiEl);
  } catch (e) {
    thinkEl.remove();
    const errEl = document.createElement('div');
    errEl.className = 'ai-msg ai-msg-ai';
    errEl.textContent = '❌ Could not reach the server.';
    msgBox.appendChild(errEl);
  }

  msgBox.scrollTop = msgBox.scrollHeight;
  window._chatBusy = false;
  sendBtn.disabled = false;
  input.focus();
}

/* ──────────────────────────────────────────────────────
   STEP 16 — AI DIFFICULTY AUTO-RATING
────────────────────────────────────────────────────── */

let _diffSuggestTimer = null;

async function aiSuggestDifficulty(topicName) {
  topicName = (topicName || '').trim();
  if (topicName.length < 3) return;     // don't fire for tiny input

  // Debounce — wait 300ms after last blur
  clearTimeout(_diffSuggestTimer);
  _diffSuggestTimer = setTimeout(async () => {
    const badge  = document.getElementById('aiDiffBadge');
    const reason = document.getElementById('aiDiffReason');
    if (!badge) return;

    badge.textContent = '✨ AI rating…';
    badge.style.display = 'inline-flex';
    reason.style.display = 'none';

    try {
      const res  = await fetch('/api/ai/suggest-difficulty', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_name: topicName })
      });
      const data = await res.json();
      if (data.error || !data.difficulty) {
        badge.style.display = 'none';
        return;
      }

      const diff  = data.difficulty;
      const stars = '★'.repeat(diff) + '☆'.repeat(5 - diff);
      badge.innerHTML = `✨ AI suggests: <strong>${stars}</strong>
        <button type="button" class="ai-diff-accept"
                onclick="acceptAiDifficulty(${diff})">Accept</button>`;
      badge.style.display = 'inline-flex';

      if (data.reason) {
        reason.textContent = `🤖 ${data.reason}`;
        reason.style.display = 'block';
      }
    } catch (e) {
      badge.style.display = 'none';
    }
  }, 300);
}

function acceptAiDifficulty(diff) {
  setDifficulty(diff);
  const badge  = document.getElementById('aiDiffBadge');
  if (badge) {
    badge.innerHTML = `✅ Difficulty set to ${'★'.repeat(diff)}`;
    setTimeout(() => { badge.style.display = 'none'; }, 2000);
  }
}

/* ──────────────────────────────────────────────────────
   STEP 18 — AI QUIZ MODAL
   Triggered after topic is marked complete.
   Wrong answers auto-schedule an extra revision.
────────────────────────────────────────────────────── */

let _quizTopicId   = null;
let _quizQuestions = [];
let _quizAnswers   = {};

// Patch toggleTopic to show quiz on completion
const _originalToggleTopic = window.toggleTopic;
window.toggleTopic = async function(topicId) {
  // Call original toggle
  const res = await fetch(`/topics/${topicId}/toggle`, { method: 'POST' });
  const data = await res.json();

  // Update UI (existing logic from original toggleTopic)
  const btn     = document.getElementById(`toggle-btn-${topicId}`);
  const nameEl  = document.getElementById(`topic-name-${topicId}`);
  const row     = document.getElementById(`topic-row-${topicId}`);
  if (btn) {
    const nowDone = btn.textContent.trim() === 'Complete';
    btn.textContent = nowDone ? 'Undo' : 'Complete';
    btn.className   = `btn btn-sm ${nowDone ? 'btn-undo' : 'btn-toggle'}`;
    if (nameEl) nameEl.classList.toggle('strikethrough', nowDone);
    if (row)    row.classList.toggle('row-done', nowDone);

    // If just completed → launch quiz
    if (nowDone && data.review_scheduled) {
      const earned = Number(data.flowcoins || 0);
      const streakEarned = Number(data.streak_bonus?.earned || 0);
      if (earned || streakEarned) {
        const total = earned + streakEarned;
        const streakText = streakEarned ? ` including ${streakEarned} streak bonus` : '';
        showToast(`+${total} FlowCoins earned${streakText}!`, 'success');
        document.querySelectorAll('.flowcoin-badge').forEach(badge => {
          if (data.balance !== undefined) badge.textContent = data.balance;
        });
      }
      setTimeout(() => launchQuiz(topicId), 400);
    }
  }
};

async function launchQuiz(topicId) {
  _quizTopicId = topicId;
  _quizAnswers = {};
  _quizQuestions = [];

  const body   = document.getElementById('quizBody');
  const footer = document.getElementById('quizFooter');
  body.innerHTML = `
    <div style="text-align:center;padding:30px 0">
      <div class="ai-thinking" style="display:inline-flex;margin-bottom:12px">
        <span></span><span></span><span></span>
      </div>
      <p style="color:var(--t2);font-size:14px">Generating 5 quiz questions with Groq AI…</p>
    </div>`;
  footer.style.display = 'none';
  openModal('quizModal');

  try {
    const res  = await fetch(`/api/ai/quiz/${topicId}`);
    const data = await res.json();

    if (data.error || !data.questions?.length) {
      body.innerHTML = `<p style="color:var(--t2);padding:20px">
        Quiz unavailable — check your Groq API key. You can try AI Tips instead.</p>`;
      return;
    }

    _quizQuestions = data.questions;
    document.getElementById('quizTopicName').textContent = data.topic;
    renderQuiz(data.questions);
    footer.style.display = 'flex';
  } catch (e) {
    body.innerHTML = `<p style="color:var(--rose);padding:20px">❌ Could not load quiz.</p>`;
  }
}

function renderQuiz(questions) {
  const body = document.getElementById('quizBody');
  body.innerHTML = questions.map((q, qi) => `
    <div class="quiz-question" id="qq-${qi}">
      <div class="quiz-q-text">
        <span class="quiz-q-num">Q${qi+1}</span> ${escapeHtml(q.q)}
      </div>
      <div class="quiz-options">
        ${Object.entries(q.options).map(([k, v]) => `
          <label class="quiz-option-label" id="qopt-${qi}-${k}">
            <input type="radio" name="q${qi}" value="${k}"
                   onchange="_quizAnswers[${qi}]='${k}'"/>
            <span class="quiz-option-key">${k}</span>
            <span class="quiz-option-text">${escapeHtml(v)}</span>
          </label>
        `).join('')}
      </div>
    </div>
  `).join('');
}

async function quizSubmit() {
  const submitBtn = document.getElementById('quizSubmitBtn');
  submitBtn.disabled = true;

  let correct = 0;
  const wrong = [];

  _quizQuestions.forEach((q, qi) => {
    const chosen = _quizAnswers[qi];
    const isRight = chosen === q.answer;
    if (isRight) {
      correct++;
    } else {
      wrong.push(qi);
    }
    // Colour the options
    Object.keys(q.options).forEach(k => {
      const el = document.getElementById(`qopt-${qi}-${k}`);
      if (!el) return;
      if (k === q.answer) el.classList.add('quiz-correct');
      else if (k === chosen) el.classList.add('quiz-wrong');
      el.querySelector('input').disabled = true;
    });
  });

  const total  = _quizQuestions.length;
  const pct    = Math.round(correct / total * 100);
  const emoji  = pct >= 80 ? '🎉' : pct >= 60 ? '👍' : '📚';

  // Show result banner
  const body = document.getElementById('quizBody');
  const resultBanner = document.createElement('div');
  resultBanner.className = `quiz-result ${pct >= 80 ? 'quiz-result-good' : pct >= 60 ? 'quiz-result-ok' : 'quiz-result-bad'}`;
  resultBanner.innerHTML = `
    <span class="quiz-result-emoji">${emoji}</span>
    <strong>${correct}/${total} correct (${pct}%)</strong>
    ${wrong.length > 0
      ? `<span style="font-size:12px;opacity:.8"> — ${wrong.length} revision session${wrong.length>1?'s':''} scheduled</span>`
      : '<span style="font-size:12px;opacity:.8"> — Excellent! No extra revision needed.</span>'}`;
  body.prepend(resultBanner);

  submitBtn.textContent = 'Close';
  submitBtn.disabled = false;
  submitBtn.onclick = () => { closeModal('quizModal'); quizCleanup(); };
}

function quizCleanup() {
  _quizTopicId = null;
  _quizQuestions = [];
  _quizAnswers = {};
}

/* ──────────────────────────────────────────────────────
   STEP 20 — VOICE INPUT FOR AI CHAT
   Uses browser Web Speech API (free, no API key).
   Adds a mic button next to the send button.
────────────────────────────────────────────────────── */

(function initVoiceInput() {
  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  // Wait for FAB + panel to be injected by existing init code
  document.addEventListener('DOMContentLoaded', () => {
    // Poll until the input row exists (panel injected dynamically)
    const tryAdd = () => {
      const inputRow = document.querySelector('.ai-chat-input-row');
      if (!inputRow) { setTimeout(tryAdd, 300); return; }
      if (document.getElementById('aiMicBtn')) return; // already added

      const micBtn = document.createElement('button');
      micBtn.id        = 'aiMicBtn';
      micBtn.className = 'ai-chat-mic';
      micBtn.title     = SpeechRecognition
        ? 'Voice input'
        : 'Voice input (not supported in this browser)';
      micBtn.innerHTML = '🎤';
      micBtn.disabled  = !SpeechRecognition;

      // Insert before send button
      const sendBtn = document.getElementById('aiChatSend');
      inputRow.insertBefore(micBtn, sendBtn);

      if (!SpeechRecognition) return;

      let recognition = null;
      let listening   = false;

      micBtn.addEventListener('click', () => {
        if (listening) {
          recognition.stop();
          return;
        }

        recognition = new SpeechRecognition();
        recognition.lang        = 'en-IN';   // Indian English
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
          listening = true;
          micBtn.classList.add('mic-active');
          micBtn.innerHTML = '🔴';
          micBtn.title     = 'Listening… click to stop';
        };

        recognition.onresult = (event) => {
          const transcript = event.results[0][0].transcript;
          const inp = document.getElementById('aiChatInput');
          if (inp) {
            inp.value = transcript;
            inp.focus();
          }
        };

        recognition.onerror = (e) => {
          console.warn('Speech recognition error:', e.error);
        };

        recognition.onend = () => {
          listening = false;
          micBtn.classList.remove('mic-active');
          micBtn.innerHTML = '🎤';
          micBtn.title     = 'Voice input';
        };

        recognition.start();
      });
    };
    setTimeout(tryAdd, 600);
  });
})();

/* ═══════════════════════════════════════════════════════
   PHASE 7 — AI UPGRADES
   Feature 1: AI Auto-Fill Topic Form
   Feature 2: Quiz Modal Fix (scroll + wrong answer revision)
   Feature 3: Practice Session (in practice.html)
═══════════════════════════════════════════════════════ */

/* ──────────────────────────────────────────────────────
   FEATURE 1 — AI AUTO-FILL TOPIC FORM
   Reads topic name + subject, calls /api/ai/autofill-topic,
   then directly fills difficulty stars, hours, and deadline.
────────────────────────────────────────────────────── */

async function aiAutofillTopic() {
  const nameInput    = document.getElementById('topicNameInput');
  const hoursInput   = document.getElementById('estimatedHoursInput');
  const deadlineInput= document.getElementById('deadlineInput');
  const reasonStrip  = document.getElementById('autofillReason');
  const btn          = document.getElementById('aiAutofillBtn');
  const subjectName  = (document.getElementById('subjectNameHidden')?.value || '').trim();

  const topicName = (nameInput?.value || '').trim();
  if (!topicName) {
    if (nameInput) {
      nameInput.focus();
      nameInput.style.borderColor = '#f43f5e';
      setTimeout(() => nameInput.style.borderColor = '', 1500);
    }
    return;
  }

  // Loading state
  btn.disabled     = true;
  btn.innerHTML    = '<span style="opacity:.6">✨ Asking AI…</span>';
  if (reasonStrip) reasonStrip.style.display = 'none';

  try {
    const res  = await fetch('/api/ai/autofill-topic', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic_name: topicName, subject_name: subjectName })
    });
    const data = await res.json();

    if (data.error) {
      btn.innerHTML = '✨ AI Auto-Fill';
      btn.disabled  = false;
      const badge   = document.getElementById('aiDiffBadge');
      if (badge) {
        badge.textContent    = '⚠ AI unavailable';
        badge.style.display  = 'inline-flex';
        setTimeout(() => badge.style.display = 'none', 3000);
      }
      return;
    }

    // ── Fill difficulty stars ──────────────────────────
    setDifficulty(data.difficulty);

    // ── Fill estimated hours ───────────────────────────
    if (hoursInput) {
      hoursInput.value = data.estimated_hours;
      // Flash highlight to signal the fill
      hoursInput.classList.add('autofill-flash');
      setTimeout(() => hoursInput.classList.remove('autofill-flash'), 1000);
    }

    // ── Fill deadline ──────────────────────────────────
    if (deadlineInput) {
      deadlineInput.value = data.suggested_deadline;
      deadlineInput.classList.add('autofill-flash');
      setTimeout(() => deadlineInput.classList.remove('autofill-flash'), 1000);
    }

    // ── Show reason strip ──────────────────────────────
    if (reasonStrip && data.reason) {
      reasonStrip.innerHTML = `
        <span class="autofill-icon">✨</span>
        <span class="autofill-text">${escapeHtml(data.reason)}</span>
        <span class="autofill-override">You can override any field manually.</span>`;
      reasonStrip.style.display = 'flex';
    }

    btn.innerHTML = '✅ Filled!';
    setTimeout(() => {
      btn.innerHTML = '✨ AI Auto-Fill';
      btn.disabled  = false;
    }, 2000);

  } catch (e) {
    btn.innerHTML = '✨ AI Auto-Fill';
    btn.disabled  = false;
  }
}

/* ──────────────────────────────────────────────────────
   FEATURE 2 — QUIZ MODAL FIXES
   - quizBody is now .quiz-scroll-body (CSS gives it fixed height + scroll)
   - Wrong answers (2+) auto-add a revision note (shown in result)
   - renderQuiz and quizSubmit updated
────────────────────────────────────────────────────── */

// Override renderQuiz from Phase 6 with scroll-aware version
window.renderQuiz = function(questions) {
  const body = document.getElementById('quizBody');
  body.innerHTML = `<div class="quiz-scroll-inner">` + questions.map((q, qi) => `
    <div class="quiz-question" id="qq-${qi}">
      <div class="quiz-q-text">
        <span class="quiz-q-num">Q${qi+1}</span> ${escapeHtml(q.q)}
      </div>
      <div class="quiz-options">
        ${Object.entries(q.options || {}).map(([k, v]) => `
          <label class="quiz-option-label" id="qopt-${qi}-${k}">
            <input type="radio" name="q${qi}" value="${k}"
                   onchange="_quizAnswers[${qi}]='${k}'"/>
            <span class="quiz-option-key">${k}</span>
            <span class="quiz-option-text">${escapeHtml(v)}</span>
          </label>
        `).join('')}
      </div>
    </div>
  `).join('') + `</div>`;
};

// Override quizSubmit with wrong-answer revision scheduling
window.quizSubmit = async function() {
  const submitBtn = document.getElementById('quizSubmitBtn');
  submitBtn.disabled = true;

  let correct = 0;
  const wrong = [];

  _quizQuestions.forEach((q, qi) => {
    const chosen  = _quizAnswers[qi];
    const isRight = chosen === q.answer;
    if (isRight) {
      correct++;
    } else {
      wrong.push(qi);
    }
    Object.keys(q.options || {}).forEach(k => {
      const el = document.getElementById(`qopt-${qi}-${k}`);
      if (!el) return;
      if (k === q.answer)  el.classList.add('quiz-correct');
      else if (k === chosen) el.classList.add('quiz-wrong');
      el.querySelector('input').disabled = true;
    });
  });

  const total = _quizQuestions.length;
  const pct   = total ? Math.round(correct / total * 100) : 0;
  const emoji = pct >= 80 ? '🎉' : pct >= 60 ? '👍' : '📚';

  // Auto-schedule extra revision if 2+ wrong
  let revisionMsg = '';
  if (wrong.length >= 2 && _quizTopicId) {
    try {
      // Just hit the SM-2 rate endpoint with quality=2 (needs review soon)
      await fetch(`/api/reviews/${_quizTopicId}/rate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quality: 2 })
      });
      revisionMsg = `<div class="quiz-revision-note">
        📅 ${wrong.length} wrong answers detected — extra revision session scheduled automatically.
      </div>`;
    } catch(e) { /* ignore */ }
  }

  const body = document.getElementById('quizBody');
  const scrollInner = body.querySelector('.quiz-scroll-inner');
  if (scrollInner) {
    // Prepend result banner inside scroll area
    const banner = document.createElement('div');
    banner.className = `quiz-result ${pct >= 80 ? 'quiz-result-good' : pct >= 60 ? 'quiz-result-ok' : 'quiz-result-bad'}`;
    banner.innerHTML = `
      <span class="quiz-result-emoji">${emoji}</span>
      <div>
        <strong>${correct}/${total} correct (${pct}%)</strong>
        ${revisionMsg}
      </div>`;
    scrollInner.prepend(banner);
    body.scrollTop = 0;
  }

  submitBtn.textContent = 'Close';
  submitBtn.disabled    = false;
  submitBtn.onclick     = () => { closeModal('quizModal'); quizCleanup(); };
};

function setAnimatedAvatarLive(root, live) {
  if (!root) return;
  root.querySelectorAll('.avatar-animated-media, .profile-hover-media').forEach(media => {
    const animatedSrc = media.dataset.animatedSrc || media.getAttribute('src');
    if (!animatedSrc) return;
    if (live) {
      if (!media.getAttribute('src')) media.setAttribute('src', animatedSrc);
      if (media.tagName !== 'VIDEO') media.setAttribute('src', animatedSrc);
      media.hidden = false;
      if (media.tagName === 'VIDEO') {
        try { media.currentTime = 0; } catch (error) {}
        const playAttempt = media.play();
        if (playAttempt && typeof playAttempt.catch === 'function') {
          playAttempt.catch(() => {});
        }
      }
      return;
    }
    if (media.tagName === 'VIDEO') {
      media.pause();
      try { media.currentTime = 0; } catch (error) {}
      media.hidden = false;
      if (!media.getAttribute('src')) media.setAttribute('src', animatedSrc);
      return;
    }
    const staticSrc = media.dataset.staticSrc;
    if (staticSrc) {
      media.setAttribute('src', staticSrc);
      media.hidden = false;
    } else {
      media.hidden = true;
      media.removeAttribute('src');
      if (typeof media.load === 'function') media.load();
    }
  });
}

const PROFILE_MEDIA_HOVER_ROOTS = [
  '.profile-animation-hover',
  '.sidebar-user',
  '.sidebar-account-link',
  '.profile-photo-row',
  '.decoration-card',
  '.avatar-reward-preview',
  '.conversation-row',
  '.chat-bubble-row',
  '.person-row',
  '.people-mini-row',
  '.avatar-link',
  '.decorated-avatar',
  '.profile-banner-preview'
].join(',');

function closestProfileMediaHoverRoot(target) {
  const root = target?.closest?.(PROFILE_MEDIA_HOVER_ROOTS);
  if (!root || !root.querySelector?.('.avatar-animated-media, .profile-hover-media')) return null;
  return root;
}

function isAlwaysLiveProfileMedia(root) {
  return Boolean(root?.classList?.contains('profile-animation-live') || root?.querySelector?.('.profile-animation-live'));
}

function wireAnimatedProfileMedia() {
  document.querySelectorAll('.profile-animation-live').forEach(root => {
    setAnimatedAvatarLive(root, true);
  });

  document.addEventListener('pointerover', event => {
    const root = closestProfileMediaHoverRoot(event.target);
    if (!root || isAlwaysLiveProfileMedia(root)) return;
    if (event.relatedTarget && root.contains(event.relatedTarget)) return;
    setAnimatedAvatarLive(root, true);
  });

  document.addEventListener('pointerout', event => {
    const root = closestProfileMediaHoverRoot(event.target);
    if (!root || isAlwaysLiveProfileMedia(root)) return;
    if (event.relatedTarget && root.contains(event.relatedTarget)) return;
    setAnimatedAvatarLive(root, false);
  });

  document.addEventListener('focusin', event => {
    const root = closestProfileMediaHoverRoot(event.target);
    if (!root || isAlwaysLiveProfileMedia(root)) return;
    setAnimatedAvatarLive(root, true);
  });

  document.addEventListener('focusout', event => {
    const root = closestProfileMediaHoverRoot(event.target);
    if (!root || isAlwaysLiveProfileMedia(root)) return;
    setAnimatedAvatarLive(root, false);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', wireAnimatedProfileMedia);
} else {
  wireAnimatedProfileMedia();
}
