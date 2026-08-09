const API_BASE = 'http://127.0.0.1:5000';
let currentMasterPassword = '';
let currentCategoryFilter = 'All';
let cachedPasswords = [];

let ipcRenderer = null;
try {
  if (typeof require !== 'undefined') {
    ipcRenderer = require('electron').ipcRenderer;
  }
} catch (e) {}

// TOAST NOTIFICATIONS
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  const iconClass = type === 'success' ? 'fa-circle-check text-accent' : (type === 'warn' ? 'fa-triangle-exclamation text-warn' : 'fa-circle-exclamation text-danger');
  toast.innerHTML = `<i class="fa-solid ${iconClass}"></i> <span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

function togglePasswordVisibility(inputId) {
  const input = document.getElementById(inputId);
  input.type = input.type === 'password' ? 'text' : 'password';
}

// SIDEBAR COLLAPSE / EXPAND TOGGLE
function initSidebarState() {
  const isCollapsed = localStorage.getItem('valtr_sidebar_collapsed') === 'true';
  const sidebar = document.getElementById('app-sidebar');
  const toggleIcon = document.getElementById('sidebar-toggle-icon');
  if (sidebar) {
    if (isCollapsed) {
      sidebar.classList.add('collapsed');
      if (toggleIcon) toggleIcon.className = 'fa-solid fa-chevron-right';
    } else {
      sidebar.classList.remove('collapsed');
      if (toggleIcon) toggleIcon.className = 'fa-solid fa-chevron-left';
    }
  }
}

function toggleSidebar() {
  const sidebar = document.getElementById('app-sidebar');
  const toggleIcon = document.getElementById('sidebar-toggle-icon');
  if (!sidebar) return;

  const isCollapsed = sidebar.classList.toggle('collapsed');
  localStorage.setItem('valtr_sidebar_collapsed', isCollapsed ? 'true' : 'false');

  if (toggleIcon) {
    toggleIcon.className = isCollapsed ? 'fa-solid fa-chevron-right' : 'fa-solid fa-chevron-left';
  }
}

// SLIDER TRACK FILL DYNAMIC UPDATER
function updateSliderFill(input) {
  if (!input) return;
  const min = parseFloat(input.min) || 0;
  const max = parseFloat(input.max) || 100;
  const val = parseFloat(input.value) || 0;
  const pct = ((val - min) / (max - min)) * 100;
  const accentColor = getComputedStyle(document.body).getPropertyValue('--accent-color').trim() || '#10b981';
  const trackColor = getComputedStyle(document.body).getPropertyValue('--card-border').trim() || '#1e293b';
  input.style.background = `linear-gradient(to right, ${accentColor} 0%, ${accentColor} ${pct}%, ${trackColor} ${pct}%, ${trackColor} 100%)`;
}

function initSliderFills() {
  document.querySelectorAll('input[type="range"]').forEach(input => {
    updateSliderFill(input);
    input.addEventListener('input', () => updateSliderFill(input));
  });
}

// INTERFACE THEMES
function setTheme(themeName) {
  document.body.setAttribute('data-theme', themeName);
  localStorage.setItem('valtr_theme', themeName);
  document.querySelectorAll('[data-theme-pill]').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-theme-pill') === themeName);
  });
  initSliderFills();
  showToast(`Theme set to ${themeName}`);
}

function initTheme() {
  const theme = localStorage.getItem('valtr_theme') || 'Obsidian';
  document.body.setAttribute('data-theme', theme);
  document.querySelectorAll('[data-theme-pill]').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-theme-pill') === theme);
  });
}

// APP INITIALIZATION
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initSidebarState();
  initSliderFills();
  setupNavigation();
  checkAppStatus();
});

// NAVIGATION
function setupNavigation() {
  const navBtns = document.querySelectorAll('.nav-item[data-tab]');
  navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabName = btn.getAttribute('data-tab');
      switchTab(tabName);
    });
  });
}

function switchTab(tabName) {
  document.querySelectorAll('.nav-item[data-tab]').forEach(b => b.classList.remove('active'));
  const activeBtn = document.querySelector(`.nav-item[data-tab="${tabName}"]`);
  if (activeBtn) activeBtn.classList.add('active');

  document.querySelectorAll('.tab-view').forEach(v => v.classList.remove('active'));
  const activeView = document.getElementById(`view-${tabName}`);
  if (activeView) activeView.classList.add('active');

  // Load view data
  if (tabName === 'vault') loadVaultData();
  else if (tabName === 'notes') loadNotesData();
  else if (tabName === 'health') loadHealthData();
  else if (tabName === 'logs') loadLogsData();
  else if (tabName === 'ml' || tabName === 'generator') loadMlSettings();
  else if (tabName === 'settings') loadSettingsData();
}

function refreshCurrentView() {
  const activeView = document.querySelector('.tab-view.active');
  if (activeView) {
    const tabName = activeView.id.replace('view-', '');
    switchTab(tabName);
    showToast('View refreshed.');
  }
}

// APP STATUS & AUTH
let isSessionAuthenticated = false;

async function checkAppStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/status`);
    if (!res.ok) throw new Error('Backend connecting...');
    const status = await res.json();

    const authScreen = document.getElementById('auth-screen');
    const mainApp = document.getElementById('main-app');
    const groupSetup = document.getElementById('group-setup-name');
    const submitBtnText = document.getElementById('btn-auth-text');

    if (status.is_unlocked && isSessionAuthenticated) {
      authScreen.classList.remove('active');
      mainApp.classList.add('active');
      switchTab('vault');
      return;
    }

    authScreen.classList.add('active');
    mainApp.classList.remove('active');

    if (status.is_setup) {
      groupSetup.style.display = 'none';
      submitBtnText.innerText = 'Unlock Vault';
    } else {
      groupSetup.style.display = 'flex';
      submitBtnText.innerText = 'Setup Master Vault';
    }
  } catch (err) {
    document.getElementById('auth-error').innerText = 'Connecting to security backend...';
    setTimeout(checkAppStatus, 1500);
  }
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const password = document.getElementById('input-master-password').value;
  const nameInput = document.getElementById('input-setup-name').value;
  const errorDiv = document.getElementById('auth-error');
  errorDiv.innerText = '';

  try {
    const statusRes = await fetch(`${API_BASE}/api/status`);
    const status = await statusRes.json();

    let endpoint = '/api/unlock';
    let body = { master_password: password };

    if (!status.is_setup) {
      endpoint = '/api/setup';
      body = { master_password: password, user_name: nameInput };
    }

    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });

    const data = await res.json();
    if (res.ok) {
      isSessionAuthenticated = true;
      currentMasterPassword = password;
      document.getElementById('auth-screen').classList.remove('active');
      document.getElementById('main-app').classList.add('active');
      switchTab('vault');
      showToast('Vault unlocked successfully!');
    } else {
      errorDiv.innerText = data.detail || 'Incorrect Master Password';
    }
  } catch (err) {
    errorDiv.innerText = 'Failed to connect to security backend.';
  }
}

async function lockVault() {
  await fetch(`${API_BASE}/api/lock`, { method: 'POST' });
  isSessionAuthenticated = false;
  currentMasterPassword = '';
  document.getElementById('input-master-password').value = '';
  checkAppStatus();
  showToast('Vault locked.');
}

