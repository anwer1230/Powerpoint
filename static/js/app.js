// ============== Globals ==============
let socket = null;
let globalDeferredPrompt = null;
let __lastClickedEl = null;

document.addEventListener('click', (e) => {
  const btn = e.target.closest('button, .btn, [role="button"], a');
  if (btn) __lastClickedEl = btn;
}, true);

// ============== Helpers ==============
async function postJSON(url, body) {
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(body || {})
    });
    const txt = await res.text();
    if (!txt || !txt.trim()) {
      return { success: false, message: `الخادم لم يُرجع بياناً (HTTP ${res.status})` };
    }
    try {
      return JSON.parse(txt);
    } catch (e) {
      return { success: false, message: `استجابة غير صالحة من الخادم (HTTP ${res.status})` };
    }
  } catch (e) {
    return { success: false, message: 'تعذر الاتصال بالخادم: ' + (e.message || e) };
  }
}

function showAlert(msg, type = 'info', anchorEl = null) {
  const target = anchorEl || __lastClickedEl;
  const colors = {
    success: { bg: '#198754', icon: '✓' },
    danger:  { bg: '#dc3545', icon: '✕' },
    warning: { bg: '#ffc107', icon: '⚠', color: '#000' },
    info:    { bg: '#0d6efd', icon: 'ℹ' }
  };
  const c = colors[type] || colors.info;
  const fg = c.color || '#fff';

  const toast = document.createElement('div');
  toast.className = 'icon-toast';
  toast.innerHTML = `<span class="it-ico">${c.icon}</span><span class="it-msg">${msg}</span>`;
  toast.style.cssText = `
    position:fixed;z-index:99999;
    background:${c.bg};color:${fg};
    padding:10px 14px;border-radius:12px;
    font-size:14px;font-weight:600;
    box-shadow:0 8px 24px rgba(0,0,0,.25);
    display:flex;align-items:center;gap:8px;
    max-width:320px;line-height:1.4;
    opacity:0;transform:scale(.85);
    transition:opacity .25s ease, transform .25s ease;
    pointer-events:auto;
  `;
  document.body.appendChild(toast);

  let top, left;
  if (target && target.getBoundingClientRect) {
    const r = target.getBoundingClientRect();
    const tr = toast.getBoundingClientRect();
    top  = r.top - tr.height - 10;
    left = r.left + (r.width / 2) - (tr.width / 2);
    if (top < 8) top = r.bottom + 10;
    if (left < 8) left = 8;
    const maxLeft = window.innerWidth - tr.width - 8;
    if (left > maxLeft) left = maxLeft;
  } else {
    top = 16;
    left = (window.innerWidth - toast.offsetWidth) / 2;
  }
  toast.style.top  = top  + 'px';
  toast.style.left = left + 'px';

  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'scale(1)';
  });

  toast.addEventListener('click', () => removeToast(toast));
  setTimeout(() => removeToast(toast), 4000);
}

function removeToast(t) {
  if (!t || !t.parentNode) return;
  t.style.opacity = '0';
  t.style.transform = 'scale(.85)';
  setTimeout(() => t.remove(), 250);
}

window.showNotification = function(msg, type) {
  const map = { error: 'danger', success: 'success', warning: 'warning', info: 'info' };
  showAlert(msg, map[type] || 'info');
};

function appendLog(message) {
  const log = document.getElementById('logContainer') || document.getElementById('logs');
  if (!log) return;
  const t = new Date().toLocaleTimeString('ar-SA');
  log.insertAdjacentHTML('beforeend', `<div class="log-line"><small class="text-muted">[${t}]</small> ${message}</div>`);
  log.scrollTop = log.scrollHeight;
}

function setLoading(btn, loading, originalText) {
  if (!btn) return;
  if (loading) {
    btn.dataset.orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>جارِ المعالجة...';
  } else {
    btn.disabled = false;
    btn.innerHTML = btn.dataset.orig || originalText || btn.innerHTML;
  }
}

