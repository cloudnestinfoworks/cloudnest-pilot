// Cloudnest Pilot — web UI client logic.
// Vanilla JS, no frameworks, no build step.
//
// Key changes from v0.1.0:
//   - Input remains usable after a tool denial (was frozen before)
//   - Better error toasts for API failures
//   - Auto-scroll to bottom on new messages even if user scrolled up
//   - Robust against pending-tool race conditions

const messagesEl = document.getElementById('messages');
const inputEl = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const greetingEl = document.getElementById('greeting');
const clusterListEl = document.getElementById('clusterList');
const clusterCountEl = document.getElementById('clusterCount');

let busy = false; // single-flight: don't allow concurrent requests

function setBusy(value) {
  busy = value;
  sendBtn.disabled = value;
  inputEl.readOnly = value;
}

// ─── Markdown rendering (minimal) ─────────────────────────────
function renderMarkdown(text) {
  if (!text) return '';
  let s = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  s = s.replace(/```(\w+)?\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code class="lang-${lang || ''}">${code.replace(/\n$/, '')}</code></pre>`
  );
  s = s.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  s = s.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  s = s.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  s = s.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  s = s.replace(/^(\s*)[-*] (.+)$/gm, '<li>$2</li>');
  s = s.replace(/(<li>.*?<\/li>\n?)+/g, m => `<ul>${m}</ul>`);
  s = s.replace(/^\d+\.\s(.+)$/gm, '<li>$1</li>');

  const paragraphs = s.split(/\n\n+/);
  return paragraphs.map(p => {
    const t = p.trim();
    if (!t) return '';
    if (t.startsWith('<pre>') || t.startsWith('<ul>') || t.startsWith('<h')) return t;
    return `<p>${t.replace(/\n/g, '<br>')}</p>`;
  }).join('');
}

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

// ─── Message UI ─────────────────────────────
function removeGreeting() {
  if (greetingEl && greetingEl.parentNode) greetingEl.parentNode.removeChild(greetingEl);
}

function appendUserMessage(text) {
  removeGreeting();
  const msg = document.createElement('div');
  msg.className = 'message user-msg';
  msg.innerHTML = `
    <div class="message-header"><span class="dot"></span> You</div>
    <div class="message-body">${escapeHtml(text)}</div>
  `;
  messagesEl.appendChild(msg);
  scrollToBottom();
}

function appendAgentText(text) {
  const msg = document.createElement('div');
  msg.className = 'message agent-msg';
  msg.innerHTML = `
    <div class="message-header"><span class="dot"></span> Agent</div>
    <div class="message-body">${renderMarkdown(text)}</div>
  `;
  messagesEl.appendChild(msg);
  scrollToBottom();
}

function appendToolResult(toolName, output) {
  const div = document.createElement('div');
  div.className = 'tool-result';
  const truncated = output.length > 4000
    ? output.slice(0, 2000) + '\n\n[... ' + (output.length - 4000) + ' chars truncated ...]\n\n' + output.slice(-2000)
    : output;
  div.innerHTML = `
    <div class="tool-result-card">
      <div class="tool-name">${escapeHtml(toolName)}</div>
      <pre>${escapeHtml(truncated)}</pre>
    </div>
  `;
  messagesEl.appendChild(div);
  scrollToBottom();
}

function appendThinking() {
  const div = document.createElement('div');
  div.className = 'thinking';
  div.id = 'thinking-indicator';
  div.innerHTML = `
    <div class="thinking-inner">
      <span>thinking</span>
      <span class="thinking-dots"><span></span><span></span><span></span></span>
    </div>
  `;
  messagesEl.appendChild(div);
  scrollToBottom();
}

function removeThinking() {
  const el = document.getElementById('thinking-indicator');
  if (el) el.remove();
}