// VAULT VIEW (MATCHING IMAGE 4)
async function loadVaultData() {
  try {
    const res = await fetch(`${API_BASE}/api/passwords`);
    cachedPasswords = res.ok ? await res.json() : [];
    renderVaultList(cachedPasswords);
    updateExpiryNotifications(cachedPasswords);
  } catch (err) {
    console.error('Failed to load vault data:', err);
  }
}

function handleVaultSearch() {
  renderVaultList(cachedPasswords);
}

function handleGlobalHeaderSearch() {
  const searchInput = document.getElementById('global-header-search');
  if (!searchInput) return;
  const query = searchInput.value.toLowerCase().trim();
  const activeView = document.querySelector('.tab-view.active');
  if (!activeView) return;

  if (activeView.id === 'view-vault') {
    renderVaultList(cachedPasswords, query);
  } else if (activeView.id === 'view-notes') {
    renderNotesList(cachedNotes, query);
  } else if (activeView.id === 'view-logs') {
    renderLogsList(cachedLogs, query);
  }
}

function filterVaultCategory(catName, btnElement) {
  document.querySelectorAll('.cat-pill').forEach(p => p.classList.remove('active'));
  if (btnElement) btnElement.classList.add('active');
  currentCategoryFilter = catName;
  renderVaultList(cachedPasswords);
}

function renderVaultList(passwords, overrideQuery = null) {
  const searchQuery = overrideQuery !== null ? overrideQuery : document.getElementById('global-header-search').value.toLowerCase().trim();

  // Filter passwords
  let filtered = passwords.filter(p => {
    const matchesSearch = !searchQuery || 
      p.domain.toLowerCase().includes(searchQuery) || 
      p.username.toLowerCase().includes(searchQuery) ||
      (p.category && p.category.toLowerCase().includes(searchQuery));
    if (currentCategoryFilter === 'All') return matchesSearch;
    if (currentCategoryFilter === 'Weak') return matchesSearch && (p.strength_score || 1.0) < 0.5;
    if (currentCategoryFilter === 'Recent') return matchesSearch;
    return matchesSearch && (p.category === currentCategoryFilter);
  });

  // Sort alphabetically by domain name A->Z (and secondary by username)
  filtered.sort((a, b) => {
    const domainA = (a.domain || '').toLowerCase();
    const domainB = (b.domain || '').toLowerCase();
    if (domainA !== domainB) return domainA.localeCompare(domainB);
    const userA = (a.username || '').toLowerCase();
    const userB = (b.username || '').toLowerCase();
    return userA.localeCompare(userB);
  });

  document.getElementById('vault-subtitle-count').innerText = `${passwords.length} secure entries stored locally.`;

  const tbody = document.getElementById('vault-table-body');
  if (!tbody) return;

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; padding: 36px; color: var(--text-dim);">
          <i class="fa-solid fa-folder-open mb-2" style="font-size: 28px; display: block;"></i>
          No password entries found matching '${searchQuery || currentCategoryFilter}'.
        </td>
      </tr>`;
    return;
  }

  // Group entries by Domain
  const domainGroupMap = {};
  filtered.forEach(p => {
    const dom = (p.domain || '').toLowerCase().trim();
    if (!domainGroupMap[dom]) domainGroupMap[dom] = [];
    domainGroupMap[dom].push(p);
  });

  const now = new Date();
  let tableRowsHtml = '';

  Object.entries(domainGroupMap).forEach(([domainKey, accounts]) => {
    const primaryDomName = accounts[0].domain;
    const avatarChar = primaryDomName ? primaryDomName[0].toUpperCase() : '?';
    const safeDomain = primaryDomName.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    const isMulti = accounts.length > 1;

    // Check if multiple entries have the EXACT SAME PASSWORD
    let samePasswordGroup = false;
    if (isMulti) {
      const firstPw = accounts[0].password;
      samePasswordGroup = accounts.every(a => a.password === firstPw);
    }

    const isSearchActive = !!searchQuery;
    const domCategory = accounts.find(a => a.category)?.category || '';
    const groupId = `group-dom-${domainKey.replace(/[^a-zA-Z0-9]/g, '_')}`;

    // If multiple accounts exist for this domain, add a Domain Group Header Row!
    if (isMulti) {
      let actionButtons = '';
      if (samePasswordGroup) {
        actionButtons = `
          <button class="btn-primary" style="padding: 3px 10px; font-size: 11px;" onclick="mergeEntriesForDomain('${safeDomain}')">
            <i class="fa-solid fa-code-merge"></i> Merge Same-Password Accounts
          </button>`;
      } else {
        actionButtons = `
          <span class="text-dim" style="font-size: 11px; margin-right: 8px;">
            <i class="fa-solid fa-shield-halved text-accent"></i> Distinct Passwords (Not Merged)
          </span>`;
      }

      tableRowsHtml += `
        <tr class="domain-group-header-row" style="background: rgba(255, 255, 255, 0.035); border-bottom: 1px solid var(--card-border);">
          <td colspan="7" style="padding: 10px 18px;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <div style="display: flex; align-items: center; gap: 10px;">
                <div class="card-avatar" style="width: 28px; height: 28px; font-size: 12px;">${avatarChar}</div>
                <span class="vault-domain-title" style="font-size: 14px; font-weight: 700; color: #ffffff;">${primaryDomName}</span>
                ${domCategory ? `<span class="badge-tag" style="font-size: 10px; padding: 2px 8px;">${domCategory}</span>` : ''}
                <span class="badge-tag" style="font-size: 10px; background: rgba(16, 185, 129, 0.15); color: var(--accent-color); border: 1px solid rgba(16, 185, 129, 0.3);">
                  ${accounts.length} Accounts Linked
                </span>
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                ${actionButtons}
                <button class="btn-note-link active" onclick="toggleDomainGroupRows('${groupId}')" style="font-size: 11px;">
                  <i class="fa-solid ${isSearchActive ? 'fa-chevron-up' : 'fa-chevron-down'}" id="eye-${groupId}"></i> ${isSearchActive ? 'Collapse' : 'Expand'} Accounts (${accounts.length})
                </button>
              </div>
            </div>
          </td>
        </tr>`;
    }

    // Render each account row under this domain
    accounts.forEach((acct, idx) => {
      const acctScore = Math.round((acct.strength_score || 1.0) * 100);
      let acctTextClass = 'text-accent';
      if (acctScore < 50) acctTextClass = 'text-danger';
      else if (acctScore < 75) acctTextClass = 'text-warn';

      // Calculate ML TTL remaining days
      const maxTtl = acct.ttl_days || 365;
      const createdDate = acct.created_at ? new Date(acct.created_at) : new Date();
      const ageDays = Math.floor((now - createdDate) / (1000 * 60 * 60 * 24));
      const remainingTtl = Math.max(0, maxTtl - ageDays);
      let ttlBadgeClass = 'badge-ttl-ok';
      if (remainingTtl <= 0 || remainingTtl < 30) ttlBadgeClass = 'badge-ttl-danger';
      else if (remainingTtl < 90) ttlBadgeClass = 'badge-ttl-warn';

      // Safe string escapes
      const safePw = acct.password.replace(/\\/g, '\\\\').replace(/'/g, "\\'");

      // Parse usernames split by comma or slash
      const userParts = (acct.username || '').split(/[,/]/).map(u => u.trim()).filter(Boolean);
      const userBadgesHtml = userParts.map(u => {
        const safeU = u.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        return `
          <span class="badge-tag" style="font-size: 11.5px; padding: 2px 7px; background: rgba(255,255,255,0.06); border: 1px solid var(--card-border); color: var(--text-main); display: inline-flex; align-items: center; gap: 4px; margin-right: 4px;">
            <i class="fa-regular fa-user" style="font-size: 9.5px; color: var(--accent-color);"></i> ${u}
            <button class="btn-icon" onclick="copyToClipboard('${safeU}', 'Username copied!')" title="Copy ${u}" style="font-size: 9.5px; padding: 1px 3px; border: none; background: transparent;"><i class="fa-regular fa-copy"></i></button>
          </span>`;
      }).join('');

      // Associated Note Button
      let noteBtnHtml = '';
      if (acct.note_id) {
        noteBtnHtml = `<button class="btn-note-link active" onclick="openAssociatedNote(${acct.note_id})" title="View Associated Secure Note"><i class="fa-solid fa-file-lines"></i> View Note</button>`;
      } else {
        noteBtnHtml = `<button class="btn-note-link" onclick="createNoteForPassword(${acct.id}, '${safeDomain}')" title="Create Associated Secure Note"><i class="fa-solid fa-square-plus"></i> Add Note</button>`;
      }

      const rowGroupClass = isMulti ? `group-row-${groupId}` : '';
      const initialDisplayStyle = (isMulti && !isSearchActive) ? 'style="display: none;"' : '';

      tableRowsHtml += `
        <tr class="${rowGroupClass}" ${initialDisplayStyle}>
          <td>
            <div class="vault-domain-cell" style="${isMulti ? 'padding-left: 18px;' : ''}">
              ${!isMulti ? `<div class="card-avatar">${avatarChar}</div>` : '<i class="fa-solid fa-turn-up text-dim" style="transform: rotate(90deg); margin-right: 6px;"></i>'}
              <span class="vault-domain-title">${acct.domain}</span>
            </div>
          </td>
          <td>
            <div class="vault-user-cell" style="display: flex; flex-wrap: wrap; gap: 4px;">
              ${userBadgesHtml}
            </div>
          </td>
          <td>
            ${(!isMulti && acct.category) ? `<span class="badge-tag" style="font-size: 10px; padding: 2px 8px;">${acct.category}</span>` : '<span class="text-dim" style="font-size: 11px;">—</span>'}
          </td>
          <td>
            <span class="font-semibold ${acctTextClass}">${acctScore}%</span>
          </td>
          <td>
            <span class="badge-ttl ${ttlBadgeClass}" title="ML Dynamic Time-To-Live: ${remainingTtl}d remaining of ${maxTtl}d"><i class="fa-solid fa-hourglass-half"></i> ${remainingTtl}d</span>
          </td>
          <td>
            ${noteBtnHtml}
          </td>
          <td>
            <div class="vault-actions-cell">
              <button class="btn-icon" onclick="copyToClipboard('${safePw}', 'Password copied!')" title="Copy Password"><i class="fa-regular fa-key"></i></button>
              <button class="btn-icon" onclick="openEditPasswordModalById(${acct.id})" title="Edit Entry"><i class="fa-solid fa-pen"></i></button>
              <button class="btn-icon text-danger" onclick="deletePasswordEntry(${acct.id})" title="Delete Entry"><i class="fa-regular fa-trash-can"></i></button>
            </div>
          </td>
        </tr>`;
    });
  });

  tbody.innerHTML = tableRowsHtml;
}

function toggleDomainGroupRows(groupId) {
  const rows = document.querySelectorAll(`.group-row-${groupId}`);
  const eyeIcon = document.getElementById(`eye-${groupId}`);
  let isExpanding = false;
  rows.forEach(r => {
    if (r.style.display === 'none' || !r.style.display) {
      r.style.display = 'table-row';
      isExpanding = true;
    } else {
      r.style.display = 'none';
    }
  });
  if (eyeIcon) {
    if (isExpanding) {
      eyeIcon.className = 'fa-solid fa-chevron-up';
    } else {
      eyeIcon.className = 'fa-solid fa-chevron-down';
    }
  }
}

async function mergeEntriesForDomain(domainName) {
  const matches = cachedPasswords.filter(p => (p.domain || '').toLowerCase().trim() === domainName.toLowerCase().trim());
  if (matches.length < 2) return;

  // Verify passwords match
  const firstPw = matches[0].password;
  const samePasswordMatches = matches.filter(m => m.password === firstPw);

  if (samePasswordMatches.length < 2) {
    showToast('Cannot merge: entries have different passwords', 'warn');
    return;
  }

  const allUsernames = [];
  samePasswordMatches.forEach(m => {
    const parts = (m.username || '').split(/[,/]/).map(u => u.trim()).filter(Boolean);
    parts.forEach(u => {
      if (!allUsernames.includes(u)) allUsernames.push(u);
    });
  });

  const mergedUsernameStr = allUsernames.join(', ');
  const primary = samePasswordMatches[0];
  const secondaries = samePasswordMatches.slice(1);

  if (!confirm(`Merge ${samePasswordMatches.length} accounts for '${primary.domain}' with identical passwords into 1 entry?\nCombined Usernames: ${mergedUsernameStr}`)) return;

  try {
    await fetch(`${API_BASE}/api/passwords/${primary.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain: primary.domain,
        username: mergedUsernameStr,
        password: primary.password,
        note_id: primary.note_id,
        category: primary.category || ''
      })
    });

    for (const sec of secondaries) {
      await fetch(`${API_BASE}/api/passwords/${sec.id}`, { method: 'DELETE' });
    }

    showToast(`Merged matching accounts for ${primary.domain}!`);
    loadVaultData();
  } catch (err) {
    console.error('Failed to merge entries:', err);
    showToast('Failed to merge accounts', 'error');
  }
}

