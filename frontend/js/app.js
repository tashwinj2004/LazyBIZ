/**
 * LazyBIZ RAG Dashboard — Single Page Application
 * Enterprise AI-powered Business Intelligence
 */

// ============================================
// CONFIG & STATE
// ============================================
const API_BASE = window.location.origin + '/api';
const APP = {
    token: localStorage.getItem('lazybiz_token'),
    user: JSON.parse(localStorage.getItem('lazybiz_user') || 'null'),
    currentPage: 'analytics',
    sidebarOpen: false,
    chartInstance: null,
    trendChartInstance: null,
    activeJob: null,
    currentFilename: null,
    lastReport: null
};

// ============================================
// ROUTER
// ============================================
function navigate(page) {
    APP.currentPage = page;
    APP.sidebarOpen = false;
    render();
}

const COUNTRY_COORDS = {
    'USA': [37.0902, -95.7129],
    'United States': [37.0902, -95.7129],
    'Canada': [56.1304, -106.3468],
    'UK': [55.3781, -3.4360],
    'United Kingdom': [55.3781, -3.4360],
    'Germany': [51.1657, 10.4515],
    'France': [46.2276, 2.2137],
    'India': [20.5937, 78.9629],
    'China': [35.8617, 104.1954],
    'Japan': [36.2048, 138.2529],
    'Australia': [-25.2744, 133.7751],
    'Brazil': [-14.2350, -51.9253],
    'Russia': [61.5240, 105.3188],
    'Mexico': [23.6345, -102.5528],
    'Italy': [41.8719, 12.5674],
    'Spain': [40.4637, -3.7492],
    'Netherlands': [52.1326, 5.2913],
    'Belgium': [50.5039, 4.4699],
    'Switzerland': [46.8182, 8.2275],
    'Sweden': [60.1282, 18.6435],
    'Norway': [60.4720, 8.4689],
    'Denmark': [56.2639, 9.5018],
    'Finland': [61.9241, 25.7482],
    'Poland': [51.9194, 19.1451],
    'Austria': [47.5162, 14.5501],
    'Greece': [39.0742, 21.8243],
    'Turkey': [38.9637, 35.2433],
    'South Korea': [35.9078, 127.7669],
    'Singapore': [1.3521, 103.8198],
    'Malaysia': [4.2105, 101.9758],
    'Thailand': [15.8700, 100.9925],
    'Vietnam': [14.0583, 108.2772],
    'Indonesia': [-0.7893, 113.9213],
    'Philippines': [12.8797, 121.7740],
    'New Zealand': [-40.9006, 174.8860],
    'South Africa': [-30.5595, 22.9375],
    'Egypt': [26.8206, 30.8025],
    'Nigeria': [9.0820, 8.6753],
    'Israel': [31.0461, 34.8516],
    'UAE': [23.4241, 53.8478],
    'Saudi Arabia': [23.8859, 45.0792],
    'Argentina': [-38.4161, -63.6167],
    'Chile': [-35.6751, -71.5430],
    'Colombia': [4.5709, -74.2973],
    'Peru': [-9.1900, -75.0152],
    'Ireland': [53.1424, -7.6921],
    'Portugal': [39.3999, -8.2245],
};

function render() {
    const app = document.getElementById('app');
    if (!APP.token || !APP.user) {
        // Check hash for register or forgot password
        if (window.location.hash === '#register') {
            app.innerHTML = renderRegisterPage();
            bindRegisterEvents();
        } else if (window.location.hash === '#forgot-password') {
            app.innerHTML = renderForgotPasswordPage();
            bindForgotPasswordEvents();
        } else {
            app.innerHTML = renderLoginPage();
            bindLoginEvents();
        }
    } else {
        app.innerHTML = renderAppLayout();
        bindAppEvents();
        loadPageContent();
    }
}

// ============================================
// API HELPERS
// ============================================
async function apiFetch(endpoint, options = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (APP.token) headers['Authorization'] = `Bearer ${APP.token}`;

    try {
        const resp = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: { ...headers, ...options.headers }
        });

        if (resp.status === 401) {
            logout();
            return { error: 'Session expired. Please login again.' };
        }

        const data = await resp.json();
        if (!resp.ok) return { error: data.error || 'Request failed' };
        return data;
    } catch (err) {
        return { error: 'Network error. Please check your connection.' };
    }
}

async function apiUpload(endpoint, formData) {
    const headers = {};
    if (APP.token) headers['Authorization'] = `Bearer ${APP.token}`;

    try {
        const resp = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers,
            body: formData
        });
        const data = await resp.json();
        if (!resp.ok) return { error: data.error || 'Upload failed' };
        return data;
    } catch (err) {
        return { error: 'Upload failed. Check your connection.' };
    }
}

function logout() {
    APP.token = null;
    APP.user = null;
    localStorage.removeItem('lazybiz_token');
    localStorage.removeItem('lazybiz_user');
    render();
}

function setAuth(token, user) {
    APP.token = token;
    APP.user = user;
    localStorage.setItem('lazybiz_token', token);
    localStorage.setItem('lazybiz_user', JSON.stringify(user));
}

