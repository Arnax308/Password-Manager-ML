const API_BASE = 'http://127.0.0.1:5000';
let cachedPopupPasswords = [];
let lastDetectedDomain = '';
let lastTypedUser = '';

let ipcRenderer = null;
try {
  if (typeof require !== 'undefined') {
    ipcRenderer = require('electron').ipcRenderer;
  }
} catch (e) {}

// TOAST
function showPopupToast(message, type = 'success') {
  const container = document.getElementById('popup-toast-container');
  const toast = document.createElement('div');
  toast.className = `popup-toast popup-toast-${type}`;
  toast.innerHTML = `<i class="fa-solid ${type === 'success' ? 'fa-circle-check' : 'fa-triangle-exclamation'}"></i> <span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 250);
  }, 2000);
}

// TAB SWITCHING
function switchPopupTab(tabName, btn) {
  document.querySelectorAll('.popup-tab').forEach(t => t.classList.remove('active'));
  if (btn) btn.classList.add('active');
  else {
    const matchingTab = document.querySelector(`.popup-tab[data-tab="${tabName}"]`);
    if (matchingTab) matchingTab.classList.add('active');
  }

  document.querySelectorAll('.popup-tab-content').forEach(c => c.classList.remove('active'));
  const target = document.getElementById(`popup-tab-${tabName}`);
  if (target) target.classList.add('active');
}

// CLOSE POPUP
function closePopup() {
  if (ipcRenderer) {
    ipcRenderer.send('close-popup');
  } else {
    window.close();
  }
}

// ESC to close
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closePopup();
});

// SEARCH & SITE DETECTION
async function loadPopupPasswords() {
  try {
    const res = await fetch(`${API_BASE}/api/passwords`);
    if (res.ok) {
      cachedPopupPasswords = await res.json();
    }
  } catch (err) {
    console.error('Failed to load passwords for popup:', err);
  }
}

function extractDomainOrSite(url, title) {
  if (url) {
    try {
      let u = url.trim();
      if (!u.startsWith('http://') && !u.startsWith('https://')) {
        u = 'https://' + u;
      }
      const parsedUrl = new URL(u);
      let host = parsedUrl.hostname.toLowerCase().replace(/^www\./, '');
      if (host && host.includes('.')) return host;
    } catch (e) {}
  }
  if (title) {
    const knownSites = ['github', 'google', 'facebook', 'twitter', 'x.com', 'amazon', 'reddit', 'netflix', 'linkedin', 'microsoft', 'apple', 'discord', 'figma', 'notion', 'spotify', 'nexusmods', 'zoom', 'ubisoft', 'steampowered', 'epicgames'];
    const lowerTitle = title.toLowerCase();
    for (const site of knownSites) {
      if (lowerTitle.includes(site)) {
        return site + '.com';
      }
    }
    const match = title.match(/([a-zA-Z0-9-]+\.[a-zA-Z]{2,})/);
    if (match) return match[1].toLowerCase().replace(/^www\./, '');
  }
  return '';
}

function handlePopupSearch() {
  const query = document.getElementById('popup-search-input').value.toLowerCase().trim();
  const container = document.getElementById('popup-results');

  if (!query) {
    container.innerHTML = `
      <div class="popup-empty-state">
        <i class="fa-solid fa-vault"></i>
        <span>Type to search your vault</span>
      </div>`;
    return;
  }

  const cleanQuery = query.replace(/^www\./, '');
  const matches = cachedPopupPasswords.filter(p => {
    const entryDom = (p.domain || '').toLowerCase().replace(/^www\./, '');
    const entryUser = (p.username || '').toLowerCase();

    const domainMatch = entryDom && (
      entryDom.includes(cleanQuery) || 
      cleanQuery.includes(entryDom) ||
      cleanQuery.split('.').some(part => part.length > 3 && entryDom.includes(part))
    );
    const userMatch = entryUser.includes(cleanQuery);
    return domainMatch || userMatch;
  });

  if (matches.length === 0) {
    container.innerHTML = `
      <div class="popup-no-entry-card">
        <div class="popup-no-entry-icon"><i class="fa-solid fa-globe"></i></div>
        <div class="popup-no-entry-title">No entries saved for <strong>${query}</strong></div>
        <div class="popup-no-entry-sub">Would you like to save credentials for this website?</div>
        <button class="popup-btn-primary mt-3" onclick="showPopupCreateForm('${query}')">
          <i class="fa-solid fa-plus"></i> Create Password Entry for ${query}
        </button>
      </div>`;
    return;
  }

  let html = matches.map(p => {
    const avatarChar = p.domain ? p.domain[0].toUpperCase() : '?';
    const scorePct = Math.round((p.strength_score || 1.0) * 100);
    let scoreClass = 'popup-score-good';
    if (scorePct < 50) scoreClass = 'popup-score-bad';
    else if (scorePct < 75) scoreClass = 'popup-score-mid';

    const safePw = p.password.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    const safeUser = p.username.replace(/\\/g, '\\\\').replace(/'/g, "\\'");

    return `
      <div class="popup-result-card">
        <div class="popup-result-avatar">${avatarChar}</div>
        <div class="popup-result-info">
          <div class="popup-result-domain">${p.domain}</div>
          <div class="popup-result-user">${p.username}</div>
        </div>
        <span class="popup-result-score ${scoreClass}">${scorePct}%</span>
        <div class="popup-result-actions">
          <button class="popup-btn-icon" onclick="copyPopupPassword('${safePw}')" title="Copy Password"><i class="fa-regular fa-copy"></i></button>
          <button class="popup-btn-accent" onclick="popupAutotype('${safeUser}', '${safePw}')" title="AutoFill"><i class="fa-solid fa-bolt"></i></button>
        </div>
      </div>`;
  }).join('');

  // Add quick 'Save another account' button at the bottom
  html += `
    <div class="popup-add-more-row">
      <button class="popup-btn-add-account" onclick="showPopupCreateForm('${query}')">
        <i class="fa-solid fa-plus"></i> Save another account for ${query}
      </button>
    </div>`;

  container.innerHTML = html;
}

function copyPopupPassword(pw) {
  navigator.clipboard.writeText(pw);
  showPopupToast('Password copied!');
}

async function popupAutotype(username, password) {
  try {
    const res = await fetch(`${API_BASE}/api/popup/autotype`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    if (res.ok) {
      showPopupToast('Auto-typing...');
      setTimeout(closePopup, 500);
    }
  } catch (err) {
    showPopupToast('AutoType failed', 'error');
  }
}

// INLINE CREATION IN POPUP
async function showPopupCreateForm(domain = '') {
  switchPopupTab('create');
  const domainInput = document.getElementById('popup-create-domain');
  const userInput = document.getElementById('popup-create-username');
  const passInput = document.getElementById('popup-create-password');

  if (domainInput) domainInput.value = domain || lastDetectedDomain || '';
  if (userInput) userInput.value = lastTypedUser || '';

  // Auto-generate password if empty
  if (passInput && !passInput.value) {
    await fillPopupCreateGeneratedPassword();
  }
}

async function fillPopupCreateGeneratedPassword() {
  const passInput = document.getElementById('popup-create-password');
  if (!passInput) return;
  try {
    const res = await fetch(`${API_BASE}/api/generate`);
    if (res.ok) {
      const data = await res.json();
      passInput.value = data.generated_password;
    } else {
      passInput.value = generateStandardPasswordString(20);
    }
  } catch (e) {
    passInput.value = generateStandardPasswordString(20);
  }
}

function togglePopupCreatePasswordVisibility() {
  const passInput = document.getElementById('popup-create-password');
  const icon = document.getElementById('popup-create-eye-icon');
  if (passInput) {
    const isPass = passInput.type === 'password';
    passInput.type = isPass ? 'text' : 'password';
    if (icon) {
      icon.className = isPass ? 'fa-solid fa-eye-slash' : 'fa-solid fa-eye';
    }
  }
}

async function handlePopupCreateSubmit(e) {
  e.preventDefault();
  const domain = document.getElementById('popup-create-domain').value.trim();
  const username = document.getElementById('popup-create-username').value.trim();
  const password = document.getElementById('popup-create-password').value;

  if (!domain || !username || !password) {
    showPopupToast('Please fill in all fields', 'warn');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/passwords`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain, username, password })
    });

    if (res.ok) {
      showPopupToast('Saved to vault!');
      await loadPopupPasswords();

      // Switch back to vault search tab and show the entry!
      switchPopupTab('search');
      const input = document.getElementById('popup-search-input');
      if (input) {
        input.value = domain;
        handlePopupSearch();
      }
    } else {
      const err = await res.json().catch(() => ({}));
      showPopupToast(err.detail || 'Failed to save entry', 'error');
    }
  } catch (err) {
    showPopupToast('Failed to connect to backend', 'error');
  }
}