async function openAssociatedNote(noteId) {
  try {
    const res = await fetch(`${API_BASE}/api/notes`);
    const notes = res.ok ? await res.json() : [];
    const note = notes.find(n => n.id === noteId);
    if (note) {
      openEditNoteModal(note.id, note.title, note.content, (note.tags || []).join(','), note.is_hidden);
    } else {
      showToast('Associated note not found', 'warn');
    }
  } catch (err) {
    showToast('Failed to load associated note', 'error');
  }
}

function createNoteForPassword(passwordId, domain) {
  openAddNoteModal();
  document.getElementById('modal-note-input-title').value = `Note for ${domain}`;
  document.getElementById('modal-note-linked-password-id').value = passwordId;
}

function toggleDomainAccounts(cardId) {
  const list = document.getElementById(cardId);
  const icon = document.getElementById('icon-' + cardId);
  if (list) {
    list.classList.toggle('collapsed');
    if (icon) icon.classList.toggle('rotated');
  }
}

async function deletePasswordEntry(id) {
  if (!confirm('Permanently delete this password entry?')) return;
  const res = await fetch(`${API_BASE}/api/passwords/${id}`, { method: 'DELETE' });
  if (res.ok) {
    loadVaultData();
    showToast('Password entry deleted');
  } else {
    showToast('Failed to delete entry', 'error');
  }
}

function copyToClipboard(text, msg = 'Copied to clipboard!') {
  navigator.clipboard.writeText(text);
  showToast(msg);
}

