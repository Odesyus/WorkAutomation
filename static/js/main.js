// ============ Tema Yönetimi ============
function setTheme(theme) {
    document.body.classList.remove('theme-modern', 'theme-corporate');
    document.body.classList.add('theme-' + theme);
    localStorage.setItem('theme', theme);
    const btn = document.getElementById('theme-toggle');
    if (btn) {
        btn.querySelector('i').className = theme === 'modern' ? 'fas fa-building' : 'fas fa-moon';
        btn.querySelector('span').textContent = theme === 'modern' ? 'Kurumsal Tema' : 'Modern Tema';
    }
}

function toggleTheme() {
    const current = localStorage.getItem('theme') || 'modern';
    setTheme(current === 'modern' ? 'corporate' : 'modern');
}

// ============ API Yardımcısı ============
async function apiCall(url, method = 'GET', data = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (data) options.body = JSON.stringify(data);
    try {
        const response = await fetch(url, options);
        const json = await response.json().catch(() => null);
        if (!json) return { success: false, error: `Sunucu hatası (HTTP ${response.status})` };
        return json;
    } catch (error) {
        console.error('API Hatası:', error);
        return { success: false, error: 'Sunucuya ulaşılamadı: ' + error.message };
    }
}

// ============ Bildirimler ============
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const icons = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i><span></span>`;
    toast.querySelector('span').textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, type === 'error' ? 6000 : 3500);
}

// ============ Buton yükleniyor durumu ============
function setLoading(button, loading, text = 'Yükleniyor...') {
    if (!button) return;
    if (loading) {
        if (!button.dataset.originalText) button.dataset.originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${text}`;
    } else {
        button.disabled = false;
        if (button.dataset.originalText) {
            button.innerHTML = button.dataset.originalText;
            delete button.dataset.originalText;
        }
    }
}