// ============================================
// TOAST NOTIFICATIONS
// ============================================
function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const icons = { success: 'check_circle', error: 'error', info: 'info' };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span class="material-icons-outlined" style="font-size:18px">${icons[type]}</span>${message}`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(60px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ============================================
// FORMAT HELPERS
// ============================================
function formatCurrency(n) {
    if (n >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return '$' + (n / 1e3).toFixed(1) + 'K';
    return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function formatNumber(n) {
    return new Intl.NumberFormat().format(n);
}

function round(val, precision = 1) {
    const factor = Math.pow(10, precision);
    return Math.round(val * factor) / factor;
}

function timeAgo(isoStr) {
    const d = new Date(isoStr);
    const now = new Date();
    const s = Math.floor((now - d) / 1000);
    if (s < 60) return 'Just now';
    if (s < 3600) return Math.floor(s / 60) + 'm ago';
    if (s < 86400) return Math.floor(s / 3600) + 'h ago';
    return Math.floor(s / 86400) + 'd ago';
}

function userInitials() {
    if (!APP.user || !APP.user.name) return '?';
    return APP.user.name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

// ============================================
// ============================================
// LOGIN PAGE
// ============================================
function renderLoginPage() {
    return `
    <div class="auth-page">
        <div class="auth-brand">
            <div class="auth-brand-content">
                <div class="auth-logo">
                    <div class="auth-logo-icon"><span class="material-icons-outlined">hub</span></div>
                    <span class="auth-logo-text">LazyBIZ</span>
                </div>
                <p class="auth-tagline">AI-powered enterprise intelligence.<br>Transform raw data into actionable insights.</p>
                <ul class="auth-features">
                    <li><span class="material-icons-outlined">auto_awesome</span> RAG-powered AI analytics on your data</li>
                    <li><span class="material-icons-outlined">query_stats</span> Real-time revenue & trend forecasting</li>
                    <li><span class="material-icons-outlined">shield</span> Enterprise-grade security & privacy</li>
                    <li><span class="material-icons-outlined">cloud_upload</span> CSV upload with instant processing</li>
                </ul>
            </div>
        </div>
        <div class="auth-form-panel">
            <h1 class="auth-form-title">LazyBIZ</h1>
            <p class="auth-form-subtitle">Sign in to your enterprise dashboard</p>
            <div class="auth-error" id="login-error">
                <span class="material-icons-outlined" style="font-size:16px">error</span>
                <span id="login-error-text"></span>
            </div>
            <form class="auth-form" id="login-form">
                <div class="input-group">
                    <label for="login-email">Email address</label>
                    <input type="email" id="login-email" class="input-field" placeholder="name@company.com" required autocomplete="email">
                </div>
                <div class="input-group">
                    <label for="login-password">Password</label>
                    <div style="position: relative; display: flex; align-items: center; width: 100%;">
                        <input type="password" id="login-password" class="input-field" placeholder="Enter your password" required autocomplete="current-password" style="padding-right: 44px; width: 100%;">
                        <span class="material-icons-outlined password-toggle" style="position: absolute; right: 14px; cursor: pointer; color: var(--on-surface-muted); font-size: 20px; user-select: none;">visibility</span>
                    </div>
                </div>
                <div class="auth-extras">
                    <label class="auth-checkbox">
                        <input type="checkbox" checked> Remember me
                    </label>
                    <a href="#forgot-password" id="goto-forgot">Forgot password?</a>
                </div>
                <button type="submit" class="btn btn-primary btn-block btn-lg" id="login-btn">
                    Sign In
                </button>
            </form>
            <p class="auth-switch">Don't have an account? <a href="#register" id="goto-register">Create an account</a></p>
        </div>
    </div>`;
}

function bindLoginEvents() {
    const form = document.getElementById('login-form');
    const errBox = document.getElementById('login-error');
    const errText = document.getElementById('login-error-text');
    const btn = document.getElementById('login-btn');

    // Show/hide password
    const toggle = form?.querySelector('.password-toggle');
    const pwdInput = document.getElementById('login-password');
    toggle?.addEventListener('click', () => {
        if (pwdInput.type === 'password') {
            pwdInput.type = 'text';
            toggle.textContent = 'visibility_off';
        } else {
            pwdInput.type = 'password';
            toggle.textContent = 'visibility';
        }
    });

    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        errBox?.classList.remove('visible');
        btn.disabled = true;
        btn.textContent = 'Signing in...';

        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;

        const data = await apiFetch('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password })
        });

        if (data.error) {
            if (errText) errText.textContent = data.error;
            errBox?.classList.add('visible');
            btn.disabled = false;
            btn.textContent = 'Sign In';
            return;
        }

        setAuth(data.token, data.user);
        navigate('analytics');
    });

    document.getElementById('goto-register')?.addEventListener('click', (e) => {
        e.preventDefault();
        window.location.hash = '#register';
        render();
    });

    document.getElementById('goto-forgot')?.addEventListener('click', (e) => {
        e.preventDefault();
        window.location.hash = '#forgot-password';
        render();
    });
}

// ============================================
// REGISTER PAGE
// ============================================
function renderRegisterPage() {
    return `
    <div class="auth-page">
        <div class="auth-brand">
            <div class="auth-brand-content">
                <div class="auth-logo">
                    <div class="auth-logo-icon"><span class="material-icons-outlined">hub</span></div>
                    <span class="auth-logo-text">LazyBIZ</span>
                </div>
                <p class="auth-tagline">Join the future of business intelligence.<br>Start making data-driven decisions today.</p>
                <ul class="auth-features">
                    <li><span class="material-icons-outlined">rocket_launch</span> Get started in under 60 seconds</li>
                    <li><span class="material-icons-outlined">psychology</span> AI learns your business patterns</li>
                    <li><span class="material-icons-outlined">trending_up</span> Predictive analytics & forecasting</li>
                    <li><span class="material-icons-outlined">group</span> Built for teams of all sizes</li>
                </ul>
            </div>
        </div>
        <div class="auth-form-panel">
            <h1 class="auth-form-title">Create an account</h1>
            <p class="auth-form-subtitle">Enter your details to get started with enterprise BI.</p>
            <div class="auth-error" id="register-error">
                <span class="material-icons-outlined" style="font-size:16px">error</span>
                <span id="register-error-text"></span>
            </div>
            <form class="auth-form" id="register-form">
                <div class="input-group">
                    <label for="reg-name">Full name</label>
                    <input type="text" id="reg-name" class="input-field" placeholder="John Doe" required autocomplete="name">
                </div>
                <div class="input-group">
                    <label for="reg-email">Email address</label>
                    <input type="email" id="reg-email" class="input-field" placeholder="name@company.com" required autocomplete="email">
                </div>
                <div class="input-group">
                    <label for="reg-phone">Phone number</label>
                    <input type="tel" id="reg-phone" class="input-field" placeholder="e.g. +1234567890" required autocomplete="tel">
                </div>
                <div class="input-group">
                    <label for="reg-password">Password</label>
                    <div style="position: relative; display: flex; align-items: center; width: 100%;">
                        <input type="password" id="reg-password" class="input-field" placeholder="Min. 6 characters" required minlength="6" autocomplete="new-password" style="padding-right: 44px; width: 100%;">
                        <span class="material-icons-outlined password-toggle" style="position: absolute; right: 14px; cursor: pointer; color: var(--on-surface-muted); font-size: 20px; user-select: none;">visibility</span>
                    </div>
                </div>
                <label class="auth-checkbox">
                    <input type="checkbox" id="reg-terms" required> I agree to the <a href="#" style="margin-left:4px">Terms of Service</a>&nbsp;and&nbsp;<a href="#">Privacy Policy</a>
                </label>
                <button type="submit" class="btn btn-primary btn-block btn-lg" id="register-btn">
                    Create Account
                </button>
            </form>
            <p class="auth-switch">Already have an account? <a href="#" id="goto-login">Sign in</a></p>
        </div>
    </div>`;
}

function bindRegisterEvents() {
    const form = document.getElementById('register-form');
    const errBox = document.getElementById('register-error');
    const errText = document.getElementById('register-error-text');
    const btn = document.getElementById('register-btn');

    // Show/hide password
    const toggle = form?.querySelector('.password-toggle');
    const pwdInput = document.getElementById('reg-password');
    toggle?.addEventListener('click', () => {
        if (pwdInput.type === 'password') {
            pwdInput.type = 'text';
            toggle.textContent = 'visibility_off';
        } else {
            pwdInput.type = 'password';
            toggle.textContent = 'visibility';
        }
    });

    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        errBox?.classList.remove('visible');
        btn.disabled = true;
        btn.textContent = 'Creating account...';

        const name = document.getElementById('reg-name').value;
        const email = document.getElementById('reg-email').value;
        const phone = document.getElementById('reg-phone').value;
        const password = document.getElementById('reg-password').value;

        const data = await apiFetch('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ name, email, phone, password })
        });

        if (data.error) {
            if (errText) errText.textContent = data.error;
            errBox?.classList.add('visible');
            btn.disabled = false;
            btn.textContent = 'Create Account';
            return;
        }

        setAuth(data.token, data.user);
        showToast('Account created successfully!', 'success');
        navigate('analytics');
    });

    document.getElementById('goto-login')?.addEventListener('click', (e) => {
        e.preventDefault();
        window.location.hash = '';
        render();
    });
}

// ============================================
// FORGOT PASSWORD PAGE
// ============================================
function renderForgotPasswordPage() {
    return `
    <div class="auth-page">
        <div class="auth-brand">
            <div class="auth-brand-content">
                <div class="auth-logo">
                    <div class="auth-logo-icon"><span class="material-icons-outlined">hub</span></div>
                    <span class="auth-logo-text">LazyBIZ</span>
                </div>
                <p class="auth-tagline">Reset your account password.<br>Verify your registered phone number to proceed.</p>
                <ul class="auth-features">
                    <li><span class="material-icons-outlined">lock_reset</span> Secure instant password reset</li>
                    <li><span class="material-icons-outlined">sms</span> Verification link simulation</li>
                    <li><span class="material-icons-outlined">shield</span> Enforced credential safety</li>
                </ul>
            </div>
        </div>
        <div class="auth-form-panel">
            <h1 class="auth-form-title">Reset password</h1>
            <p class="auth-form-subtitle">Enter your registered phone number and new password.</p>
            <div class="auth-error" id="forgot-error">
                <span class="material-icons-outlined" style="font-size:16px">error</span>
                <span id="forgot-error-text"></span>
            </div>
            <form class="auth-form" id="forgot-form">
                <div class="input-group">
                    <label for="forgot-phone">Registered Phone Number</label>
                    <input type="tel" id="forgot-phone" class="input-field" placeholder="e.g. +1234567890" required autocomplete="tel">
                </div>
                <div class="input-group">
                    <label for="forgot-password">New Password</label>
                    <div style="position: relative; display: flex; align-items: center; width: 100%;">
                        <input type="password" id="forgot-password" class="input-field" placeholder="Min. 6 characters" required minlength="6" autocomplete="new-password" style="padding-right: 44px; width: 100%;">
                        <span class="material-icons-outlined password-toggle" style="position: absolute; right: 14px; cursor: pointer; color: var(--on-surface-muted); font-size: 20px; user-select: none;">visibility</span>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary btn-block btn-lg" id="forgot-btn">
                    Reset &amp; Sign In
                </button>
            </form>
            <p class="auth-switch"><a href="#" id="forgot-goto-login">Back to Sign In</a></p>
        </div>
    </div>`;
}

function bindForgotPasswordEvents() {
    const form = document.getElementById('forgot-form');
    const errBox = document.getElementById('forgot-error');
    const errText = document.getElementById('forgot-error-text');
    const btn = document.getElementById('forgot-btn');

    // Show/hide password
    const toggle = form?.querySelector('.password-toggle');
    const pwdInput = document.getElementById('forgot-password');
    toggle?.addEventListener('click', () => {
        if (pwdInput.type === 'password') {
            pwdInput.type = 'text';
            toggle.textContent = 'visibility_off';
        } else {
            pwdInput.type = 'password';
            toggle.textContent = 'visibility';
        }
    });

    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        errBox?.classList.remove('visible');
        btn.disabled = true;
        btn.textContent = 'Resetting...';

        const phone = document.getElementById('forgot-phone').value;
        const password = document.getElementById('forgot-password').value;

        const data = await apiFetch('/auth/reset-password', {
            method: 'POST',
            body: JSON.stringify({ phone, password })
        });

        if (data.error) {
            if (errText) errText.textContent = data.error;
            errBox?.classList.add('visible');
            btn.disabled = false;
            btn.textContent = 'Reset & Sign In';
            return;
        }

        setAuth(data.token, data.user);
        showToast('Password reset successfully!', 'success');
        navigate('analytics');
    });

    document.getElementById('forgot-goto-login')?.addEventListener('click', (e) => {
        e.preventDefault();
        window.location.hash = '';
        render();
    });
}

// ============================================
// APP LAYOUT (Sidebar + Main)
// ============================================
function renderAppLayout() {
    const navItems = [
        { id: 'analytics', icon: 'query_stats', label: 'Dashboard' },
        { id: 'map', icon: 'public', label: 'Map' },
        { id: 'history', icon: 'history', label: 'History' },
    ];

    const navHTML = navItems.map(n => `
        <button class="nav-item ${APP.currentPage === n.id ? 'active' : ''}" data-page="${n.id}" id="nav-${n.id}">
            <span class="material-icons-outlined">${n.icon}</span>
            ${n.label}
        </button>
    `).join('');

    const mobileNavHTML = navItems.map(n => `
        <button class="mobile-nav-item ${APP.currentPage === n.id ? 'active' : ''}" data-page="${n.id}">
            <span class="material-icons-outlined">${n.icon}</span>
            ${n.label}
        </button>
    `).join('');

    return `
    <div class="sidebar-overlay" id="sidebar-overlay"></div>

    <div class="app-layout" id="app-layout">
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-logo">
                    <div class="sidebar-logo-icon"><span class="material-icons-outlined">hub</span></div>
                    <div>
                        <div class="sidebar-logo-name">LazyBIZ</div>
                        <span class="sidebar-logo-badge">AI BI</span>
                    </div>
                </div>
            </div>
            <nav class="sidebar-nav">
                ${navHTML}
                <div class="nav-spacer"></div>
                <button class="nav-item" data-page="account" id="nav-account">
                    <span class="material-icons-outlined">account_circle</span>
                    Account
                </button>
                <button class="nav-item" id="nav-logout">
                    <span class="material-icons-outlined">logout</span>
                    Logout
                </button>
            </nav>
            <div class="sidebar-footer">
                <div class="user-info">
                    <div class="user-avatar">${userInitials()}</div>
                    <div>
                        <div class="user-name">${APP.user?.name || 'User'}</div>
                        <div class="user-email">${APP.user?.email || ''}</div>
                    </div>
                </div>
            </div>
        </aside>

        <button class="sidebar-toggle-btn" id="sidebar-toggle-btn" title="Toggle Sidebar">
            <span class="material-icons-outlined" id="sidebar-toggle-icon">chevron_left</span>
        </button>

        <main class="main-content" id="main-content">
            <div id="page-container" class="page-enter"></div>
        </main>
    </div>

    <nav class="mobile-bottom-nav">
        <div class="mobile-nav-items">
            ${mobileNavHTML}
        </div>
    </nav>`;
}

function bindAppEvents() {
    document.querySelectorAll('.nav-item[data-page]').forEach(btn => {
        btn.addEventListener('click', () => navigate(btn.dataset.page));
    });

    document.querySelectorAll('.mobile-nav-item[data-page]').forEach(btn => {
        btn.addEventListener('click', () => navigate(btn.dataset.page));
    });

    document.getElementById('nav-logout')?.addEventListener('click', () => {
        logout();
        showToast('Logged out successfully', 'info');
    });

    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const layout = document.getElementById('app-layout');
    const menuBtn = document.getElementById('sidebar-menu-btn');
    const toggleBtn = document.getElementById('sidebar-toggle-btn');
    const toggleIcon = document.getElementById('sidebar-toggle-icon');

    function toggleSidebar() {
        const isCollapsed = sidebar?.classList.contains('collapsed');
        if (isCollapsed) {
            sidebar?.classList.remove('collapsed');
            layout?.classList.remove('sidebar-collapsed');
            if (toggleIcon) toggleIcon.textContent = 'chevron_left';
        } else {
            sidebar?.classList.add('collapsed');
            layout?.classList.add('sidebar-collapsed');
            if (toggleIcon) toggleIcon.textContent = 'chevron_right';
        }
    }

    // Header menu button toggles sidebar on all screen sizes
    menuBtn?.addEventListener('click', toggleSidebar);
    
    // Desktop slider button
    toggleBtn?.addEventListener('click', toggleSidebar);

    overlay?.addEventListener('click', () => {
        sidebar?.classList.remove('open');
        overlay?.classList.remove('open');
    });
}

// ============================================
// PAGE CONTENT LOADER
// ============================================
function loadPageContent() {
    const container = document.getElementById('page-container');
    if (!container) return;

    container.innerHTML = '';
    container.className = 'page-container page-enter';

    if (APP.currentPage === 'analytics') {
        renderAnalyticsPage(container);
    } else if (APP.currentPage === 'map') {
        renderMapPage(container);
    } else if (APP.currentPage === 'history') {
        renderHistoryPage(container);
    } else if (APP.currentPage === 'account') {
        renderAccountPage(container);
    } else {
        renderAnalyticsPage(container);
    }
}

// ============================================
// ANALYTICS PAGE — Full MCP Pipeline UI
// ============================================
function renderAnalyticsPage(container) {
    container.innerHTML = `
    <div class="page-header">
        <div class="page-header-row">
            <div style="display:flex;align-items:center;gap:14px">
                <button class="sidebar-menu-btn" id="sidebar-menu-btn" title="Toggle Sidebar">
                    <span class="material-icons-outlined" id="sidebar-menu-icon">menu</span>
                </button>
                <div>
                    <h1 class="page-title">Dashboard</h1>
                    <p class="page-subtitle">Upload a CSV → MCP cleans &amp; analyzes → AI generates charts &amp; insights.</p>
                </div>
            </div>
            <span class="chip chip-info">
                <span class="material-icons-outlined" style="font-size:14px">auto_awesome</span>
                MCP + RAG + LLM
            </span>
        </div>
    </div>
    <div class="page-body">
        <div class="pipeline-steps">
            <div class="pipeline-step active"><span class="step-num">1</span><span>Upload CSV</span></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step" id="ps-clean"><span class="step-num">2</span><span>MCP Clean</span></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step" id="ps-analyze"><span class="step-num">3</span><span>MCP Analyze</span></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step" id="ps-viz"><span class="step-num">4</span><span>Visualize</span></div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step" id="ps-llm"><span class="step-num">5</span><span>RAG + LLM</span></div>
        </div>

        <div class="card" id="analytics-upload-card">
            <div class="upload-zone" id="analytics-drop-zone">
                <span class="material-icons-outlined upload-icon">upload_file</span>
                <div class="upload-title">Drop your CSV here</div>
                <div class="upload-subtitle">Sales, reviews, orders — any CSV file works</div>
                <button class="btn btn-primary" id="analytics-browse-btn">
                    <span class="material-icons-outlined" style="font-size:18px">folder_open</span>
                    Browse CSV
                </button>
                <input type="file" id="analytics-file-input" accept=".csv" style="display:none">
            </div>
            <div id="pipeline-progress-wrapper" style="display:none; margin-top:20px">
                <div class="pipeline-progress-bar-bg">
                    <div class="pipeline-progress-bar-fill" id="pipeline-progress-fill" style="width:0%"></div>
                </div>
                <div id="pipeline-progress-msg" class="pipeline-progress-msg">Starting...</div>
            </div>
        </div>

        <div id="analytics-results" style="display:none">
            <div class="card mt-md" id="clean-report-card">
                <div class="card-header">
                    <div>
                        <div class="card-title">🔧 MCP: Data Cleaning Report</div>
                        <div class="card-subtitle">Issues detected &amp; fixed automatically</div>
                    </div>
                    <span class="chip chip-success">Complete</span>
                </div>
                <div id="clean-report-body"></div>
            </div>

            <div class="kpi-grid mt-md" id="analytics-kpi-grid"></div>

            <!-- Charts Row: Sales Trend + Category Revenue -->
            <div class="dashboard-main-row mt-md" id="dashboard-charts-row" style="display:none">
                <div class="card dashboard-chart-col">
                    <div class="card-header">
                        <div>
                            <div class="card-title">📊 Sales Trend</div>
                            <div class="card-subtitle" id="trend-chart-subtitle">Revenue generated over time</div>
                        </div>
                        <select id="trend-time-filter" class="input-field" style="width: auto; padding: 4px 8px; font-size: 13px;">
                            <option value="yearly">Yearly</option>
                            <option value="monthly">Monthly</option>
                        </select>
                    </div>
                    <div style="height:220px;position:relative">
                        <canvas id="yearly-sales-canvas"></canvas>
                    </div>
                </div>
                <div class="card dashboard-chart-col" id="category-revenue-card">
                    <div class="card-header">
                        <div>
                            <div class="card-title">📈 Category Revenue</div>
                            <div class="card-subtitle">Revenue by product category</div>
                        </div>
                    </div>
                    <div style="height:220px;position:relative">
                        <canvas id="category-revenue-canvas"></canvas>
                    </div>
                </div>
            </div>

            <!-- Products Row -->
            <!-- Products & Customers Row -->
            <div class="dashboard-main-row mt-md" id="dashboard-customers-row" style="display:none; gap: 24px;">
                <div class="card dashboard-products-col" id="top-customers-card" style="display:none; flex: 1;">
                    <div class="card-header">
                        <div>
                            <div class="card-title">💎 Top 5 High-Revenue Customers</div>
                            <div class="card-subtitle">By total purchase value</div>
                        </div>
                        <span class="chip chip-info" style="font-size:11px">High Value</span>
                    </div>
                    <div class="product-list-compact" id="top-customers-list" style="max-height: 400px;"></div>
                </div>

                <div class="card dashboard-products-col" id="top-ordered-card" style="display:none; flex: 1;">
                    <div class="card-header">
                        <div>
                            <div class="card-title">📦 Top 5 Most Ordered Products</div>
                            <div class="card-subtitle">By total order volume</div>
                        </div>
                        <span class="chip chip-success" style="font-size:11px">High Volume</span>
                    </div>
                    <div class="product-list-compact" id="top-ordered-products-list" style="max-height: 400px;"></div>
                </div>
            </div>

            <div id="sentiment-overview-container" style="display:none" class="mt-md"></div>

            <!-- Risk Analysis Section (25:75 Split) -->
            <div id="risk-analysis-container" style="display:none" class="mt-md">
                <div class="card">
                    <div class="card-header">
                        <div>
                            <div class="card-title">🚩 Product Risk & Solutions</div>
                            <div class="card-subtitle">Products with highest negative feedback and recommended fixes</div>
                        </div>
                    </div>
                    <div class="risk-layout">
                        <div class="risk-list-col">
                            <h4 class="risk-col-title">Top 5 At-Risk Products</h4>
                            <div id="risk-products-list"></div>
                        </div>
                        <div class="risk-solution-col">
                            <h4 class="risk-col-title">AI-Recommended Solutions</h4>
                            <div id="risk-solutions-list"></div>
                        </div>
                    </div>
                </div>
            </div>


            <!-- Future Sales Prediction Section -->
            <div id="prediction-container" style="display:none" class="mt-md">
                <div class="card">
                    <div class="card-header">
                        <div>
                            <div class="card-title">🚀 Future Sales Prediction</div>
                            <div class="card-subtitle">Risk-Mitigated Growth Projection (Next 4 Months)</div>
                        </div>
                        <div class="kpi-indicator positive" id="forecast-boost-badge" style="display:none">
                             Potential Recovery: <span id="forecast-boost-val">$0</span>
                        </div>
                    </div>
                    <div class="p-lg">
                        <div style="height:350px">
                            <canvas id="prediction-chart"></canvas>
                        </div>
                        <div class="mt-md p-md" style="background: rgba(var(--primary-rgb), 0.05); border-radius: var(--radius); border: 1px solid rgba(var(--primary-rgb), 0.1);">
                            <div class="d-flex align-center gap-sm text-primary mb-xs">
                                <span class="material-icons-outlined" style="font-size:18px">info</span>
                                <strong style="font-size:13px">Prediction Logic</strong>
                            </div>
                            <p class="text-muted" style="font-size:12px; line-height:1.5;">
                                This projection simulates total revenue growth assuming the identified <strong>Product Risks</strong> are resolved. 
                                It uses a recovery-boost algorithm that converts negative sentiment impact into neutral/satisfied volume across your catalog.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
            <!-- AI Insights Section -->
            <div class="card mt-md">
                <div class="card-header">
                    <div>
                        <div class="card-title">✨ AI-Powered Business Insights</div>
                        <div class="card-subtitle">Strategic recommendations generated by RAG + LLM</div>
                    </div>
                    <span class="chip chip-info" id="chart-count-badge">Processing...</span>
                </div>
                <div class="insights-panel" id="analytics-insights-panel"></div>
            </div>



            <div class="card mt-md">
                <div class="card-header">
                    <div>
                        <div class="card-title">💬 Ask LazyBIZ AI</div>
                        <div class="card-subtitle" id="chat-subtitle">Query your data with natural language</div>
                    </div>
                </div>
                <div class="chat-messages" id="analytics-messages" style="min-height:120px;max-height:400px">
                    <div class="chat-msg ai">Data loaded! Ask me anything about your CSV — trends, top products, anomalies…</div>
                </div>
                <div class="chat-input-row">
                    <input type="text" class="input-field" id="analytics-chat-input" placeholder="e.g. What drives our highest revenue?">
                    <button class="btn btn-primary" id="analytics-chat-send">
                        <span class="material-icons-outlined" style="font-size:18px">send</span>
                    </button>
                </div>
            </div>
        </div>

        <div class="card mt-xl" id="analytics-recent-uploads">
            <div class="card-header">
                <div>
                    <div class="card-title">Recent Data Sources</div>
                    <div class="card-subtitle">Previously ingested files available for RAG search</div>
                </div>
                <span class="material-icons-outlined text-muted" style="font-size:20px">storage</span>
            </div>
            <div id="uploads-list">
                <div class="skeleton skeleton-text" style="height:40px;margin-top:8px"></div>
                <div class="skeleton skeleton-text" style="height:40px;margin-top:8px"></div>
            </div>
        </div>
    </div>
    `;

    bindAnalyticsUploadEvents();
    if (APP.activeJob) {
        document.getElementById('pipeline-progress-wrapper').style.display = 'block';
        setPipelineProgress(APP.activeJob.progress, APP.activeJob.message);
    }
    loadUploads();
}

function bindAnalyticsUploadEvents() {
    const zone = document.getElementById('analytics-drop-zone');
    const input = document.getElementById('analytics-file-input');
    const browseBtn = document.getElementById('analytics-browse-btn');

    browseBtn?.addEventListener('click', (e) => { e.stopPropagation(); input.click(); });
    zone?.addEventListener('click', () => input.click());

    zone?.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
    zone?.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone?.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        const f = e.dataTransfer.files[0];
        if (f) startPipeline(f);
    });

    input?.addEventListener('change', () => {
        if (input.files[0]) startPipeline(input.files[0]);
    });

    const chatInput = document.getElementById('analytics-chat-input');
    const chatSend = document.getElementById('analytics-chat-send');
    const sendChat = () => {
        const q = chatInput?.value.trim();
        if (q) { sendAnalyticsMessage(q); chatInput.value = ''; }
    };
    chatSend?.addEventListener('click', sendChat);
    chatInput?.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendChat(); });
}

async function startPipeline(file) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
        showToast('Only CSV files are supported.', 'error'); return;
    }
    
    APP.currentFilename = file.name;

    document.getElementById('pipeline-progress-wrapper').style.display = 'block';
    document.getElementById('analytics-results').style.display = 'none';
    setPipelineProgress(2, '⏳ Uploading CSV...');

    const formData = new FormData();
    formData.append('file', file);

    const uploadData = await apiUpload('/upload', formData);
    if (uploadData.error) {
        showToast(uploadData.error, 'error');
        setPipelineProgress(0, '❌ Upload failed');
        return;
    }
    
    if (uploadData.file_name) {
        APP.currentFilename = uploadData.file_name;
    }

    const fileId = uploadData.file_id;
    loadUploads();

    setPipelineProgress(5, '⏳ Starting analysis...');
    const startData = await apiFetch('/start-analysis', {
        method: 'POST',
        body: JSON.stringify({ file_id: fileId })
    });

    if (startData.error) {
        showToast(startData.error, 'error');
        setPipelineProgress(0, '❌ Failed to start analysis');
        return;
    }

    pollPipeline(startData.job_id, fileId);
}

function setPipelineProgress(pct, msg) {
    const fill = document.getElementById('pipeline-progress-fill');
    const msgEl = document.getElementById('pipeline-progress-msg');
    if (fill) fill.style.width = pct + '%';
    if (msgEl) msgEl.textContent = msg;

    if (pct >= 20) document.getElementById('ps-clean')?.classList.add('active');
    if (pct >= 50) document.getElementById('ps-analyze')?.classList.add('active');
    if (pct >= 75) document.getElementById('ps-viz')?.classList.add('active');
    if (pct >= 90) document.getElementById('ps-llm')?.classList.add('active');
}

async function pollPipeline(jobId, fileId) {
    APP.activeJob = { jobId, fileId, progress: 0, message: 'Starting...' };

    const interval = setInterval(async () => {
        const data = await apiFetch(`/job/${jobId}`);
        if (data.error && !data.status) {
            clearInterval(interval);
            APP.activeJob = null;
            showToast('Failed to poll job.', 'error'); return;
        }

        const progress = data.progress || 0;
        const message = data.message || '';
        if (APP.activeJob) {
            APP.activeJob.progress = progress;
            APP.activeJob.message = message;
        }

        if (APP.currentPage === 'analytics') {
            setPipelineProgress(progress, message);
        }

        if (data.status === 'done') {
            clearInterval(interval);
            APP.activeJob = null;
            showToast('Pipeline complete! Fetching results...', 'success');
            const reportData = await apiFetch(`/report/${fileId}`);
            if (reportData.error) {
                showToast('Failed to fetch report.', 'error');
            } else if (APP.currentPage === 'analytics') {
                renderPipelineResults(reportData);
            }
            loadUploads();
        } else if (data.status === 'error' || data.status === 'failed') {
            clearInterval(interval);
            APP.activeJob = null;
            if (APP.currentPage === 'analytics') {
                setPipelineProgress(0, '❌ ' + (data.error || 'Pipeline error'));
            }
            showToast('Pipeline failed: ' + (data.error?.slice(0, 80) || ''), 'error');
        }
    }, 1500);
}

function renderPipelineResults(result) {
    const resultsArea = document.getElementById('analytics-results');
    if (resultsArea) resultsArea.style.display = 'block';

    const chatSubtitle = document.getElementById('chat-subtitle');
    if (chatSubtitle && APP.currentFilename) {
        chatSubtitle.innerHTML = `Chatting with: <b style="color:var(--primary)">${escapeHtml(APP.currentFilename)}</b>`;
    }

    const cr = result.clean_report || {};
    const cleanBody = document.getElementById('clean-report-body');
    if (cleanBody) {
        const steps = (cr.steps || []).map(s => {
            const detail = Object.entries(s)
                .filter(([k]) => k !== 'step')
                .map(([k, v]) => `<span class="stat-pill">${k}: <b>${JSON.stringify(v)}</b></span>`)
                .join(' ');
            return `<div class="clean-step">
                <span class="material-icons-outlined" style="font-size:16px;color:var(--secondary)">check</span>
                <strong>${s.step.replace(/_/g,' ')}</strong> ${detail}
            </div>`;
        }).join('');
        cleanBody.innerHTML = `
            <div class="clean-summary">
                <span class="stat-pill">Original: <b>${cr.original_shape?.rows} rows × ${cr.original_shape?.cols} cols</b></span>
                <span class="stat-pill">Clean: <b>${cr.clean_shape?.rows} rows × ${cr.clean_shape?.cols} cols</b></span>
                <span class="stat-pill">Issues fixed: <b>${cr.issues_fixed}</b></span>
            </div>
            <div class="clean-steps">${steps}</div>
        `;
    }

    APP.lastReport = result;
    window._selectedCategory = null; // reset filter on new report

    // ── Declare ALL variables first ────────────────────────────────────────
    const kpis      = result.analysis?.kpis || {};
    const sent      = result.analysis?.sentiment;
    const yearly    = result.analysis?.yearly_trend || {};
    const topCusts  = result.analysis?.top_customers || [];
    const topOrd    = result.analysis?.top_ordered_products || [];
    const catRev    = result.analysis?.category_revenue || {};
    const riskProds = result.analysis?.risk_products || [];
    const forecast  = result.analysis?.future_forecast;
    const charts    = (result.charts || []).filter(c => c.image);
    const insights  = result.insights || [];

    // ── KPI Cards ──────────────────────────────────────────────────────────
    const kpiGrid = document.getElementById('analytics-kpi-grid');
    if (kpiGrid && kpis.total !== undefined) {
        const growthValue = kpis.yearly_growth_pct ?? kpis.growth_rate_pct ?? 0;
        const growthLabel = kpis.yearly_growth_pct != null ? 'vs last year' : 'vs last period';
        const isPositive = growthValue >= 0;
        const growthHtml = `
            <div class="kpi-indicator ${isPositive ? 'positive':'negative'}">
               <span class="material-icons-outlined">${isPositive ? 'trending_up':'trending_down'}</span>
               ${Math.abs(growthValue)}%
               <span class="indicator-label">${growthLabel}</span>
            </div>`;
        kpiGrid.innerHTML = `
            <div class="kpi-card"><div class="kpi-card-content">
                <div class="kpi-label"><span class="material-icons-outlined">payments</span> Total Revenue</div>
                <div class="kpi-value">${formatCurrency(kpis.total || 0)}</div>
                ${growthHtml}
            </div></div>
            <div class="kpi-card"><div class="kpi-card-content">
                <div class="kpi-label"><span class="material-icons-outlined">trending_up</span> Total Profit</div>
                <div class="kpi-value">${formatCurrency(kpis.total_profit || 0)}</div>
                <div class="kpi-indicator ${isPositive ? 'positive' : 'negative'}">
                    <span class="material-icons-outlined">${isPositive ? 'trending_up' : 'trending_down'}</span>
                    ${Math.abs(Math.round(growthValue * 0.8))}%
                    <span class="indicator-label">${growthLabel}</span>
                </div>
            </div></div>
            <div class="kpi-card"><div class="kpi-card-content">
                <div class="kpi-label"><span class="material-icons-outlined">shopping_cart</span> Total Orders</div>
                <div class="kpi-value">${formatNumber(kpis.total_orders || 0)}</div>
                <div class="kpi-indicator ${isPositive ? 'positive' : 'negative'}">
                    <span class="material-icons-outlined">${isPositive ? 'trending_up' : 'trending_down'}</span>
                    ${Math.abs(Math.round(growthValue * 1.2))}%
                    <span class="indicator-label">${growthLabel}</span>
                </div>
            </div></div>
            <div class="kpi-card"><div class="kpi-card-content">
                <div class="kpi-label"><span class="material-icons-outlined">assignment_return</span> Return Rate</div>
                <div class="kpi-value">${kpis.return_rate != null ? kpis.return_rate + '%' : 'N/A'}</div>
                <div class="kpi-indicator ${kpis.return_rate > 5 ? 'negative' : 'positive'}">
                    <span class="material-icons-outlined">${kpis.return_rate > 5 ? 'trending_up' : 'trending_down'}</span>
                    ${kpis.return_rate > 5 ? 'Needs Attention' : 'Stable'}
                    <span class="indicator-label">risk level</span>
                </div>
            </div></div>
        `;
    }

    // ── Sales Trend + Category Revenue Charts ──────────────────────────────
    const chartsRow = document.getElementById('dashboard-charts-row');
    if ((yearly.labels && yearly.labels.length) || (catRev.labels && catRev.labels.length)) {
        chartsRow?.style.setProperty('display', 'flex');
    }
    const trendSelect = document.getElementById('trend-time-filter');
    if (trendSelect) {
        trendSelect.value = 'yearly';
        trendSelect.onchange = () => {
            const val = trendSelect.value;
            if (val === 'yearly') {
                renderYearlySalesChart(result.analysis?.yearly_trend || {}, null, 'Yearly Sales Trend');
            } else {
                renderYearlySalesChart(result.analysis?.trend || {}, null, 'Monthly Sales Trend');
            }
        };
    }
    renderYearlySalesChart(yearly, null, 'Yearly Sales Trend');
    // renderCategoryRevenueChart is called via setTimeout inside renderPipelineResults (below)

    // ── Top Customers & Ordered Products ──────────────────────────────────
    const customersRow = document.getElementById('dashboard-customers-row');
    const topCustsEl = document.getElementById('top-customers-list');
    const topOrdEl = document.getElementById('top-ordered-products-list');

    if (customersRow && (topCusts.length > 0 || topOrd.length > 0)) {
        customersRow.style.setProperty('display', 'flex');
        
        if (topCustsEl && topCusts.length > 0) {
            topCustsEl.innerHTML = topCusts.map((c, i) => `
                <div class="product-item-compact">
                    <div class="product-rank">${i + 1}</div>
                    <div class="product-name">${escapeHtml(c.name)}</div>
                    <div class="product-value" style="color:var(--primary)">${formatCurrency(c.revenue)}</div>
                </div>
            `).join('');
            document.getElementById('top-customers-card')?.style.setProperty('display', 'flex');
            document.getElementById('top-customers-card')?.style.setProperty('flex-direction', 'column');
        }

        if (topOrdEl && topOrd.length > 0) {
            topOrdEl.innerHTML = topOrd.map((p, i) => `
                <div class="product-item-compact">
                    <div class="product-rank">${i + 1}</div>
                    <div class="product-name">${escapeHtml(p.name)}</div>
                    <div class="product-value" style="color:var(--secondary)">${formatNumber(p.value)} units</div>
                </div>
            `).join('');
            document.getElementById('top-ordered-card')?.style.setProperty('display', 'flex');
            document.getElementById('top-ordered-card')?.style.setProperty('flex-direction', 'column');
        }
    }

    // ── Sentiment Overview ─────────────────────────────────────────────────
    const sentContainer = document.getElementById('sentiment-overview-container');
    if (sentContainer) {
        sentContainer.style.display = 'block';
        if (sent && sent.distribution && sent.total_analyzed > 0) {
            renderSentimentOverview(sentContainer, sent);
        } else {
            sentContainer.innerHTML = `
                <div class="card p-lg text-center">
                    <div class="sentiment-header">
                        <h3 class="sentiment-main-title">Customer Sentiment Overview</h3>
                    </div>
                    <div class="p-xl">
                        <span class="material-icons-outlined" style="font-size:48px;color:var(--on-surface-muted);opacity:0.3">reviews</span>
                        <p class="mt-md text-muted">No review or feedback data detected in this CSV.<br>Please upload a file with a 'Review' or 'Comment' column to see sentiment analysis.</p>
                    </div>
                </div>
            `;
        }
    }

    // ── Risk Analysis ──────────────────────────────────────────────────────
    const riskContainer = document.getElementById('risk-analysis-container');
    const riskProdsEl = document.getElementById('risk-products-list');
    const riskSolsEl = document.getElementById('risk-solutions-list');
    if (riskContainer && riskProds.length > 0) {
        riskContainer.style.display = 'block';
        riskProdsEl.innerHTML = riskProds.map(p => `
            <div class="risk-product-item">
                <span class="material-icons-outlined" style="font-size:16px; color:var(--error)">warning</span>
                <span class="risk-product-name">${escapeHtml(p.name)}</span>
            </div>
        `).join('');
        riskSolsEl.innerHTML = riskProds.map(p => `
            <div class="risk-solution-item">
                <div class="risk-sol-header">
                    <strong>Issue with ${escapeHtml(p.name)}</strong>
                    <span class="chip chip-danger" style="font-size:10px">High Risk</span>
                </div>
                <p class="risk-sol-text">${escapeHtml(p.solution)}</p>
            </div>
        `).join('');
    }

    // ── Future Sales Prediction ────────────────────────────────────────────
    if (forecast && forecast.forecast_values && forecast.forecast_values.length) {
        const predContainer = document.getElementById('prediction-container');
        if (predContainer) {
            predContainer.style.display = 'block';
            renderFuturePredictionChart(forecast);
        }
    }

    // ── Charts badge ───────────────────────────────────────────────────────
    const badge = document.getElementById('chart-count-badge');
    if (badge) badge.textContent = `${sent?.distribution ? 1 : 0} charts`;

    // ── Make Category Revenue chart interactive ────────────────────────────
    // Re-render with click handler after a tick so the canvas is ready
    setTimeout(() => renderCategoryRevenueChart(catRev, result), 50);

    // ── AI Insights Panel ──────────────────────────────────────────────────
    const insightsPanel = document.getElementById('analytics-insights-panel');
    const typeIcons = { risk: 'warning', opportunity: 'lightbulb', trend: 'insights' };
    if (insightsPanel) {
        insightsPanel.innerHTML = insights.map(i => `
            <div class="insight-item type-${i.type || 'trend'}">
                <span class="insight-icon material-icons-outlined">${typeIcons[i.type] || 'auto_awesome'}</span>
                <div class="insight-title">${escapeHtml(i.title)}</div>
                <div class="insight-body">${escapeHtml(i.body)}</div>
            </div>
        `).join('') || '<p class="text-muted" style="padding:16px">No insights generated.</p>';
    }

    resultsArea?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Map Page ──────────────────────────────────────────────────
function renderMapPage(container) {
    container.innerHTML = `
    <div class="map-page-container">
        <div id="world-map" style="width: 100%; height: 100%; min-height: calc(100vh - 120px);"></div>
        <div class="map-overlay-info">
            <h2 class="map-title">Global Order Distribution</h2>
            <p class="map-subtitle">Visualizing order volume by country</p>
        </div>
    </div>`;

    // Wait for container to be in DOM before initializing Leaflet
    setTimeout(() => {
        const mapEl = document.getElementById('world-map');
        if (!mapEl) return;

        const map = L.map('world-map', {
            center: [20, 0],
            zoom: 2,
            minZoom: 2,
            maxZoom: 12
        });

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }).addTo(map);

        const ordersByCountry = APP.lastReport?.analysis?.orders_by_country || {};
        const countries = Object.keys(ordersByCountry);

        if (countries.length === 0) {
            showToast('No country data available. Upload a dataset first.', 'info');
            return;
        }

        const counts = Object.values(ordersByCountry);
        const maxOrders = Math.max(...counts);

        countries.forEach(country => {
            const coords = COUNTRY_COORDS[country];
            if (coords) {
                const count = ordersByCountry[country];
                // Proportional size and color intensity
                const radius = Math.max(6, (count / maxOrders) * 30);
                const opacity = 0.5 + (count / maxOrders) * 0.4;
                
                L.circleMarker(coords, {
                    radius: radius,
                    fillColor: "#096C6C",
                    color: "#0B8A8A",
                    weight: 1.5,
                    opacity: 1,
                    fillOpacity: opacity
                }).addTo(map).bindPopup(`
                    <div style="color:#1e293b; font-family: 'Inter', sans-serif;">
                        <strong style="font-size:14px">${country}</strong><br>
                        <span style="font-size:12px">Total Orders: ${formatNumber(count)}</span>
                    </div>
                `);
            }
        });
    }, 100);
}


// ── Yearly Sales Trend Chart (Chart.js) ──────────────────────
function renderYearlySalesChart(yearlyData, filterCategory, customTitle) {
    const canvas = document.getElementById('yearly-sales-canvas');
    const wrapper = document.getElementById('yearly-sales-card');
    if (!canvas) return;

    let labels, values, title;
    const byCategory = yearlyData.by_category || {};
    const years = yearlyData.years || yearlyData.labels || [];

    if (filterCategory && byCategory[filterCategory]) {
        labels = years;
        values = byCategory[filterCategory];
        title  = `Sales Trend — ${filterCategory}`;
    } else {
        labels = yearlyData.labels || [];
        values = yearlyData.values || [];
        title  = customTitle || 'Year-Wise Sales Trend';
    }

    if (!labels.length) { wrapper?.style.setProperty('display','none'); return; }
    wrapper?.style.setProperty('display','block');

    if (APP.trendChartInstance) { APP.trendChartInstance.destroy(); APP.trendChartInstance = null; }

    const ctx = canvas.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 260);
    grad.addColorStop(0, 'rgba(37,99,235,0.25)');
    grad.addColorStop(1, 'rgba(37,99,235,0.01)');

    APP.trendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Revenue',
                data: values,
                borderColor: '#2563EB',
                backgroundColor: grad,
                borderWidth: 3,
                pointRadius: 5,
                pointBackgroundColor: '#2563EB',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                tension: 0,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: { display: true, text: title, color: '#344054', font: { size: 14, weight: '600' } },
                tooltip: {
                    callbacks: {
                        label: ctx => ' ' + formatCurrency(ctx.parsed.y)
                    }
                }
            },
            scales: {
                x: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { color: '#667085' } },
                y: {
                    grid: { color: 'rgba(0,0,0,0.05)' },
                    ticks: { color: '#667085', callback: v => formatCurrency(v) }
                }
            }
        }
    });
}

// ── Category Revenue Horizontal Bar Chart (Chart.js) ──────────
// Pass the full report object so click-filter can access all sub-data
function renderCategoryRevenueChart(catData, fullReport) {
    const canvas = document.getElementById('category-revenue-canvas');
    if (!canvas) return;

    const labels = catData.labels || [];
    const values = catData.values || [];

    if (!labels.length) {
        document.getElementById('category-revenue-card')?.style.setProperty('display', 'none');
        return;
    }
    document.getElementById('category-revenue-card')?.style.setProperty('display', 'block');

    if (window.catRevChartInstance) { window.catRevChartInstance.destroy(); }

    // Track selected category (null = all)
    window._selectedCategory = window._selectedCategory || null;

    const baseColors = labels.map((_, i) =>
        window._selectedCategory === labels[i] ? '#2563eb' : '#D1D5DB'
    );

    const ctx = canvas.getContext('2d');
    window.catRevChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Revenue',
                data: values,
                backgroundColor: baseColors,
                borderRadius: 4,
                borderSkipped: false,
                barThickness: 12
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            onClick(evt, elements) {
                if (!elements.length) return;
                const clickedLabel = labels[elements[0].index];
                // Toggle: click same category to reset
                if (window._selectedCategory === clickedLabel) {
                    window._selectedCategory = null;
                    applyDashboardFilter(null, fullReport || APP.lastReport);
                } else {
                    window._selectedCategory = clickedLabel;
                    applyDashboardFilter(clickedLabel, fullReport || APP.lastReport);
                }
                // Re-render bar chart to update highlight colors
                renderCategoryRevenueChart(catData, fullReport || APP.lastReport);
            },
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: window._selectedCategory
                        ? `📈 Category: ${window._selectedCategory}  ✕ (click to reset)`
                        : 'Revenue by Category — click a bar to filter',
                    color: '#344054',
                    font: { size: 13, weight: '600' }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => ' ' + formatCurrency(ctx.parsed.x)
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: '#667085', callback: v => formatCurrency(v) }
                },
                y: {
                    grid: { display: false },
                    ticks: { color: '#667085', font: { size: 11 } }
                }
            }
        }
    });
}

// ── Apply dashboard filter by category ────────────────────────
function applyDashboardFilter(category, report) {
    if (!report) return;
    const analysis = report.analysis || {};

    // ── Sales Trend line chart ─────────────────────────────────
    const yearly = analysis.yearly_trend || {};
    if (category) {
        const byCategory = yearly.by_category || {};
        const catValues = byCategory[category];
        const years = yearly.years || yearly.labels || [];
        if (catValues && years.length) {
            renderYearlySalesChart({ labels: years, values: catValues }, null, `Sales Trend — ${category}`);
        } else {
            renderYearlySalesChart({ labels: [], values: [] }, null, '');
        }
    } else {
        renderYearlySalesChart(yearly, null, 'Yearly Sales Trend');
    }

    // ── KPI cards ─────────────────────────────────────────────
    const kpiGrid = document.getElementById('analytics-kpi-grid');
    if (kpiGrid) {
        const catKpis = category
            ? (analysis.category_kpis || {})[category]
            : null;
        const kpis = catKpis || analysis.kpis || {};
        const growthValue = kpis.yearly_growth_pct ?? kpis.growth_rate_pct ?? 0;
        const growthLabel = kpis.yearly_growth_pct != null ? 'vs last year' : 'vs last period';
        const isPositive = growthValue >= 0;
        const growthHtml = `
            <div class="kpi-indicator ${isPositive ? 'positive':'negative'}">
               <span class="material-icons-outlined">${isPositive ? 'trending_up':'trending_down'}</span>
               ${Math.abs(growthValue)}%
               <span class="indicator-label">${growthLabel}</span>
            </div>`;
        kpiGrid.innerHTML = `
            <div class="kpi-card"><div class="kpi-card-content">
                <div class="kpi-label"><span class="material-icons-outlined">payments</span> ${category ? category + ' Revenue' : 'Total Revenue'}</div>
                <div class="kpi-value">${formatCurrency(kpis.total || 0)}</div>
                ${growthHtml}
            </div></div>
            <div class="kpi-card"><div class="kpi-card-content">
                <div class="kpi-label"><span class="material-icons-outlined">trending_up</span> Total Profit</div>
                <div class="kpi-value">${formatCurrency(kpis.total_profit || 0)}</div>
                <div class="kpi-indicator ${isPositive ? 'positive' : 'negative'}">
                    <span class="material-icons-outlined">${isPositive ? 'trending_up' : 'trending_down'}</span>
                    ${Math.abs(Math.round(growthValue * 0.8))}%
                    <span class="indicator-label">${growthLabel}</span>
                </div>
            </div></div>
            <div class="kpi-card"><div class="kpi-card-content">
                <div class="kpi-label"><span class="material-icons-outlined">shopping_cart</span> Total Orders</div>
                <div class="kpi-value">${formatNumber(kpis.total_orders || 0)}</div>
                <div class="kpi-indicator ${isPositive ? 'positive' : 'negative'}">
                    <span class="material-icons-outlined">${isPositive ? 'trending_up' : 'trending_down'}</span>
                    ${Math.abs(Math.round(growthValue * 1.2))}%
                    <span class="indicator-label">${growthLabel}</span>
                </div>
            </div></div>
            <div class="kpi-card"><div class="kpi-card-content">
                <div class="kpi-label"><span class="material-icons-outlined">assignment_return</span> Return Rate</div>
                <div class="kpi-value">${kpis.return_rate != null ? kpis.return_rate + '%' : 'N/A'}</div>
                <div class="kpi-indicator ${kpis.return_rate > 5 ? 'negative' : 'positive'}">
                    <span class="material-icons-outlined">${kpis.return_rate > 5 ? 'trending_up' : 'trending_down'}</span>
                    ${kpis.return_rate > 5 ? 'Needs Attention' : 'Stable'}
                    <span class="indicator-label">risk level</span>
                </div>
            </div></div>
        `;
    }

    // ── Top Customers & Ordered Products ─────────────────────
    const topCustsEl = document.getElementById('top-customers-list');
    const topOrdEl = document.getElementById('top-ordered-products-list');
    const customersRow = document.getElementById('dashboard-customers-row');
    
    if (customersRow) {
        const allCustomers = analysis.top_customers || [];
        const allOrdered = analysis.top_ordered_products || [];
        
        const catCustomers = category
            ? (analysis.customers_by_category || {})[category] || allCustomers
            : allCustomers;
            
        const catOrdered = category
            ? (analysis.products_by_category || {})[category] || allOrdered
            : allOrdered;

        if (catCustomers.length || catOrdered.length) {
            customersRow.style.setProperty('display', 'flex');
            
            if (topCustsEl && catCustomers.length) {
                document.getElementById('top-customers-card')?.style.setProperty('display', 'flex');
                topCustsEl.innerHTML = catCustomers.map((c, i) => `
                    <div class="product-item-compact">
                        <div class="product-rank">${i + 1}</div>
                        <div class="product-name">${escapeHtml(c.name)}</div>
                        <div class="product-value" style="color:var(--primary)">${formatCurrency(c.revenue)}</div>
                    </div>
                `).join('');
            } else {
                document.getElementById('top-customers-card')?.style.setProperty('display', 'none');
            }

            if (topOrdEl && catOrdered.length) {
                document.getElementById('top-ordered-card')?.style.setProperty('display', 'flex');
                topOrdEl.innerHTML = catOrdered.map((p, i) => `
                    <div class="product-item-compact">
                        <div class="product-rank">${i + 1}</div>
                        <div class="product-name">${escapeHtml(p.name)}</div>
                        <div class="product-value" style="color:var(--secondary)">${formatNumber(p.value)} units</div>
                    </div>
                `).join('');
            } else {
                document.getElementById('top-ordered-card')?.style.setProperty('display', 'none');
            }
        } else {
            customersRow.style.setProperty('display', 'none');
        }
    }

    // ── Sentiment ─────────────────────────────────────────────
    const sentContainer = document.getElementById('sentiment-overview-container');
    if (sentContainer) {
        const sent = category
            ? (analysis.sentiment_by_category || {})[category] || analysis.sentiment
            : analysis.sentiment;
        if (sent && sent.distribution && sent.total_analyzed > 0) {
            sentContainer.style.display = 'block';
            renderSentimentOverview(sentContainer, sent);
        } else if (!category) {
            sentContainer.style.display = 'none';
        }
    }

    // ── Risk products ─────────────────────────────────────────
    const riskContainer = document.getElementById('risk-analysis-container');
    const riskProdsEl = document.getElementById('risk-products-list');
    const riskSolsEl = document.getElementById('risk-solutions-list');
    if (riskContainer && riskProdsEl && riskSolsEl) {
        const allRisk = analysis.risk_products || [];
        const catRisk = category
            ? allRisk.filter(p => (p.category || '').toLowerCase() === category.toLowerCase())
            : allRisk;
        if (catRisk.length) {
            riskContainer.style.display = 'block';
            riskProdsEl.innerHTML = catRisk.map(p => `
                <div class="risk-product-item">
                    <span class="material-icons-outlined" style="font-size:16px; color:var(--error)">warning</span>
                    <span class="risk-product-name">${escapeHtml(p.name)}</span>
                </div>
            `).join('');
            riskSolsEl.innerHTML = catRisk.map(p => `
                <div class="risk-solution-item">
                    <div class="risk-sol-header">
                        <strong>Issue with ${escapeHtml(p.name)}</strong>
                        <span class="chip chip-danger" style="font-size:10px">High Risk</span>
                    </div>
                    <p class="risk-sol-text">${escapeHtml(p.solution)}</p>
                </div>
            `).join('');
        } else {
            riskContainer.style.display = category ? 'none' : 'block';
        }
    }

    // ── Future Prediction chart ────────────────────────────────
    const forecast = analysis.future_forecast;
    const predContainer = document.getElementById('prediction-container');
    if (forecast && forecast.forecast_values?.length && predContainer) {
        predContainer.style.display = 'block';
        renderFuturePredictionChart(forecast);
    }

    // ── Filter banner ─────────────────────────────────────────
    let banner = document.getElementById('filter-banner');
    if (category) {
        if (!banner) {
            banner = document.createElement('div');
            banner.id = 'filter-banner';
            banner.style.cssText = 'position:sticky;top:0;z-index:100;background:rgba(37,99,235,0.92);color:#fff;padding:10px 20px;display:flex;align-items:center;justify-content:space-between;font-size:13px;font-weight:600;backdrop-filter:blur(6px);border-radius:0 0 10px 10px;margin-bottom:8px;';
            const resultsArea = document.getElementById('analytics-results');
            resultsArea?.insertAdjacentElement('afterbegin', banner);
        }
        banner.innerHTML = `
            <span>🔍 Filtering by category: <b>${escapeHtml(category)}</b></span>
            <button onclick="window._selectedCategory=null; applyDashboardFilter(null, APP.lastReport); renderCategoryRevenueChart(APP.lastReport?.analysis?.category_revenue||{}, APP.lastReport);" 
                style="background:rgba(255,255,255,0.2);border:1px solid rgba(255,255,255,0.4);color:#fff;padding:4px 12px;border-radius:6px;cursor:pointer;font-size:12px;">
                ✕ Reset Filter
            </button>`;
    } else {
        banner?.remove();
    }
}

async function sendAnalyticsMessage(question) {
    const messages = document.getElementById('analytics-messages');
    if (!messages) return;

    messages.innerHTML += `<div class="chat-msg user">${escapeHtml(question)}</div>`;
    const lid = 'alid-' + Date.now();
    messages.innerHTML += `<div class="chat-msg ai" id="${lid}"><div class="spinner"></div> Searching your data...</div>`;
    messages.scrollTop = messages.scrollHeight;

    const bodyPayload = { question };
    if (APP.currentFilename) {
        bodyPayload.filename = APP.currentFilename;
    }

    const data = await apiFetch('/chat', { method: 'POST', body: JSON.stringify(bodyPayload) });
    const el = document.getElementById(lid);
    if (el) {
        const answer = data.error || data.answer || 'Unable to process.';
        const sources = data.sources?.length
            ? `<div class="sources">📄 Sources: ${data.sources.join(', ')}</div>` : '';
        el.innerHTML = `${escapeHtml(answer)}${sources}`;
    }
    messages.scrollTop = messages.scrollHeight;
}

async function loadUploads() {
    const list = document.getElementById('uploads-list');
    if (!list) return;

    const data = await apiFetch('/uploads');
    const files = data.files || [];

    if (files.length === 0) {
        list.innerHTML = '<p class="text-muted body-md" style="padding:16px 0">No files uploaded yet. Upload a CSV to get started.</p>';
        return;
    }

    list.innerHTML = `
        <table class="uploads-table">
            <thead>
                <tr>
                    <th>Filename</th>
                    <th>Size</th>
                    <th>Uploaded</th>
                    <th>Status</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${files.map(f => `
                    <tr>
                        <td><span class="file-icon"><span class="material-icons-outlined">description</span>${escapeHtml(f.filename)}</span></td>
                        <td>${f.size}</td>
                        <td>${timeAgo(f.uploaded_at)}</td>
                        <td><span class="chip chip-success">Ingested</span></td>
                        <td>
                            <div style="display:flex; gap:8px">
                                <button class="btn btn-primary btn-sm btn-load-report" data-id="${f.file_id}" data-filename="${escapeHtml(f.filename)}" style="padding: 4px 12px; font-size: 12px">
                                    View Analysis
                                </button>
                                <button class="btn btn-outline btn-sm btn-delete-upload" data-id="${f.file_id}" style="padding: 4px 8px; font-size: 12px; border-color: #fee2e2; color: #ef4444">
                                    <span class="material-icons-outlined" style="font-size:16px">delete</span>
                                </button>
                            </div>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    list.querySelectorAll('.btn-load-report').forEach(btn => {
        btn.addEventListener('click', async () => {
            const fid = btn.getAttribute('data-id');
            const fname = btn.getAttribute('data-filename');
            
            // Temporary hack to decode escaped HTML quotes if any, although escapeHtml handles tags
            APP.currentFilename = fname;
            
            showToast('Fetching analysis results...', 'info');
            const report = await apiFetch(`/report/${fid}`);
            if (report.error) {
                showToast('Report not found. You may need to run analysis first.', 'warning');
            } else {
                const chatSubtitle = document.getElementById('chat-subtitle');
                if (chatSubtitle) {
                    chatSubtitle.innerHTML = `Chatting with: <b style="color:var(--primary)">${escapeHtml(fname)}</b>`;
                }
                renderPipelineResults(report);
            }
        });
    });

    list.querySelectorAll('.btn-delete-upload').forEach(btn => {
        btn.addEventListener('click', async () => {
            const fid = btn.getAttribute('data-id');
            if (!confirm('Are you sure you want to delete this data source and its analysis?')) return;
            showToast('Deleting...', 'info');
            const res = await apiFetch(`/upload/${fid}`, { method: 'DELETE' });
            if (!res.error) {
                showToast('Deleted successfully', 'success');
                loadUploads();
            }
        });
    });
}

// ============================================
// HISTORY PAGE
// ============================================
function renderHistoryPage(container) {
    container.innerHTML = `
        <div class="page-header">
            <div class="page-header-row">
                <div>
                    <h1 class="page-title">History</h1>
                    <p class="page-subtitle">View your data ingestion history and system activity.</p>
                </div>
            </div>
        </div>
        <div class="page-body">
            <div class="card">
                <div class="card-header">
                    <div>
                        <div class="card-title">Ingested Data Sources</div>
                        <div class="card-subtitle">All files processed through the RAG pipeline</div>
                    </div>
                </div>
                <div id="history-list">
                    <div class="skeleton skeleton-text" style="height:40px;margin-top:8px"></div>
                </div>
            </div>
        </div>
    `;
    loadHistoryData();
}

async function loadHistoryData() {
    const list = document.getElementById('history-list');
    if (!list) return;
    const data = await apiFetch('/uploads');
    const files = data.files || [];
    if (files.length === 0) {
        list.innerHTML = '<p class="text-muted body-md" style="padding:16px 0">No history yet.</p>';
        return;
    }
    list.innerHTML = `
        <table class="uploads-table">
            <thead><tr><th>File</th><th>Size</th><th>Processed</th><th>Status</th></tr></thead>
            <tbody>
                ${files.map(f => `
                    <tr>
                        <td><span class="file-icon"><span class="material-icons-outlined">description</span>${escapeHtml(f.filename)}</span></td>
                        <td>${f.size}</td>
                        <td>${timeAgo(f.uploaded_at)}</td>
                        <td><span class="chip chip-success">Complete</span></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// ── Sentiment Overview (Image-Style) ───────────────────────
function renderSentimentOverview(container, sentData) {
    const dist = sentData.distribution;
    const total = sentData.total_analyzed || 0;
    const satisfiedPct = sentData.Satisfied_pct || 0;
    const needsAttentionPct = sentData.NeedsAttention_pct || 0;

    container.innerHTML = `
        <div class="card sentiment-overview-card">
            <div class="sentiment-header">
                <h3 class="sentiment-main-title">Customer Sentiment Overview</h3>
                <p class="sentiment-subtitle">All Categories</p>
            </div>
            
            <div class="sentiment-body">
                <!-- Left Card -->
                <div class="sentiment-side-card left">
                    <div class="sentiment-pct-large">${satisfiedPct}%</div>
                    <div class="sentiment-cat-title">Satisfied Customers</div>
                    <div class="sentiment-cat-desc">Excellent product quality and outstanding customer service experience</div>
                </div>

                <!-- Center Donut -->
                <div class="sentiment-donut-wrapper">
                    <canvas id="sentiment-donut-canvas-large"></canvas>
                    <div class="sentiment-donut-center">
                        <div class="donut-center-value">${formatNumber(total)}</div>
                        <div class="donut-center-label">Total Reviews</div>
                    </div>
                </div>

                <!-- Right Card -->
                <div class="sentiment-side-card right">
                    <div class="sentiment-pct-large">${needsAttentionPct}%</div>
                    <div class="sentiment-cat-title">Areas for Improvement</div>
                    <div class="sentiment-cat-desc">Customer feedback highlighting opportunities for enhancement</div>
                </div>
            </div>

            <!-- Bottom Legend Cards -->
            <div class="sentiment-footer">
                <div class="sentiment-legend-item">
                    <span class="legend-dot satisfied"></span>
                    <div class="legend-content">
                        <div class="legend-name">Satisfied</div>
                        <div class="legend-val">${satisfiedPct}% • ${formatNumber(dist.Satisfied)} reviews</div>
                    </div>
                </div>
                <div class="sentiment-legend-item">
                    <span class="legend-dot neutral"></span>
                    <div class="legend-content">
                        <div class="legend-name">Neutral</div>
                        <div class="legend-val">${round(100 - satisfiedPct - needsAttentionPct, 1)}% • ${formatNumber(dist.Neutral)} reviews</div>
                    </div>
                </div>
                <div class="sentiment-legend-item">
                    <span class="legend-dot needs-attention"></span>
                    <div class="legend-content">
                        <div class="legend-name">Needs Attention</div>
                        <div class="legend-val">${needsAttentionPct}% • ${formatNumber(dist["Needs Attention"])} reviews</div>
                    </div>
                </div>
            </div>
        </div>
    `;

    setTimeout(() => {
        const canvas = document.getElementById('sentiment-donut-canvas-large');
        if (!canvas) return;
        new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: ['Satisfied', 'Neutral', 'Needs Attention'],
                datasets: [{
                    data: [dist.Satisfied, dist.Neutral, dist["Needs Attention"]],
                    backgroundColor: ['#22c55e', '#3b82f6', '#ef4444'],
                    borderWidth: 0,
                    hoverOffset: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '80%',
                plugins: { legend: { display: false }, tooltip: { enabled: true } }
            }
        });
    }, 100);
}


// ── KPI Background Sparkline ──────────────────────────────────
function renderKPISparkline(canvasId, data, color) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
    grad.addColorStop(0, color + '33');
    grad.addColorStop(1, color + '00');

    new Chart(canvas, {
        type: 'line',
        data: {
            labels: data.map((_, i) => i),
            datasets: [{
                data: data,
                borderColor: color,
                borderWidth: 2,
                tension: 0.4,
                pointRadius: 0,
                fill: true,
                backgroundColor: grad
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            scales: {
                x: { display: false },
                y: { display: false, beginAtZero: false }
            },
            layout: { padding: { bottom: -10, left: -10, right: -10 } }
        }
    });
}


// ============================================
// ACCOUNT PAGE
// ============================================
function renderAccountPage(container) {
    container.innerHTML = `
        <div class="page-header">
            <div class="page-header-row">
                <div>
                    <h1 class="page-title">Account</h1>
                    <p class="page-subtitle">Manage your profile and preferences.</p>
                </div>
            </div>
        </div>
        <div class="page-body">
            <div class="card" style="max-width:600px">
                <div class="card-header">
                    <div class="card-title">Profile Information</div>
                </div>
                <div style="display:flex;align-items:center;gap:20px;margin-bottom:24px">
                    <div class="user-avatar" style="width:64px;height:64px;font-size:24px">${userInitials()}</div>
                    <div>
                        <div style="font-size:20px;font-weight:600">${escapeHtml(APP.user?.name || 'User')}</div>
                        <div class="text-muted">${escapeHtml(APP.user?.email || '')}</div>
                    </div>
                </div>
                <div style="margin-top:24px;padding-top:24px;border-top:1px solid var(--outline-variant)">
                    <button class="btn btn-secondary" id="account-logout">
                        <span class="material-icons-outlined" style="font-size:18px">logout</span>
                        Sign Out
                    </button>
                </div>
            </div>
        </div>
    `;
    document.getElementById('account-logout')?.addEventListener('click', () => {
        logout();
        showToast('Logged out successfully', 'info');
    });
}

// ============================================
// UTILITIES
// ============================================
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ============================================
// INIT
// ============================================
window.addEventListener('hashchange', render);
document.addEventListener('DOMContentLoaded', render);

let predictionChart = null;
function renderFuturePredictionChart(forecast) {
    const ctx = document.getElementById('prediction-chart')?.getContext('2d');
    if (!ctx) return;

    if (predictionChart) predictionChart.destroy();

    const histLabels = forecast.historical_labels || [];
    const histValues = forecast.historical_values || [];
    const forecastLabels = forecast.forecast_labels || [];
    const forecastValues = forecast.forecast_values || [];

    // Combine for a continuous line
    const allLabels = [...histLabels, ...forecastLabels];
    
    // Dataset 1: Historical (ends at last hist point)
    const histData = [...histValues];
    
    // Dataset 2: Forecast (starts at last hist point)
    const predData = new Array(histValues.length - 1).fill(null);
    predData.push(histValues[histValues.length - 1]); // bridge point
    predData.push(...forecastValues);

    const boostBadge = document.getElementById('forecast-boost-badge');
    const boostVal = document.getElementById('forecast-boost-val');
    if (boostBadge && boostVal && forecast.avg_recovery_boost) {
        boostBadge.style.display = 'flex';
        boostVal.textContent = formatCurrency(forecast.avg_recovery_boost) + '/mo';
    }

    predictionChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: allLabels,
            datasets: [
                {
                    label: 'Historical Sales',
                    data: histData,
                    borderColor: '#2563EB',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    borderWidth: 3,
                    pointRadius: 4,
                    pointBackgroundColor: '#2563EB',
                    tension: 0,
                    fill: true
                },
                {
                    label: 'Future Trend (Risk Resolved)',
                    data: predData,
                    borderColor: '#F59E0B',
                    borderDash: [5, 5],
                    borderWidth: 3,
                    pointRadius: 4,
                    pointBackgroundColor: '#F59E0B',
                    tension: 0,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: { 
                    display: true, 
                    position: 'top',
                    labels: { color: '#f8fafc', font: { family: 'Inter', size: 12 } }
                },
                tooltip: {
                    backgroundColor: '#1e293b',
                    titleColor: '#f8fafc',
                    bodyColor: '#cbd5e1',
                    padding: 12,
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + formatCurrency(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                y: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#94a3b8', font: { size: 11 }, callback: (v) => formatCurrency(v) }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8', font: { size: 11 } }
                }
            }
        }
    });
}