function openEditPasswordModalById(id) {
  const acct = cachedPasswords.find(p => p.id == id);
  if (acct) {
    openEditPasswordModal(acct.id, acct.domain, acct.username, acct.password, acct.category || '', acct.note_id || null);
  } else {
    console.error('Account not found in cachedPasswords for id:', id);
  }
}

function openEditNoteModalById(id) {
  const note = cachedNotes.find(n => n.id == id);
  if (note) {
    openEditNoteModal(note.id, note.title, note.content, (note.tags || []).join(', '), note.is_hidden !== false);
  } else {
    console.error('Note not found in cachedNotes for id:', id);
  }
}

// MODALS FOR PASSWORDS
async function openAddPasswordModal() {
  document.getElementById('modal-pw-title').innerText = 'New Password Entry';
  document.getElementById('modal-pw-id').value = '';
  document.getElementById('modal-pw-domain').value = '';
  document.getElementById('modal-pw-username').value = '';
  document.getElementById('modal-pw-password').value = '';
  document.getElementById('modal-pw-quick-note').value = '';

  const catRes = await fetch(`${API_BASE}/api/categories`);
  const categories = catRes.ok ? await catRes.json() : [];
  const select = document.getElementById('modal-pw-category');
  select.innerHTML = '<option value="">Uncategorized</option>';
  categories.forEach(c => select.innerHTML += `<option value="${c}">${c}</option>`);

  await populateNoteLinkDropdown(null);

  document.getElementById('modal-password').classList.add('active');
}

async function openEditPasswordModal(id, domain, username, password, category, noteId) {
  document.getElementById('modal-pw-title').innerText = 'Edit Password Entry';
  document.getElementById('modal-pw-id').value = id;
  document.getElementById('modal-pw-domain').value = domain;
  document.getElementById('modal-pw-username').value = username;
  document.getElementById('modal-pw-password').value = password;
  document.getElementById('modal-pw-quick-note').value = '';

  const catRes = await fetch(`${API_BASE}/api/categories`);
  const categories = catRes.ok ? await catRes.json() : [];
  const select = document.getElementById('modal-pw-category');
  select.innerHTML = '<option value="">Uncategorized</option>';
  categories.forEach(c => {
    const sel = c === category ? ' selected' : '';
    select.innerHTML += `<option value="${c}"${sel}>${c}</option>`;
  });

  await populateNoteLinkDropdown(noteId || null);

  // If entry has a linked note, fetch and prefill the note content so user can edit it
  if (noteId) {
    try {
      const notesRes = await fetch(`${API_BASE}/api/notes`);
      if (notesRes.ok) {
        const allNotes = await notesRes.json();
        const linkedNote = allNotes.find(n => n.id == noteId);
        if (linkedNote) {
          document.getElementById('modal-pw-quick-note').value = linkedNote.content || '';
        }
      }
    } catch (e) {}
  }

  document.getElementById('modal-password').classList.add('active');
}

async function populateNoteLinkDropdown(selectedNoteId) {
  const noteSelect = document.getElementById('modal-pw-note-link');
  noteSelect.innerHTML = '<option value="">\u2014 None \u2014</option>';
  try {
    const res = await fetch(`${API_BASE}/api/notes`);
    if (res.ok) {
      const notes = await res.json();
      notes.forEach(n => {
        const sel = (selectedNoteId && n.id == selectedNoteId) ? ' selected' : '';
        noteSelect.innerHTML += `<option value="${n.id}"${sel}>${n.title}</option>`;
      });
    }
  } catch (e) {}
}

function closeModal(modalId) {
  document.getElementById(modalId).classList.remove('active');
}

async function handleSavePasswordSubmit(e) {
  e.preventDefault();
  const id = document.getElementById('modal-pw-id').value;
  const domain = document.getElementById('modal-pw-domain').value.trim();
  const username = document.getElementById('modal-pw-username').value.trim();
  const password = document.getElementById('modal-pw-password').value;
  const category = document.getElementById('modal-pw-category').value;
  const quickNote = document.getElementById('modal-pw-quick-note').value.trim();
  let noteId = document.getElementById('modal-pw-note-link').value || null;

  if (noteId) noteId = parseInt(noteId, 10);

  const passwordTags = ['notes'];
  if (category) passwordTags.push(category.toLowerCase());

  if (noteId) {
    // Update existing linked note content & merge password entry tags
    try {
      const notesRes = await fetch(`${API_BASE}/api/notes`);
      if (notesRes.ok) {
        const allNotes = await notesRes.json();
        const linkedNote = allNotes.find(n => n.id === noteId);
        if (linkedNote) {
          const currentTags = linkedNote.tags || [];
          const mergedTags = Array.from(new Set([...currentTags, ...passwordTags]));
          await fetch(`${API_BASE}/api/notes/${noteId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title: linkedNote.title,
              content: quickNote || linkedNote.content,
              tags: mergedTags,
              is_hidden: linkedNote.is_hidden !== false
            })
          });
        }
      }
    } catch (err) {
      console.error('Failed to update linked note:', err);
    }
  } else if (quickNote) {
    // Create a new note and link it with inherited password entry tags
    try {
      const noteTitle = `Note: ${domain} (${username})`;
      const noteRes = await fetch(`${API_BASE}/api/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: noteTitle, content: quickNote, tags: passwordTags, is_hidden: true })
      });
      if (noteRes.ok) {
        const allNotesRes = await fetch(`${API_BASE}/api/notes`);
        if (allNotesRes.ok) {
          const allNotes = await allNotesRes.json();
          const match = allNotes.find(n => n.title === noteTitle);
          if (match) noteId = match.id;
        }
      }
    } catch (err) {
      console.error('Failed to create quick note:', err);
    }
  }

  const method = id ? 'PUT' : 'POST';
  const url = id ? `${API_BASE}/api/passwords/${id}` : `${API_BASE}/api/passwords`;

  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ domain, username, password, category, note_id: noteId || null })
  });

  if (res.ok) {
    closeModal('modal-password');
    loadVaultData();
    showToast(id ? 'Password entry updated!' : 'Password saved to vault!');
  } else {
    const errData = await res.json().catch(() => ({}));
    showToast(errData.detail || 'Failed to save password', 'error');
  }
}

// SECURE NOTES VIEW (MATCHING IMAGE 1)
let cachedNotes = [];
let currentNoteTagFilter = 'All';

// SECURE NOTES VIEW (WITH TAG CRUD & HIDE/REVEAL TOGGLING)
async function loadNotesData() {
  try {
    const res = await fetch(`${API_BASE}/api/notes`);
    cachedNotes = res.ok ? await res.json() : [];
    renderNotesGrid(cachedNotes);
  } catch (err) {
    console.error('Failed to load notes:', err);
  }
}

function filterNotesTag(tagName, btnElement) {
  document.querySelectorAll('#notes-tag-pills-bar .cat-pill').forEach(p => p.classList.remove('active'));
  if (btnElement) btnElement.classList.add('active');
  currentNoteTagFilter = tagName;
  renderNotesGrid(cachedNotes);
}