// HTML kaçış (sunucudan gelen metinleri güvenle basmak için)
function escapeHtml(str) {
    return String(str ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ============ Başlangıç ============
document.addEventListener('DOMContentLoaded', () => {
    setTheme(localStorage.getItem('theme') || 'modern');
    document.getElementById('theme-toggle')?.addEventListener('click', toggleTheme);

    // Mobil menü
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    document.getElementById('mobile-menu-btn')?.addEventListener('click', () => {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('show');
    });
    overlay?.addEventListener('click', () => {
        sidebar.classList.remove('open');
        overlay.classList.remove('show');
    });

    // Odaklanınca hata vurgusunu kaldır
    document.querySelectorAll('input').forEach(input =>
        input.addEventListener('focus', () => input.classList.remove('input-error')));
});


// ============ Sistem Güncelleme Yönetimi ============
async function checkSystemUpdates() {
    const btn = document.getElementById('btn-check-update');
    const icon = document.getElementById('update-icon');
    const label = document.getElementById('update-btn-label');

    if (btn) btn.disabled = true;
    if (icon) icon.classList.add('fa-spin');
    if (label) label.textContent = 'Denetleniyor...';

    try {
        const res = await apiCall('/api/system/check-update', 'POST');
        if (!res.success) {
            showToast(res.error || 'Güncellemeler denetlenemedi.', 'error');
            return;
        }

        const data = res.data;
        if (!data.has_update) {
            showToast(data.message || 'Sisteminiz en güncel sürümde.', 'success');
            return;
        }

        openUpdateModal(data);
    } catch (e) {
        showToast('Bağlantı hatası: ' + e.message, 'error');
    } finally {
        if (btn) btn.disabled = false;
        if (icon) icon.classList.remove('fa-spin');
        if (label) label.textContent = 'Güncellemeleri Denetle';
    }
}

function openUpdateModal(data) {
    const modal = document.getElementById('update-modal');
    const body = document.getElementById('update-modal-body');
    if (!modal || !body) return;

    const commitsHtml = (data.commits || []).map(c => `
        <li style="margin-bottom: 6px;">
            <code style="background: rgba(0,212,255,0.1); color: var(--primary); padding: 2px 5px; border-radius: 4px;">${escapeHtml(c.hash)}</code>
            <strong>${escapeHtml(c.title)}</strong>
            <span style="color: var(--text-muted); font-size: 0.78rem;">(${escapeHtml(c.date)})</span>
        </li>
    `).join('');

    body.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;">
            <span class="badge badge-primary" style="font-size: 0.88rem; padding: 4px 10px;">
                <i class="fas fa-code-branch"></i> ${data.commits_behind} Yeni Güncelleme
            </span>
            <span style="font-size: 0.82rem; color: var(--text-muted);">
                Mevcut: <code>${escapeHtml(data.local_hash)}</code> &rarr; Yeni: <code>${escapeHtml(data.remote_hash)}</code>
            </span>
        </div>
        <p style="font-size: 0.88rem; color: var(--text-muted); margin-bottom: 14px; line-height: 1.45;">
            GitHub üzerinden yeni bir sürüm yayınlandı. Güncelleme işlemi kodları çekecek ve gerekirse kütüphaneleri otomatik yenileyecektir.
        </p>
        <div style="background: rgba(0,0,0,0.25); border: 1px solid var(--surface-border); border-radius: 8px; padding: 12px; max-height: 150px; overflow-y: auto; margin-bottom: 20px;">
            <ul style="margin: 0; padding-left: 18px; font-size: 0.84rem;">
                ${commitsHtml || '<li>Yeni sürüm iyileştirmeleri ve hata düzeltmeleri.</li>'}
            </ul>
        </div>
        <div style="display: flex; gap: 10px;">
            <button type="button" class="btn btn-secondary" onclick="closeUpdateModal()" style="flex: 1; justify-content: center;">
                Daha Sonra
            </button>
            <button type="button" class="btn btn-primary" id="btn-apply-update" onclick="applySystemUpdate()" style="flex: 2; justify-content: center;">
                <i class="fas fa-download"></i> Şimdi Güncelle
            </button>
        </div>
    `;

    modal.style.display = 'flex';
}

function closeUpdateModal() {
    const modal = document.getElementById('update-modal');
    if (modal) modal.style.display = 'none';
}

async function applySystemUpdate() {
    const btn = document.getElementById('btn-apply-update');
    const body = document.getElementById('update-modal-body');

    if (btn) setLoading(btn, true, 'Güncelleniyor...');

    if (body) {
        body.innerHTML = `
            <div style="text-align: center; padding: 24px 10px;">
                <i class="fas fa-circle-notch fa-spin" style="font-size: 2.4rem; color: var(--primary); margin-bottom: 16px;"></i>
                <h4 style="margin: 0 0 8px 0;">Güncelleme Uygulanıyor</h4>
                <p style="font-size: 0.88rem; color: var(--text-muted); margin: 0;">
                    GitHub'dan kodlar çekiliyor ve kütüphaneler yenileniyor. Lütfen bekleyin...
                </p>
            </div>
        `;
    }

    try {
        const res = await apiCall('/api/system/apply-update', 'POST');
        if (res.success) {
            if (body) {
                body.innerHTML = `
                    <div style="text-align: center; padding: 24px 10px;">
                        <i class="fas fa-check-circle" style="font-size: 2.6rem; color: #10b981; margin-bottom: 16px;"></i>
                        <h4 style="margin: 0 0 8px 0; color: #10b981;">Güncelleme Başarılı!</h4>
                        <p style="font-size: 0.88rem; color: var(--text-muted); margin: 0 0 16px 0;">
                            Uygulama başarıyla güncellendi. Sayfa otomatik olarak yenileniyor...
                        </p>
                    </div>
                `;
            }
            showToast('Uygulama başarıyla güncellendi. Yenileniyor...', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 2500);
        } else {
            showToast(res.error || 'Güncelleme uygulanamadı.', 'error');
            if (body) {
                body.innerHTML = `
                    <div style="text-align: center; padding: 16px;">
                        <i class="fas fa-exclamation-triangle text-danger" style="font-size: 2.2rem; margin-bottom: 12px;"></i>
                        <h4 style="color: #ef4444; margin: 0 0 8px 0;">Güncelleme Hatası</h4>
                        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 16px;">${escapeHtml(res.error || 'Hata oluştu.')}</p>
                        <button class="btn btn-secondary" onclick="closeUpdateModal()">Kapat</button>
                    </div>
                `;
            }
        }
    } catch (e) {
        showToast('Bağlantı hatası: ' + e.message, 'error');
    }
}

/**
 * Şifre görünürlüğünü aç/kapat (eye icon toggle)
 */
function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const icon = btn ? btn.querySelector('i') : null;
    if (input.type === 'password') {
        input.type = 'text';
        if (icon) {
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
        }
    } else {
        input.type = 'password';
        if (icon) {
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
        }
    }
}