// GENERATOR
function generateStandardPasswordString(length = 20) {
  const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?';
  let pwd = '';
  for (let i = 0; i < length; i++) {
    pwd += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return pwd;
}

function popupGenerateStandard() {
  const upper = document.getElementById('popup-gen-upper').checked;
  const numbers = document.getElementById('popup-gen-numbers').checked;
  const symbols = document.getElementById('popup-gen-symbols').checked;
  const length = parseInt(document.getElementById('popup-gen-length').value, 10);

  let chars = 'abcdefghijklmnopqrstuvwxyz';
  if (upper) chars += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  if (numbers) chars += '0123456789';
  if (symbols) chars += '!@#$%^&*()_+-=[]{}|;:,.<>?';

  let pwd = '';
  for (let i = 0; i < length; i++) {
    pwd += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  document.getElementById('popup-gen-text').innerText = pwd;
}

async function popupGenerateSmart() {
  try {
    const res = await fetch(`${API_BASE}/api/generate`);
    if (res.ok) {
      const data = await res.json();
      document.getElementById('popup-gen-text').innerText = data.generated_password;
      showPopupToast(`ML Generated! Score: ${data.score.toFixed(2)}`);
    } else {
      popupGenerateStandard();
    }
  } catch (err) {
    popupGenerateStandard();
  }
}

function copyPopupGenerated() {
  const pwd = document.getElementById('popup-gen-text').innerText;
  if (pwd && pwd !== 'Click Generate') {
    navigator.clipboard.writeText(pwd);
    showPopupToast('Password copied!');
  }
}

// INIT & POPUP SHOWN EVENT
document.addEventListener('DOMContentLoaded', () => {
  loadPopupPasswords();

  if (ipcRenderer) {
    ipcRenderer.on('popup-context', (event, data) => {
      handleContextData(data);
    });
    ipcRenderer.on('popup-shown', () => {
      onPopupShown();
    });
  }

  onPopupShown();
});

function handleContextData(data) {
  if (!data) return;
  lastTypedUser = data.typed_user || '';
  const domain = extractDomainOrSite(data.browser_url, data.title);
  if (domain) {
    lastDetectedDomain = domain;
    const input = document.getElementById('popup-search-input');
    if (input) {
      input.value = domain;
      handlePopupSearch();
    }
  }
}

async function onPopupShown() {
  const input = document.getElementById('popup-search-input');
  if (input) {
    input.focus();
  }
  await loadPopupPasswords();

  try {
    const res = await fetch(`${API_BASE}/api/popup/trigger`);
    if (res.ok) {
      const data = await res.json();
      handleContextData(data);
    }
  } catch (e) {}
}