function renderNotesGrid(notes) {
  document.getElementById('notes-subtitle-count').innerText = `${notes.length} End-to-end encrypted entries`;

  // Collect all unique tags across notes for the tag pills bar
  const allTags = new Set();
  notes.forEach(n => {
    (n.tags || []).forEach(t => allTags.add(t.toUpperCase()));
  });

  // Render Tag Pills Bar
  const tagPillsBar = document.getElementById('notes-tag-pills-bar');
  if (tagPillsBar) {
    let pillsHtml = `<button class="cat-pill ${currentNoteTagFilter === 'All' ? 'active' : ''}" onclick="filterNotesTag('All', this)">All</button>`;
    allTags.forEach(tag => {
      const activeClass = currentNoteTagFilter === tag ? 'active' : '';
      pillsHtml += `<button class="cat-pill ${activeClass}" onclick="filterNotesTag('${tag}', this)">${tag}</button>`;
    });
    tagPillsBar.innerHTML = pillsHtml;
  }

  // Filter notes by current tag filter
  const filteredNotes = notes.filter(n => {
    if (currentNoteTagFilter === 'All') return true;
    return (n.tags || []).map(t => t.toUpperCase()).includes(currentNoteTagFilter);
  });

  const grid = document.getElementById('notes-grid');
  grid.innerHTML = '';

  const tagColors = ['border-danger', 'border-accent', 'border-warn', 'border-muted'];

  filteredNotes.forEach((note, idx) => {
    const noteCard = document.createElement('div');
    const borderClass = tagColors[idx % tagColors.length];
    noteCard.className = `note-card ${borderClass}`;

    const tagsArr = (note.tags && note.tags.length) ? note.tags : ['PERSONAL'];
    const tagsHtml = tagsArr.map(t => `<span class="badge-tag tag-${t.toLowerCase()}" onclick="event.stopPropagation(); filterNotesTag('${t.toUpperCase()}', null)" title="Filter by tag ${t}">${t.toUpperCase()}</span>`).join(' ');
    const safeContent = note.content.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n');
    const safeTags = tagsArr.join(', ').replace(/'/g, "\\'");
    const isHidden = note.is_hidden !== false;

    noteCard.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div class="note-tags-row">${tagsHtml}</div>
        <i class="fa-solid fa-thumbtack text-dim" style="font-size: 12px;"></i>
      </div>
      <div class="note-card-title">${note.title}</div>
      <div class="note-masked-box" id="note-content-box-${note.id}">
        ${isHidden ? '\u2022\u2022\u2022\u2022\u2022 ENCRYPTED_AES_256' : safeContent.replace(/\\n/g, '<br>')}
      </div>
      <div class="note-card-footer">
        <span>Updated recently</span>
        <div>
          <button class="btn-icon" onclick="event.stopPropagation(); toggleNoteContentReveal(${note.id})" title="${isHidden ? 'Reveal Content' : 'Mask Content'}">
            <i class="fa-solid ${isHidden ? 'fa-eye' : 'fa-eye-slash'}" id="note-eye-icon-${note.id}"></i>
          </button>
          <button class="btn-icon" onclick="event.stopPropagation(); openEditNoteModalById(${note.id})" title="Edit Note"><i class="fa-solid fa-pen"></i></button>
          <button class="btn-icon" onclick="event.stopPropagation(); copyToClipboard('${safeContent}', 'Note copied!')" title="Copy Content"><i class="fa-regular fa-copy"></i></button>
          <button class="btn-icon text-danger" onclick="event.stopPropagation(); deleteNote(${note.id})" title="Delete Note"><i class="fa-regular fa-trash-can"></i></button>
        </div>
      </div>`;

    grid.appendChild(noteCard);
  });

  // Add Note Card Tile
  const addCard = document.createElement('div');
  addCard.className = 'add-entry-card';
  addCard.onclick = openAddNoteModal;
  addCard.innerHTML = `
    <i class="fa-solid fa-plus" style="font-size: 24px;"></i>
    <span style="font-size: 13px; font-weight: 600;">Add new note</span>`;
  grid.appendChild(addCard);
}

function toggleNoteContentReveal(noteId) {
  const note = cachedNotes.find(n => n.id === noteId);
  if (!note) return;

  const box = document.getElementById(`note-content-box-${noteId}`);
  const icon = document.getElementById(`note-eye-icon-${noteId}`);

  if (box) {
    const isCurrentlyMasked = box.innerText.includes('ENCRYPTED_AES_256');
    if (isCurrentlyMasked) {
      box.innerHTML = note.content.replace(/\n/g, '<br>');
      if (icon) icon.className = 'fa-solid fa-eye-slash';
    } else {
      box.innerText = '\u2022\u2022\u2022\u2022\u2022 ENCRYPTED_AES_256';
      if (icon) icon.className = 'fa-solid fa-eye';
    }
  }
}

function openEditNoteModal(id, title, content, tags, isHidden = true) {
  document.getElementById('modal-note-title').innerText = 'Edit Secure Note';
  document.getElementById('modal-note-id').value = id;
  document.getElementById('modal-note-input-title').value = title;
  document.getElementById('modal-note-input-content').value = content.replace(/\\n/g, '\n');
  document.getElementById('modal-note-input-tags').value = tags;
  document.getElementById('modal-note-input-hidden').checked = isHidden !== false;
  document.getElementById('modal-note').classList.add('active');
}

function openAddNoteModal() {
  document.getElementById('modal-note-title').innerText = 'New Secure Note';
  document.getElementById('modal-note-id').value = '';
  const linkedInput = document.getElementById('modal-note-linked-password-id');
  if (linkedInput) linkedInput.value = '';
  document.getElementById('modal-note-input-title').value = '';
  document.getElementById('modal-note-input-content').value = '';
  document.getElementById('modal-note-input-tags').value = '';
  document.getElementById('modal-note-input-hidden').checked = true;
  document.getElementById('modal-note').classList.add('active');
}

async function handleSaveNoteSubmit(e) {
  e.preventDefault();
  const id = document.getElementById('modal-note-id').value;
  const title = document.getElementById('modal-note-input-title').value.trim();
  const content = document.getElementById('modal-note-input-content').value;
  const tagsRaw = document.getElementById('modal-note-input-tags').value;
  const tags = tagsRaw.split(',').map(t => t.trim()).filter(Boolean);
  const is_hidden = document.getElementById('modal-note-input-hidden').checked;

  const method = id ? 'PUT' : 'POST';
  const url = id ? `${API_BASE}/api/notes/${id}` : `${API_BASE}/api/notes`;

  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, content, tags, is_hidden })
  });

  if (res.ok) {
    const data = await res.json().catch(() => ({}));
    const newNoteId = data.id;
    const linkedPwId = document.getElementById('modal-note-linked-password-id')?.value;

    if (linkedPwId && newNoteId) {
      const pwItem = cachedPasswords.find(p => p.id === parseInt(linkedPwId));
      if (pwItem) {
        await fetch(`${API_BASE}/api/passwords/${linkedPwId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            domain: pwItem.domain,
            username: pwItem.username,
            password: pwItem.password,
            note_id: newNoteId,
            category: pwItem.category || ''
          })
        });
      }
      document.getElementById('modal-note-linked-password-id').value = '';
    }

    closeModal('modal-note');
    loadNotesData();
    loadVaultData();
    showToast(id ? 'Note updated!' : 'Secure Note Saved!');
  } else {
    const err = await res.json().catch(() => ({}));
    showToast(err.detail || 'Failed to save note', 'error');
  }
}