// ============== Login Form ==============
document.addEventListener('DOMContentLoaded', () => {
  const loginForm = document.getElementById('loginForm');
  const verifyForm = document.getElementById('verifyForm');
  const passwordForm = document.getElementById('passwordForm');

  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const phone = document.getElementById('phone').value.trim();
      const password = (document.getElementById('password') || {}).value || '';
      if (!phone) { showAlert('يرجى إدخال رقم الهاتف', 'warning'); return; }
      const btn = document.getElementById('loginBtn');
      setLoading(btn, true);
      try {
        const r = await postJSON('/api/save_login', { phone, password });
        showAlert(r.message || '', r.success ? 'success' : 'danger');
        if (r.success) {
          if (r.code_required) {
            verifyForm.style.display = 'block';
            document.getElementById('verificationCode').focus();
          } else {
            // already authenticated
            updateLoggedInUI();
          }
        }
      } catch (err) {
        showAlert('خطأ في الاتصال: ' + err.message, 'danger');
      } finally {
        setLoading(btn, false, '<i class="fas fa-sign-in-alt me-2"></i>تسجيل الدخول');
      }
    });
  }

  if (verifyForm) {
    verifyForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const code = document.getElementById('verificationCode').value.trim();
      if (!code) { showAlert('يرجى إدخال كود التحقق', 'warning'); return; }
      const btn = verifyForm.querySelector('button[type="submit"]');
      setLoading(btn, true);
      try {
        const r = await postJSON('/api/verify_code', { code });
        showAlert(r.message || '', r.success ? 'success' : 'danger');
        if (r.success) {
          if (r.password_required) {
            verifyForm.style.display = 'none';
            passwordForm.style.display = 'block';
            document.getElementById('twoFactorPassword').focus();
          } else {
            verifyForm.style.display = 'none';
            updateLoggedInUI();
            const activeTab = document.querySelector('.user-tab.active');
            const def = (activeTab && activeTab.dataset.defaultName) || '';
            const color = activeTab ? activeTab.style.color : '';
            updateCurrentUserDisplay(def, r.account_name, color);
            refreshAccountInfo();
          }
        }
      } catch (err) {
        showAlert('خطأ: ' + err.message, 'danger');
      } finally {
        setLoading(btn, false, '<i class="fas fa-check me-2"></i>تأكيد الكود');
      }
    });
  }

  if (passwordForm) {
    passwordForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const password = document.getElementById('twoFactorPassword').value;
      if (!password) { showAlert('يرجى إدخال كلمة المرور', 'warning'); return; }
      const btn = passwordForm.querySelector('button[type="submit"]');
      setLoading(btn, true);
      try {
        const r = await postJSON('/api/verify_code', { password });
        showAlert(r.message || '', r.success ? 'success' : 'danger');
        if (r.success) {
          passwordForm.style.display = 'none';
          updateLoggedInUI();
          const activeTab = document.querySelector('.user-tab.active');
          const def = (activeTab && activeTab.dataset.defaultName) || '';
          const color = activeTab ? activeTab.style.color : '';
          updateCurrentUserDisplay(def, r.account_name, color);
          refreshAccountInfo();
        }
      } catch (err) {
        showAlert('خطأ: ' + err.message, 'danger');
      } finally {
        setLoading(btn, false, '<i class="fas fa-unlock me-2"></i>تأكيد كلمة المرور');
      }
    });
  }

  // Resend code
  const resendBtn = document.getElementById('resendCodeBtn');
  const resendSmsBtn = document.getElementById('resendSmsBtn');
  async function doResend(forceSms) {
    const r = await postJSON('/api/resend_code', { force_sms: forceSms });
    showAlert(r.message || '', r.success ? 'success' : 'danger');
  }
  if (resendBtn) resendBtn.addEventListener('click', () => doResend(false));
  if (resendSmsBtn) resendSmsBtn.addEventListener('click', () => doResend(true));

  // Logout
  const logoutBtn = document.getElementById('logoutButton');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      if (!confirm('هل أنت متأكد من تسجيل الخروج؟')) return;
      const r = await postJSON('/api/user_logout', {});
      showAlert(r.message || '', r.success ? 'success' : 'danger');
      if (r.success) setTimeout(() => location.reload(), 800);
    });
  }

  // Settings save
  const settingsForm = document.getElementById('settingsForm');
  if (settingsForm) {
    settingsForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const data = {
        message: (document.getElementById('message') || {}).value || '',
        groups: (document.getElementById('groups') || {}).value || '',
        interval_seconds: parseInt((document.getElementById('intervalSeconds') || {}).value || '3600'),
        watch_words: (document.getElementById('watchWords') || {}).value || '',
        send_type: (document.getElementById('sendType') || {}).value || 'manual',
        scheduled_time: (document.getElementById('scheduledTime') || {}).value || '',
        max_retries: parseInt((document.getElementById('maxRetries') || {}).value || '5'),
        auto_reconnect: (document.getElementById('autoReconnect') || {}).checked || false
      };
      const r = await postJSON('/api/save_settings', data);
      showAlert(r.message || '', r.success ? 'success' : 'danger');
    });
  }

  // User switching
  document.querySelectorAll('.user-tab').forEach(tab => {
    tab.addEventListener('click', async (ev) => {
      const newId = tab.dataset.userId;
      const defaultName = tab.dataset.defaultName || tab.querySelector('.user-tab-name')?.textContent || '';
      const wasActive = tab.classList.contains('active');
      __lastClickedEl = tab;
      if (wasActive) {
        showAlert(`أنت بالفعل على حساب: ${defaultName}`, 'info', tab);
        return;
      }
      const r = await postJSON('/api/switch_user', { user_id: newId });
      if (r.success) {
        document.querySelectorAll('.user-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const accountName = r.account_name;
        if (accountName) {
          showAlert(`تم الانتقال إلى: ${defaultName} (${accountName})`, 'success', tab);
        } else {
          showAlert(`تم الانتقال إلى: ${defaultName} — لم يسجل دخول بعد`, 'warning', tab);
        }
        updateCurrentUserDisplay(defaultName, accountName, tab.style.color);
        const tabNameEl = tab.querySelector('.user-tab-name');
        if (tabNameEl && accountName) tabNameEl.textContent = `${defaultName} · ${accountName}`;
      } else {
        showAlert(r.message || 'تعذر الانتقال', 'danger', tab);
      }
    });
  });

  // Initial state
  fetchLoginStatus();
  initSocket();
  initPWA();
  refreshAccountInfo();
});