function appendErrorToast(message) {
  const div = document.createElement('div');
  div.className = 'error-card';
  div.innerHTML = `
    <div class="error-inner">
      <strong>Error</strong>
      ${escapeHtml(message)}
    </div>
  `;
  messagesEl.appendChild(div);
  scrollToBottom();
}

function appendConfirmationCard(call) {
  const { tool_use_id, tool_name, tool_input } = call;
  const card = document.createElement('div');
  card.className = 'confirm-card';
  card.dataset.toolUseId = tool_use_id;

  let title = 'Confirm action';
  let purposeText = '';
  let payloadHtml = '';
  let metaHtml = '';

  if (tool_name === 'run_shell') {
    title = '⚠ Approval needed — shell command';
    purposeText = tool_input.purpose || '';
    const argv = tool_input.argv || [];
    const cmd = argv.map(shellQuote).join(' ');
    payloadHtml = `<span class="cmd-prefix">$ </span>${escapeHtml(cmd)}`;
    const cwd = tool_input.cwd || '.';
    const timeout = tool_input.timeout_seconds || 600;
    metaHtml = `<div class="confirm-meta">
      <span>cwd: ${escapeHtml(cwd)}</span>
      <span>timeout: ${timeout}s</span>
    </div>`;
  } else if (tool_name === 'write_file') {
    title = '⚠ Approval needed — write file';
    purposeText = tool_input.purpose || '';
    const content = tool_input.content || '';
    const preview = content.length > 1500 ? content.slice(0, 1500) + '\n\n[... truncated ...]' : content;
    payloadHtml = escapeHtml(preview);
    metaHtml = `<div class="confirm-meta">
      <span>path: ${escapeHtml(tool_input.path || '')}</span>
      <span>size: ${content.length} chars</span>
    </div>`;
  } else {
    title = `⚠ Approval needed — ${tool_name}`;
    payloadHtml = escapeHtml(JSON.stringify(tool_input, null, 2));
  }

  const purposeHtml = purposeText
    ? `<div class="confirm-purpose"><span class="label">Purpose</span>${escapeHtml(purposeText)}</div>`
    : '';

  card.innerHTML = `
    <div class="confirm-inner">
      <div class="confirm-title">${title}</div>
      ${purposeHtml}
      <div class="confirm-payload">${payloadHtml}</div>
      ${metaHtml}
      <div class="confirm-actions">
        <button class="btn-action btn-deny" data-action="deny">Deny</button>
        <button class="btn-action btn-approve" data-action="approve">Approve &amp; run</button>
      </div>
    </div>
  `;
  messagesEl.appendChild(card);
  scrollToBottom();
  return card;
}

function shellQuote(s) {
  if (/^[A-Za-z0-9_\-=\/.:@]+$/.test(s)) return s;
  return "'" + s.replace(/'/g, "'\\''") + "'";
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  });
}

// ─── API calls ─────────────────────────────
async function sendMessage() {
  if (busy) return;
  const text = inputEl.value.trim();
  if (!text) return;

  inputEl.value = '';
  autoGrow();
  setBusy(true);

  appendUserMessage(text);
  appendThinking();

  try {
    const res = await fetch('/api/chat/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      credentials: 'same-origin',
    });
    removeThinking();
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Request failed' }));
      appendErrorToast(err.error || 'Unknown error');
      return;
    }
    const data = await res.json();
    await handleTurnResponse(data);
  } catch (e) {
    removeThinking();
    appendErrorToast(`Network error: ${e.message}`);
  } finally {
    setBusy(false);
    inputEl.focus();
    refreshClusters();
  }
}

async function handleTurnResponse(data) {
  for (const text of (data.texts || [])) {
    appendAgentText(text);
  }
  for (const result of (data.auto_tool_results || [])) {
    appendToolResult(result.tool, result.output);
  }
  if (data.pending_tools && data.pending_tools.length > 0) {
    await handlePendingTools(data.pending_tools);
  }
}