async function deleteNote(id) {
  if (!confirm('Permanently delete this note?')) return;
  try {
    const res = await fetch(`${API_BASE}/api/notes/${id}`, { method: 'DELETE' });
    if (res.ok) {
      await loadNotesData();
      showToast('Note deleted successfully!');
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || 'Failed to delete note', 'error');
    }
  } catch (err) {
    console.error('Failed to delete note:', err);
    showToast('Failed to delete note', 'error');
  }
}

// VAULT HEALTH AUDIT VIEW (MATCHING IMAGE 3)
async function loadHealthData() {
  try {
    const res = await fetch(`${API_BASE}/api/passwords`);
    const passwords = res.ok ? await res.json() : [];

    const weak = passwords.filter(p => (p.strength_score || 1.0) < 0.5);
    const pwCounts = {};
    passwords.forEach(p => pwCounts[p.password] = (pwCounts[p.password] || 0) + 1);
    const reused = passwords.filter(p => pwCounts[p.password] > 1);

    const now = new Date();
    const expired = passwords.filter(p => {
      const created = p.created_at ? new Date(p.created_at) : new Date();
      const ttlDays = p.ttl_days || 365;
      const ageDays = Math.floor((now - created) / (1000 * 60 * 60 * 24));
      return ageDays >= ttlDays;
    });

    const total = passwords.length;
    const avgScore = total ? Math.round((passwords.reduce((acc, curr) => acc + (curr.strength_score || 1.0), 0) / total) * 100) : 100;

    document.getElementById('health-score-pct').innerText = `${avgScore}%`;
    document.getElementById('health-score-label').innerText = avgScore >= 80 ? 'Excellent' : (avgScore >= 50 ? 'Fair' : 'Critical');
    document.getElementById('health-summary-text').innerText = `Security Audit complete. ${weak.length + reused.length + expired.length} vulnerabilities found.`;

    document.getElementById('health-stat-total').innerText = total;
    document.getElementById('health-stat-weak').innerText = weak.length;
    document.getElementById('health-stat-reused').innerText = reused.length;
    document.getElementById('health-stat-expired').innerText = expired.length;

    // Render Reused List
    const reusedContainer = document.getElementById('health-reused-list');
    reusedContainer.innerHTML = reused.map(r => `
      <div class="account-row mb-2">
        <div style="flex:1;">
          <div class="font-semibold">${r.domain}</div>
          <div class="subtitle-text">${r.username}</div>
        </div>
        <span class="text-warn font-semibold">0${pwCounts[r.password]}</span>
        <button class="btn-outline text-accent" style="padding: 4px 10px; font-size: 11px;" onclick="openEditPasswordModalById(${r.id})">Update</button>
      </div>`).join('') || '<p class="subtitle-text">No reused passwords detected.</p>';

    // Render Weak List
    const weakContainer = document.getElementById('health-weak-list');
    weakContainer.innerHTML = weak.map(w => `
      <div class="account-row mb-2">
        <span style="color: var(--danger-color); font-size: 18px;">•</span>
        <div style="flex:1;">
          <div class="font-semibold">${w.domain}</div>
          <div class="subtitle-text">${w.username}</div>
        </div>
        <button class="btn-primary" style="padding: 4px 12px; font-size: 11px;" onclick="openEditPasswordModalById(${w.id})">Fix Now</button>
      </div>`).join('') || '<p class="subtitle-text text-accent"><i class="fa-solid fa-circle-check"></i> Great job! No weak passwords.</p>';
  } catch (err) {
    console.error('Failed to load health data:', err);
  }
}

// GENERATOR VIEW (MATCHING IMAGE 5)
function generateStandardPassword() {
  const upper = document.getElementById('gen-upper').checked;
  const lower = true; // Always include lowercase
  const numbers = document.getElementById('gen-numbers').checked;
  const symbols = document.getElementById('gen-symbols').checked;
  const length = parseInt(document.getElementById('gen-length').value, 10);

  let chars = 'abcdefghijklmnopqrstuvwxyz';
  if (upper) chars += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  if (numbers) chars += '0123456789';
  if (symbols) chars += '!@#$%^&*()_+-=[]{}|;:,.<>?';

  let pwd = '';
  for (let i = 0; i < length; i++) {
    pwd += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  document.getElementById('gen-output-text').innerText = pwd;
}

async function generateSmartPassword() {
  try {
    const res = await fetch(`${API_BASE}/api/generate`);
    if (res.ok) {
      const data = await res.json();
      document.getElementById('gen-output-text').innerText = data.generated_password;
      showToast(`Smart ML Generated! Style Score: ${data.score.toFixed(2)}`);
    } else {
      generateStandardPassword();
    }
  } catch (err) {
    generateStandardPassword();
  }
}

function copyGeneratedPassword() {
  const pwd = document.getElementById('gen-output-text').innerText;
  if (!pwd) return;
  copyToClipboard(pwd, 'Generated password copied!');
}

function fillModalGeneratedPassword() {
  const pwd = document.getElementById('gen-output-text').innerText;
  if (pwd) {
    document.getElementById('modal-pw-password').value = pwd;
  }
}

// ML SETTINGS (NEURAL CONTEXT)
async function loadMlSettings() {
  try {
    const res = await fetch(`${API_BASE}/api/settings`);
    if (res.ok) {
      const s = await res.json();
      document.getElementById('neural-input-name').value = s.user_name || '';
      document.getElementById('neural-input-words').value = (s.familiar_words || []).join(', ');
      document.getElementById('ml-input-name').value = s.user_name || '';
      document.getElementById('ml-input-words').value = (s.familiar_words || []).join(', ');
    }
  } catch (err) {
    console.error('Failed to load ML settings:', err);
  }
}

async function syncMlNeuralContext() {
  const name = document.getElementById('neural-input-name').value;
  const words = document.getElementById('neural-input-words').value;
  const familiarWords = words.split(',').map(w => w.trim()).filter(Boolean);

  await fetch(`${API_BASE}/api/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_name: name, familiar_words: familiarWords })
  });
  showToast('Neural Context Updated');
}

// SETTINGS VIEW (MATCHING IMAGE 2)
async function loadSettingsData() {
  try {
    const sRes = await fetch(`${API_BASE}/api/settings`);
    if (sRes.ok) {
      const s = await sRes.json();
      document.getElementById('setting-autolock-slider').value = s.auto_lock_minutes || 15;
      document.getElementById('setting-autolock-badge').innerText = `${s.auto_lock_minutes || 15} mins`;
      document.getElementById('setting-hotkey').value = s.hotkey || 'ctrl+shift+l';
    }

    if (ipcRenderer) {
      const openAtLogin = await ipcRenderer.invoke('get-startup-setting');
      const startupToggle = document.getElementById('setting-launch-startup');
      if (startupToggle) startupToggle.checked = Boolean(openAtLogin);
    }

    initSliderFills();
    await loadSettingsTags();
  } catch (err) {
    console.error('Failed to load settings:', err);
  }
}

async function loadSettingsTags() {
  const container = document.getElementById('settings-tags-list');
  if (!container) return;

  try {
    const res = await fetch(`${API_BASE}/api/tags`);
    const tags = res.ok ? await res.json() : [];

    if (tags.length === 0) {
      container.innerHTML = '<span class="subtitle-text">No tags created yet.</span>';
      return;
    }

    container.innerHTML = tags.map(tag => {
      const safeTag = tag.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
      return `
        <div class="settings-tag-pill">
          <span class="settings-tag-name">${tag}</span>
          <button class="settings-tag-btn" onclick="handleRenameTag('${safeTag}')" title="Rename Tag"><i class="fa-solid fa-pen"></i></button>
          <button class="settings-tag-btn text-danger" onclick="handleDeleteTag('${safeTag}')" title="Delete Tag"><i class="fa-solid fa-xmark"></i></button>
        </div>`;
    }).join('');
  } catch (err) {
    console.error('Failed to load settings tags:', err);
  }
}

async function handleCreateTagSubmit() {
  const input = document.getElementById('setting-new-tag-input');
  if (!input) return;
  const name = input.value.trim();
  if (!name) return;

  try {
    const res = await fetch(`${API_BASE}/api/tags`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    if (res.ok) {
      input.value = '';
      showToast(`Tag '${name}' created!`);
      loadSettingsTags();
      loadVaultData();
      loadNotesData();
    }
  } catch (err) {
    showToast('Failed to create tag', 'error');
  }
}

async function handleRenameTag(oldName) {
  const newName = prompt(`Rename tag '${oldName}' to:`, oldName);
  if (!newName || newName.trim() === '' || newName.trim() === oldName) return;

  try {
    const res = await fetch(`${API_BASE}/api/tags/${encodeURIComponent(oldName)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_name: newName.trim() })
    });
    if (res.ok) {
      showToast(`Tag renamed to '${newName.trim()}'`);
      loadSettingsTags();
      loadVaultData();
      loadNotesData();
    }
  } catch (err) {
    showToast('Failed to rename tag', 'error');
  }
}