function updateCurrentUserDisplay(predefinedName, accountName, color) {
  const cu = document.getElementById('currentUserNameDisplay');
  if (cu) {
    cu.textContent = predefinedName || '';
    if (color) cu.style.color = color;
  }
  const ca = document.getElementById('currentAccountNameDisplay');
  if (ca) {
    if (accountName) {
      ca.textContent = '👤 ' + accountName;
      ca.style.display = 'inline-block';
    } else {
      ca.textContent = '';
      ca.style.display = 'none';
    }
  }
  const activeTab = document.querySelector('.user-tab.active');
  if (activeTab) {
    const tabNameEl = activeTab.querySelector('.user-tab-name');
    const def = activeTab.dataset.defaultName || '';
    if (tabNameEl) {
      tabNameEl.textContent = accountName ? `${def} · ${accountName}` : def;
    }
  }
}

async function refreshAccountInfo() {
  try {
    const res = await fetch('/api/get_account_info', { credentials: 'same-origin' });
    const txt = await res.text();
    if (!txt) return;
    const r = JSON.parse(txt);
    if (r && r.success) {
      const activeTab = document.querySelector('.user-tab.active');
      const def = (activeTab && activeTab.dataset.defaultName) || r.predefined_name || '';
      const color = activeTab ? activeTab.style.color : '';
      updateCurrentUserDisplay(def, r.account_name, color);
    }
  } catch (e) {}
}

function updateLoggedInUI() {
  const sc = document.getElementById('sessionControls');
  const lbc = document.getElementById('loginButtonContainer');
  if (sc) sc.style.display = 'block';
  if (lbc) lbc.style.display = 'none';
  const status = document.getElementById('connectionStatus');
  if (status) { status.textContent = 'متصل'; status.className = 'badge bg-success'; }
}

async function fetchLoginStatus() {
  try {
    const r = await fetch('/api/get_login_status').then(x => x.json());
    if (r && r.success && r.logged_in) updateLoggedInUI();
  } catch (e) {}
}

// ============== Socket.IO ==============
function initSocket() {
  if (typeof io === 'undefined') return;
  socket = io({ transports: ['websocket', 'polling'] });
  socket.on('connect', () => appendLog('🔌 متصل بالسيرفر'));
  socket.on('disconnect', () => appendLog('⚠️ انقطع الاتصال'));
  socket.on('log_update', d => appendLog(d.message || ''));
  socket.on('connection_status', d => {
    const status = document.getElementById('connectionStatus');
    if (status) {
      const ok = d.status === 'connected';
      status.textContent = ok ? 'متصل' : 'غير متصل';
      status.className = 'badge ' + (ok ? 'bg-success' : 'bg-danger');
    }
  });
  socket.on('login_status', d => { if (d.logged_in) updateLoggedInUI(); });
  socket.on('stats_update', d => {
    const s = document.getElementById('sentCount');
    const e = document.getElementById('errorCount');
    if (s && d.sent !== undefined) s.textContent = d.sent;
    if (e && d.errors !== undefined) e.textContent = d.errors;
  });
}

// ============== PWA Install ==============
function initPWA() {
  const installBtn = document.getElementById('installAppBtn');
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    globalDeferredPrompt = e;
    if (installBtn) installBtn.style.display = 'inline-block';
  });
  if (installBtn) {
    installBtn.addEventListener('click', async () => {
      if (!globalDeferredPrompt) {
        showAlert('التثبيت غير متاح في هذا المتصفح. على iPhone: استخدم زر المشاركة ثم "إضافة إلى الشاشة الرئيسية"', 'info');
        return;
      }
      globalDeferredPrompt.prompt();
      const { outcome } = await globalDeferredPrompt.userChoice;
      if (outcome === 'accepted') {
        showAlert('✅ تم تثبيت التطبيق', 'success');
        installBtn.style.display = 'none';
      }
      globalDeferredPrompt = null;
    });
  }
  window.addEventListener('appinstalled', () => {
    showAlert('✅ تم تثبيت التطبيق بنجاح', 'success');
    if (installBtn) installBtn.style.display = 'none';
  });
}

function showUpdateNotification() {
  showAlert('🔄 يتوفر تحديث جديد، أعد تحميل الصفحة', 'info');
}