async function handlePendingTools(pendingTools) {
  // Render all confirmation cards at once, let user decide each.
  // KEY FIX: setBusy(false) here so input is usable, then re-set after they decide.
  setBusy(false);
  inputEl.focus();

  const cards = pendingTools.map(call => ({ call, element: appendConfirmationCard(call) }));

  const approvals = await Promise.all(cards.map(({ call, element }) => new Promise(resolve => {
    element.querySelector('[data-action="approve"]').addEventListener('click', () => {
      element.querySelectorAll('button').forEach(b => b.disabled = true);
      const titleEl = element.querySelector('.confirm-title');
      titleEl.textContent = '✓ Approved — running...';
      element.querySelector('.confirm-inner').style.borderColor = 'var(--success)';
      resolve({ id: call.tool_use_id, approved: true });
    });
    element.querySelector('[data-action="deny"]').addEventListener('click', () => {
      element.querySelectorAll('button').forEach(b => b.disabled = true);
      const titleEl = element.querySelector('.confirm-title');
      titleEl.textContent = '✗ Denied';
      element.querySelector('.confirm-inner').style.borderColor = 'var(--danger)';
      resolve({ id: call.tool_use_id, approved: false });
    });
  })));

  const approvalsMap = {};
  for (const a of approvals) approvalsMap[a.id] = a.approved;

  setBusy(true);
  appendThinking();

  try {
    const res = await fetch('/api/chat/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approvals: approvalsMap, edited_inputs: {} }),
      credentials: 'same-origin',
    });
    removeThinking();
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Request failed' }));
      appendErrorToast(err.error || 'Tool execution error');
      // KEY FIX: even on error, ensure input is re-enabled below in finally
      return;
    }
    const data = await res.json();
    await handleTurnResponse(data);
  } catch (e) {
    removeThinking();
    appendErrorToast(`Tool execution failed: ${e.message}`);
  } finally {
    setBusy(false);
    inputEl.focus();
  }
}

async function refreshClusters() {
  try {
    const res = await fetch('/api/clusters', { credentials: 'same-origin' });
    if (!res.ok) return;
    const data = await res.json();
    const clusters = data.clusters || [];
    clusterCountEl.textContent = clusters.length;
    if (clusters.length === 0) {
      clusterListEl.innerHTML = '<div class="empty-hint">No clusters yet. Tell the agent to deploy one.</div>';
      return;
    }
    clusterListEl.innerHTML = clusters.map(c => `
      <div class="cluster-item" onclick="quickStart('Check the health of cluster ${escapeHtml(c.name)}')">
        <div class="name">${escapeHtml(c.name)}</div>
        <div class="status">
          <span class="status-dot ${c.status === 'ready' ? 'ready' : c.status === 'installed' ? 'installed' : 'configured'}"></span>
          ${escapeHtml(c.status)}
        </div>
      </div>
    `).join('');
  } catch (e) {
    // Silent fail — sidebar is non-essential
  }
}

async function resetSession() {
  if (!confirm('Start a fresh conversation? This clears the current chat history.')) return;
  await fetch('/api/reset', { method: 'POST', credentials: 'same-origin' });
  window.location.reload();
}

// ─── UI niceties ─────────────────────────────
function quickStart(text) {
  inputEl.value = text;
  autoGrow();
  sendMessage();
}

function autoGrow() {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + 'px';
}

inputEl.addEventListener('input', autoGrow);
inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Make functions globally callable from inline onclick handlers.
window.sendMessage = sendMessage;
window.resetSession = resetSession;
window.quickStart = quickStart;

// Populate environment info
document.getElementById('envOs').textContent = /Win/.test(navigator.platform) ? 'Windows'
  : /Mac/.test(navigator.platform) ? 'macOS' : 'Linux';
document.getElementById('envModel').textContent = 'Claude';

// Initial cluster load
refreshClusters();
setInterval(() => { if (!document.hidden) refreshClusters(); }, 10000);

inputEl.focus();