async function handleDeleteTag(tagName) {
  if (!confirm(`Delete tag '${tagName}'? This will remove it from all entries.`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/tags/${encodeURIComponent(tagName)}`, {
      method: 'DELETE'
    });
    if (res.ok) {
      showToast(`Tag '${tagName}' deleted`);
      loadSettingsTags();
      loadVaultData();
      loadNotesData();
    }
  } catch (err) {
    showToast('Failed to delete tag', 'error');
  }
}

async function toggleLaunchAtStartup(checkbox) {
  if (ipcRenderer) {
    try {
      const isEnabled = await ipcRenderer.invoke('set-startup-setting', checkbox.checked);
      checkbox.checked = Boolean(isEnabled);
      showToast(isEnabled ? 'Launch at startup enabled' : 'Launch at startup disabled');
    } catch (err) {
      console.error('Failed to update startup setting:', err);
      showToast('Failed to update startup setting', 'warn');
    }
  } else {
    showToast('Startup setting active in Desktop App');
  }
}

async function exportVaultCSV() {
  if (!currentMasterPassword) return;
  const res = await fetch(`${API_BASE}/api/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ master_password: currentMasterPassword })
  });

  if (res.ok) {
    const data = await res.json();
    const blob = new Blob([data.csv_content], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'valtr_vault_export.csv';
    a.click();
    showToast('Vault exported to CSV');
  }
}

// ── GLOBAL HOTKEY & RECORDING ──
if (ipcRenderer) {
  ipcRenderer.on('global-hotkey-pressed', () => {
    handleHotkeyTrigger();
  });
}

async function handleHotkeyTrigger() {
  switchTab('vault');
  const searchInput = document.getElementById('global-header-search');
  if (searchInput) searchInput.focus();
  
  try {
    const res = await fetch(`${API_BASE}/api/popup/trigger`);
    if (res.ok) {
      const data = await res.json();
      let filterText = '';
      if (data.browser_url) {
        try {
          const urlObj = new URL(data.browser_url);
          filterText = urlObj.hostname.replace(/^www\./, '');
        } catch (e) {
          filterText = data.browser_url;
        }
      } else if (data.typed_user || data.typed_pass) {
        filterText = data.typed_user || data.typed_pass;
      }
      
      if (filterText && searchInput) {
        searchInput.value = filterText;
        handleGlobalHeaderSearch();
        showToast(`AutoFill search active for '${filterText}'`);
      }
    }
  } catch (err) {
    console.error('Failed to query hotkey trigger:', err);
  }
}

async function autoTypeAccount(username, password) {
  try {
    const res = await fetch(`${API_BASE}/api/popup/autotype`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    if (res.ok) {
      showToast(`Auto-typing credentials for ${username}...`);
    } else {
      showToast('AutoType request failed', 'warn');
    }
  } catch (err) {
    showToast('AutoType request failed', 'warn');
  }
}

let isRecordingHotkey = false;

async function startHotkeyRecording() {
  const input = document.getElementById('setting-hotkey');
  const btn = document.getElementById('btn-record-hotkey');
  if (!input || isRecordingHotkey) return;

  isRecordingHotkey = true;
  input.classList.add('recording');
  input.value = 'Press key combination...';
  if (btn) btn.innerHTML = '<i class="fa-solid fa-circle-dot text-danger"></i> Recording...';

  // Unregister Electron global shortcuts while recording so modifier key events aren't swallowed
  if (ipcRenderer) {
    try {
      await ipcRenderer.invoke('set-global-hotkey', '__unregister_all__');
    } catch (e) {}
  }

  const MODIFIER_CODES = {
    'ControlLeft': 'ctrl', 'ControlRight': 'ctrl',
    'ShiftLeft': 'shift', 'ShiftRight': 'shift',
    'AltLeft': 'alt', 'AltRight': 'alt',
    'MetaLeft': 'win', 'MetaRight': 'win'
  };

  function codeToName(code) {
    if (MODIFIER_CODES[code]) return MODIFIER_CODES[code];
    if (code.startsWith('Key')) return code.slice(3).toLowerCase();
    if (code.startsWith('Digit')) return code.slice(5);
    if (code.startsWith('Numpad')) return code.toLowerCase();
    if (/^F\d+$/.test(code)) return code;
    const specialMap = {
      'Space': 'space', 'Tab': 'tab', 'Enter': 'enter',
      'Backspace': 'backspace', 'Delete': 'delete', 'Escape': 'esc',
      'ArrowUp': 'up', 'ArrowDown': 'down', 'ArrowLeft': 'left', 'ArrowRight': 'right',
      'BracketLeft': '[', 'BracketRight': ']', 'Backslash': '\\',
      'Semicolon': ';', 'Quote': "'", 'Comma': ',', 'Period': '.',
      'Slash': '/', 'Minus': '-', 'Equal': '=', 'Backquote': '`'
    };
    if (code in specialMap) return specialMap[code];
    return code.toLowerCase();
  }

  function stopRecording(combo) {
    window.removeEventListener('keydown', onKeyDown, true);
    input.classList.remove('recording');
    isRecordingHotkey = false;
    if (btn) btn.innerHTML = '<i class="fa-solid fa-keyboard"></i> Record Hotkey';

    if (combo) {
      input.value = combo;
      saveNewHotkey(combo);
    } else {
      loadSettingsData();
    }
  }

  function onKeyDown(e) {
    // If key event is targeted at another input field, cancel hotkey recording immediately
    if (e.target && e.target.id !== 'setting-hotkey' && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {
      stopRecording(null);
      return;
    }

    e.preventDefault();
    e.stopPropagation();

    // Cancel recording on ESC
    if (e.code === 'Escape') {
      stopRecording(null);
      return;
    }

    // Detect currently pressed modifiers
    const mods = [];
    if (e.ctrlKey) mods.push('ctrl');
    if (e.altKey) mods.push('alt');
    if (e.shiftKey) mods.push('shift');
    if (e.metaKey) mods.push('win');

    const keyName = codeToName(e.code);
    const isModifier = MODIFIER_CODES[e.code] !== undefined;

    if (isModifier) {
      // Live preview of held modifiers
      input.value = mods.length ? mods.join('+') + '+...' : 'Press key combination...';
      return;
    }

    // A non-modifier key was pressed! Combine modifiers + key and finish immediately
    if (keyName) {
      const parts = [...mods];
      if (!parts.includes(keyName)) {
        parts.push(keyName);
      }
      const combo = parts.join('+');
      stopRecording(combo);
    }
  }

  window.addEventListener('keydown', onKeyDown, true);
}

async function saveNewHotkey(newHotkey) {
  try {
    const sRes = await fetch(`${API_BASE}/api/settings`);
    let currentSettings = sRes.ok ? await sRes.json() : {};
    currentSettings.hotkey = newHotkey;

    await fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentSettings)
    });

    if (ipcRenderer) {
      await ipcRenderer.invoke('set-global-hotkey', newHotkey);
    }

    showToast(`Global hotkey saved: ${newHotkey}`);
  } catch (err) {
    console.error('Failed to save hotkey:', err);
    showToast('Failed to save hotkey', 'warn');
  }
}

// ── EXPIRY NOTIFICATIONS & DROPDOWN ──
function toggleNotificationDropdown() {
  const dropdown = document.getElementById('notification-dropdown');
  if (dropdown) dropdown.classList.toggle('active');
}

function updateExpiryNotifications(passwords) {
  const now = new Date();
  const expiringEntries = [];

  passwords.forEach(p => {
    const createdDate = p.created_at ? new Date(p.created_at) : new Date();
    const maxTtl = p.ttl_days || 365;
    const ageDays = Math.floor((now - createdDate) / (1000 * 60 * 60 * 24));
    const remainingTtl = maxTtl - ageDays;

    if (remainingTtl <= 30) {
      expiringEntries.push({
        id: p.id,
        domain: p.domain,
        username: p.username,
        remainingTtl: remainingTtl,
        maxTtl: maxTtl,
        isExpired: remainingTtl <= 0
      });
    }
  });

  const badgeEl = document.getElementById('bell-badge-count');
  const dropdownList = document.getElementById('notification-dropdown-list');

  if (badgeEl) {
    if (expiringEntries.length > 0) {
      badgeEl.innerText = expiringEntries.length;
      badgeEl.style.display = 'inline-flex';
    } else {
      badgeEl.style.display = 'none';
    }
  }

  if (dropdownList) {
    if (expiringEntries.length === 0) {
      dropdownList.innerHTML = `
        <div class="notification-item-empty">
          <i class="fa-solid fa-circle-check text-accent" style="font-size: 20px;"></i>
          <span>All passwords have healthy ML TTL lifetime.</span>
        </div>`;
    } else {
      dropdownList.innerHTML = expiringEntries.map(e => {
        const cardClass = e.isExpired ? 'danger' : 'warn';
        const msgText = e.isExpired ? 'Expired!' : `Expires in ${e.remainingTtl}d`;
        const iconClass = e.isExpired ? 'fa-triangle-exclamation text-danger' : 'fa-hourglass-half text-warn';
        return `
          <div class="notification-item-card ${cardClass}">
            <div class="notification-item-info">
              <span class="notification-item-title"><i class="fa-solid ${iconClass}"></i> ${e.domain}</span>
              <span class="notification-item-sub">${e.username} • ${msgText}</span>
            </div>
            <button class="btn-autofill-sm" onclick="event.stopPropagation(); toggleNotificationDropdown(); openEditPasswordModalById(${e.id})">Rotate</button>
          </div>`;
      }).join('');
    }
  }

  // Toast alert if expiring entries exist and haven't notified in this session
  if (expiringEntries.length > 0 && !window._hasNotifiedExpiry) {
    window._hasNotifiedExpiry = true;
    const expiredCount = expiringEntries.filter(e => e.isExpired).length;
    if (expiredCount > 0) {
      showToast(`⚠️ ${expiredCount} password${expiredCount > 1 ? 's have' : ' has'} expired! Check Notifications.`, 'warn');
    } else {
      showToast(`⚠️ ${expiringEntries.length} password${expiringEntries.length > 1 ? 's are' : ' is'} expiring soon based on ML TTL!`, 'warn');
    }
  }
}

// ── SLIDER FILL CALCULATOR ──
function updateSliderFill(input) {
  if (!input) return;
  const min = parseFloat(input.min) || 0;
  const max = parseFloat(input.max) || 100;
  const val = parseFloat(input.value) || 0;
  const pct = ((val - min) / (max - min)) * 100;
  input.style.background = `linear-gradient(to right, var(--accent-color) ${pct}%, var(--surface-color) ${pct}%)`;
}

// ── SECURITY LOGS & AUDIT VIEW ──
let cachedLogs = [];
let currentLogFilter = 'All';

async function loadLogsData() {
  try {
    const res = await fetch(`${API_BASE}/api/logs`);
    cachedLogs = res.ok ? await res.json() : [];
    renderLogsList(cachedLogs);
  } catch (err) {
    console.error('Failed to load security logs:', err);
  }
}

function renderLogsList(logs) {
  const tbody = document.getElementById('logs-table-body');
  if (!tbody) return;

  let filtered = logs.filter(l => {
    if (currentLogFilter === 'All') return true;
    return l.severity === currentLogFilter;
  });

  const countEl = document.getElementById('logs-subtitle-count');
  if (countEl) {
    countEl.innerText = `${logs.length} security audit events recorded.`;
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; padding: 36px; color: var(--text-dim);">
          <i class="fa-solid fa-clipboard-check mb-2" style="font-size: 28px; display: block;"></i>
          No security log events found matching '${currentLogFilter}'.
        </td>
      </tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(log => {
    const dt = log.timestamp ? new Date(log.timestamp).toLocaleString() : 'Just now';
    let sevBadge = '<span class="badge-ttl badge-ttl-ok"><i class="fa-solid fa-circle-info"></i> INFO</span>';
    if (log.severity === 'warn') {
      sevBadge = '<span class="badge-ttl badge-ttl-warn"><i class="fa-solid fa-triangle-exclamation"></i> WARN</span>';
    } else if (log.severity === 'danger') {
      sevBadge = '<span class="badge-ttl badge-ttl-danger"><i class="fa-solid fa-circle-xmark"></i> CRITICAL</span>';
    }

    return `
      <tr>
        <td style="font-size: 11.5px; color: var(--text-muted); font-family: monospace;">${dt}</td>
        <td><span class="badge-tag" style="font-size: 10px; font-weight: 700;">${log.event_type}</span></td>
        <td style="font-weight: 500;">${log.description}</td>
        <td>${sevBadge}</td>
        <td style="font-size: 11.5px; color: var(--text-muted); font-family: monospace;">${log.ip_address || '127.0.0.1'}</td>
      </tr>`;
  }).join('');
}

function filterLogsSeverity(severity, btnElement) {
  currentLogFilter = severity;
  if (btnElement && btnElement.parentElement) {
    btnElement.parentElement.querySelectorAll('.cat-pill').forEach(p => p.classList.remove('active'));
    btnElement.classList.add('active');
  }
  renderLogsList(cachedLogs);
}
