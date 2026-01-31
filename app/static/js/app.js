// Smart Mover - Frontend JavaScript

// ============================================
// Mobile Navigation
// ============================================

function toggleNav() {
    const navLinks = document.getElementById('nav-links');
    if (navLinks) {
        navLinks.classList.toggle('open');
    }
}

// Close mobile nav when clicking a link
document.addEventListener('DOMContentLoaded', function() {
    const navLinks = document.querySelectorAll('.nav-links a');
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            const nav = document.getElementById('nav-links');
            if (nav) nav.classList.remove('open');
        });
    });
});

// ============================================
// Utility Functions
// ============================================

function showAlert(message, type = 'info') {
    const container = document.getElementById('alert-container');
    if (!container) return;

    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = message;

    container.innerHTML = '';
    container.appendChild(alert);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alert.remove();
    }, 5000);
}

function formatBytes(gb) {
    return gb.toFixed(1) + ' GB';
}

function formatSizeBytes(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    const size = bytes / Math.pow(1024, i);
    return size.toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
}

function formatDuration(seconds) {
    if (seconds < 60) {
        return seconds.toFixed(1) + 's';
    }
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}m ${secs}s`;
}

function formatDateTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString();
}

function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (!element) {
        console.error('Element not found:', elementId);
        return;
    }

    const text = element.textContent || element.innerText;

    if (!text || text.trim() === '') {
        showAlert('Nothing to copy', 'info');
        return;
    }

    // Try modern clipboard API first
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            showAlert('Copied to clipboard!', 'success');
        }).catch(err => {
            console.error('Clipboard API failed:', err);
            fallbackCopy(text);
        });
    } else {
        // Fallback for non-secure contexts (HTTP)
        fallbackCopy(text);
    }
}

function fallbackCopy(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    textarea.style.top = '0';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();

    try {
        const successful = document.execCommand('copy');
        if (successful) {
            showAlert('Copied to clipboard!', 'success');
        } else {
            showAlert('Failed to copy', 'error');
        }
    } catch (err) {
        console.error('Fallback copy failed:', err);
        showAlert('Failed to copy: ' + err.message, 'error');
    }

    document.body.removeChild(textarea);
}

// Parse cron schedule and calculate next run time
function getNextRunTime(cronExpression) {
    if (!cronExpression) return null;

    const parts = cronExpression.split(' ');
    if (parts.length !== 5) return null;

    const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;
    const now = new Date();

    // Simple parser for common cron patterns
    // Handle "0 */6 * * *" (every 6 hours) pattern
    if (hour.startsWith('*/')) {
        const interval = parseInt(hour.substring(2));
        const currentHour = now.getHours();
        const nextHour = Math.ceil((currentHour + 1) / interval) * interval;

        const nextRun = new Date(now);
        nextRun.setMinutes(parseInt(minute) || 0);
        nextRun.setSeconds(0);
        nextRun.setMilliseconds(0);

        if (nextHour >= 24) {
            nextRun.setDate(nextRun.getDate() + 1);
            nextRun.setHours(0);
        } else if (nextHour <= currentHour && now.getMinutes() >= (parseInt(minute) || 0)) {
            nextRun.setHours(nextHour + interval >= 24 ? interval : nextHour + interval);
            if (nextRun.getHours() < currentHour) {
                nextRun.setDate(nextRun.getDate() + 1);
            }
        } else {
            nextRun.setHours(nextHour);
        }

        return nextRun;
    }

    // Handle specific hour "0 3 * * *" (at 3:00 AM)
    if (!isNaN(parseInt(hour))) {
        const targetHour = parseInt(hour);
        const targetMinute = parseInt(minute) || 0;

        const nextRun = new Date(now);
        nextRun.setHours(targetHour);
        nextRun.setMinutes(targetMinute);
        nextRun.setSeconds(0);
        nextRun.setMilliseconds(0);

        if (nextRun <= now) {
            nextRun.setDate(nextRun.getDate() + 1);
        }

        return nextRun;
    }

    return null;
}

function formatRelativeTime(date) {
    if (!date) return '';

    const now = new Date();
    const diff = date - now;
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (hours > 0) {
        return `Next run in ${hours}h ${minutes}m`;
    } else if (minutes > 0) {
        return `Next run in ${minutes}m`;
    } else {
        return 'Next run soon';
    }
}

// ============================================
// Dashboard Functions
// ============================================

async function loadCacheUsage() {
    try {
        const response = await fetch('/api/cache-usage');
        const data = await response.json();

        // Update hero percentage display
        const percentage = document.getElementById('cache-percentage');
        if (percentage) {
            percentage.textContent = Math.round(data.percent_used) + '%';
            percentage.classList.remove('warning', 'critical');
            if (data.percent_used >= 90) {
                percentage.classList.add('critical');
            } else if (data.above_threshold) {
                percentage.classList.add('warning');
            }
        }

        // Update bar
        const fill = document.getElementById('cache-bar-fill');
        const threshold = document.getElementById('cache-bar-threshold');

        if (fill) {
            fill.style.width = data.percent_used + '%';
            fill.classList.remove('warning', 'critical');
            if (data.percent_used >= 90) {
                fill.classList.add('critical');
            } else if (data.above_threshold) {
                fill.classList.add('warning');
            }
        }

        if (threshold) {
            threshold.style.left = data.threshold + '%';
        }

        // Update stats
        const used = document.getElementById('cache-used');
        const free = document.getElementById('cache-free');

        if (used) used.textContent = formatBytes(data.used_gb) + ' used';
        if (free) free.textContent = formatBytes(data.free_gb) + ' free';

        // Show/hide threshold notice
        const thresholdNotice = document.getElementById('threshold-notice');
        const nextRunTime = document.getElementById('next-run-time');

        if (thresholdNotice) {
            if (data.above_threshold) {
                thresholdNotice.classList.remove('hidden');

                // Fetch schedule settings to show next run time
                try {
                    const settingsResponse = await fetch('/api/settings');
                    const settings = await settingsResponse.json();

                    if (settings.schedule_enabled && settings.schedule_cron && nextRunTime) {
                        const nextRun = getNextRunTime(settings.schedule_cron);
                        if (nextRun) {
                            nextRunTime.textContent = formatRelativeTime(nextRun);
                        } else {
                            nextRunTime.textContent = '';
                        }
                    } else if (nextRunTime) {
                        nextRunTime.textContent = settings.schedule_enabled ? '' : '(Scheduled runs disabled)';
                    }
                } catch (e) {
                    console.error('Failed to load settings:', e);
                }
            } else {
                thresholdNotice.classList.add('hidden');
            }
        }

    } catch (error) {
        console.error('Failed to load cache usage:', error);
    }
}

// Global status polling interval
let globalStatusInterval = null;

// Update global nav indicator (works on all pages)
function updateGlobalRunStatus(isRunning) {
    const globalStatus = document.getElementById('global-run-status');
    if (globalStatus) {
        if (isRunning) {
            globalStatus.classList.remove('hidden');
            // Start polling if not already
            if (!globalStatusInterval) {
                globalStatusInterval = setInterval(checkGlobalRunStatus, 2000);
            }
        } else {
            globalStatus.classList.add('hidden');
            // Stop polling
            if (globalStatusInterval) {
                clearInterval(globalStatusInterval);
                globalStatusInterval = null;
            }
        }
    }
}

// Check status globally (called on all pages)
async function checkGlobalRunStatus() {
    try {
        const response = await fetch('/api/run/status');
        const data = await response.json();
        updateGlobalRunStatus(data.is_running);
        return data;
    } catch (error) {
        console.error('Failed to check run status:', error);
        return null;
    }
}

// Polling interval for dashboard status updates
let dashboardStatusInterval = null;

async function loadRunStatus() {
    try {
        const response = await fetch('/api/run/status');
        const data = await response.json();

        // Update global nav indicator
        updateGlobalRunStatus(data.is_running);

        // Update dashboard-specific elements
        const runStatus = document.getElementById('run-status');
        const runBtn = document.getElementById('run-btn');
        const currentStatusEl = document.getElementById('current-status');

        if (data.is_running) {
            if (runStatus) runStatus.classList.remove('hidden');
            if (runBtn) runBtn.disabled = true;

            // Update current status text
            if (currentStatusEl && data.current_status) {
                currentStatusEl.textContent = data.current_status;
            }

            // Start polling for status updates if not already
            if (!dashboardStatusInterval) {
                dashboardStatusInterval = setInterval(async () => {
                    const statusResp = await fetch('/api/run/status');
                    const statusData = await statusResp.json();

                    if (currentStatusEl && statusData.current_status) {
                        currentStatusEl.textContent = statusData.current_status;
                    }

                    if (!statusData.is_running) {
                        clearInterval(dashboardStatusInterval);
                        dashboardStatusInterval = null;
                        loadRunStatus(); // Refresh final state
                    }
                }, 1000);
            }
        } else {
            if (runStatus) runStatus.classList.add('hidden');
            if (runBtn) runBtn.disabled = false;

            // Stop polling
            if (dashboardStatusInterval) {
                clearInterval(dashboardStatusInterval);
                dashboardStatusInterval = null;
            }
        }

        // Update last run stats
        if (data.last_run) {
            const lr = data.last_run;
            const statStatus = document.getElementById('stat-status');
            const statMode = document.getElementById('stat-mode');
            const statDuration = document.getElementById('stat-duration');
            const lastRunTime = document.getElementById('last-run-time');

            if (statStatus) {
                statStatus.textContent = lr.success ? 'Success' : 'Failed';
                statStatus.className = 'stat-value ' + (lr.success ? 'text-success' : 'text-error');
            }

            if (statMode) {
                statMode.textContent = lr.dry_run ? 'Dry Run' : 'Live';
            }

            if (statDuration) {
                statDuration.textContent = formatDuration(lr.duration_seconds);
            }

            if (lastRunTime) {
                lastRunTime.textContent = formatDateTime(lr.start_time);
            }
        }
    } catch (error) {
        console.error('Failed to load run status:', error);
    }
}

async function runScript() {
    const dryRun = document.getElementById('dry-run-toggle')?.checked ?? true;
    const runBtn = document.getElementById('run-btn');
    const runStatus = document.getElementById('run-status');

    // Update UI
    if (runBtn) runBtn.disabled = true;
    if (runStatus) runStatus.classList.remove('hidden');
    updateGlobalRunStatus(true);

    try {
        // Start the script (returns immediately)
        const response = await fetch('/api/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dry_run: dryRun })
        });

        const data = await response.json();

        if (!data.started) {
            showAlert(data.message, 'error');
            if (runBtn) runBtn.disabled = false;
            if (runStatus) runStatus.classList.add('hidden');
            updateGlobalRunStatus(false);
            return;
        }

        // Poll for completion and update status
        const currentStatusEl = document.getElementById('current-status');
        const pollInterval = setInterval(async () => {
            const statusResponse = await fetch('/api/run/status');
            const status = await statusResponse.json();

            // Update current status display
            if (currentStatusEl && status.current_status) {
                currentStatusEl.textContent = status.current_status;
            }

            if (!status.is_running) {
                clearInterval(pollInterval);

                // Script completed - update UI
                if (runBtn) runBtn.disabled = false;
                if (runStatus) runStatus.classList.add('hidden');
                updateGlobalRunStatus(false);

                // Show result
                if (status.last_run) {
                    if (status.last_run.success) {
                        showAlert('Script completed successfully!', 'success');
                    } else {
                        showAlert('Script failed. Check logs for details.', 'error');
                    }
                }

                // Refresh data
                await loadRunStatus();
                await loadRecentLogs();
                await loadCacheUsage();
            }
        }, 1000);

    } catch (error) {
        showAlert('Error starting script: ' + error.message, 'error');
        if (runBtn) runBtn.disabled = false;
        if (runStatus) runStatus.classList.add('hidden');
        updateGlobalRunStatus(false);
    }
}

async function loadRecentLogs() {
    try {
        const response = await fetch('/api/logs?lines=50');
        const data = await response.json();

        const recentLogs = document.getElementById('recent-logs');
        if (recentLogs) {
            recentLogs.textContent = data.content || '';
        }
    } catch (error) {
        console.error('Failed to load recent logs:', error);
    }
}

// ============================================
// Settings Functions
// ============================================

function updateThresholdDisplay(value) {
    const display = document.getElementById('threshold-display');
    const label = document.getElementById('threshold-value');
    if (display) display.textContent = value + '%';
    if (label) label.textContent = value + '%';
}

function toggleScheduleOptions() {
    const enabled = document.getElementById('schedule_enabled')?.checked;
    const options = document.getElementById('schedule-options');
    if (options) {
        options.classList.toggle('hidden', !enabled);
    }
}

async function saveSettings(event) {
    event.preventDefault();

    const saveBtn = document.getElementById('save-btn');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';
    }

    try {
        // Gather form data
        const apiKeyValue = document.getElementById('jellyfin_api_key')?.value || '';

        const settings = {
            jellyfin_url: document.getElementById('jellyfin_url')?.value || '',
            jellyfin_user_ids: document.getElementById('jellyfin_user_ids')?.value || '',
            cache_threshold: parseInt(document.getElementById('cache_threshold')?.value || '90'),
            cache_drive: document.getElementById('cache_drive')?.value || '/mnt/cache',
            array_path: document.getElementById('array_path')?.value || '/mnt/disk1',
            movies_pool: document.getElementById('movies_pool')?.value || 'movies-pool',
            tv_pool: document.getElementById('tv_pool')?.value || 'tv-pool',
            jellyfin_path_prefix: document.getElementById('jellyfin_path_prefix')?.value || '',
            local_path_prefix: document.getElementById('local_path_prefix')?.value || '',
            dry_run: document.getElementById('dry_run')?.checked ?? true,
            debug: document.getElementById('debug')?.checked ?? false,
            log_level: document.getElementById('log_level')?.value || 'INFO',
            schedule_enabled: document.getElementById('schedule_enabled')?.checked ?? false,
            schedule_cron: document.getElementById('schedule_cron')?.value || '0 */6 * * *'
        };

        // Only include API key if user entered a new value (non-empty)
        // This prevents overwriting the saved key when field is left blank
        if (apiKeyValue.trim()) {
            settings.jellyfin_api_key = apiKeyValue;
        }

        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        const data = await response.json();

        if (response.ok) {
            showAlert('Settings saved successfully!', 'success');
        } else {
            showAlert('Failed to save settings: ' + (data.detail || data.message), 'error');
        }

    } catch (error) {
        showAlert('Error saving settings: ' + error.message, 'error');
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save Settings';
        }
    }
}

// ============================================
// Logs Functions
// ============================================

let autoRefreshInterval = null;

async function loadLogs() {
    try {
        const levelFilter = document.getElementById('log-level-filter')?.value || '';
        let url = '/api/logs';
        if (levelFilter) {
            url += `?level=${levelFilter}`;
        }

        const response = await fetch(url);
        const data = await response.json();

        const logContent = document.getElementById('log-content');
        const lineCount = document.getElementById('log-line-count');

        if (logContent) {
            logContent.textContent = data.content || '';
            // Scroll to bottom
            logContent.parentElement.scrollTop = logContent.parentElement.scrollHeight;
        }

        if (lineCount) {
            lineCount.textContent = data.lines + ' lines';
        }

    } catch (error) {
        console.error('Failed to load logs:', error);
    }
}

function toggleAutoRefresh() {
    const enabled = document.getElementById('auto-refresh')?.checked;

    if (enabled) {
        autoRefreshInterval = setInterval(loadLogs, 3000);
    } else {
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = null;
        }
    }
}

async function clearLogs() {
    if (!confirm('Are you sure you want to clear all logs?')) {
        return;
    }

    try {
        const response = await fetch('/api/logs', { method: 'DELETE' });
        const data = await response.json();

        if (response.ok) {
            showAlert('Logs cleared successfully!', 'success');
            await loadLogs();
        } else {
            showAlert('Failed to clear logs: ' + data.detail, 'error');
        }

    } catch (error) {
        showAlert('Error clearing logs: ' + error.message, 'error');
    }
}

// ============================================
// Run History Functions
// ============================================

async function loadRunHistory() {
    const loading = document.getElementById('run-history-loading');
    const empty = document.getElementById('run-history-empty');
    const table = document.getElementById('run-history-table');
    const tbody = document.getElementById('run-history-body');

    if (!tbody) return;

    try {
        const response = await fetch('/api/runs');
        const runs = await response.json();

        if (loading) loading.classList.add('hidden');

        if (!runs || runs.length === 0) {
            if (empty) empty.classList.remove('hidden');
            if (table) table.classList.add('hidden');
            return;
        }

        if (empty) empty.classList.add('hidden');
        if (table) table.classList.remove('hidden');

        tbody.innerHTML = runs.map(run => {
            const date = new Date(run.timestamp);
            const timeStr = formatRunTime(date);
            const modeClass = run.dry_run ? 'run-mode-dry' : 'run-mode-live';
            const modeText = run.dry_run ? 'Dry' : 'Live';
            const statusClass = run.success ? 'run-status-success' : 'run-status-failed';
            const statusText = run.success ? 'OK' : 'Failed';
            const duration = formatDuration(run.duration_seconds);

            return `
                <tr>
                    <td class="run-col-time">${timeStr}</td>
                    <td class="run-col-mode"><span class="${modeClass}">${modeText}</span></td>
                    <td class="run-col-status"><span class="${statusClass}">${statusText}</span></td>
                    <td class="run-col-files">${run.files_moved}</td>
                    <td class="run-col-duration">${duration}</td>
                </tr>
            `;
        }).join('');

    } catch (error) {
        console.error('Failed to load run history:', error);
        if (loading) loading.classList.add('hidden');
        if (empty) {
            empty.classList.remove('hidden');
            empty.querySelector('p').textContent = 'Failed to load history';
        }
    }
}

function formatRunTime(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) {
        return 'Just now';
    } else if (diffMins < 60) {
        return `${diffMins}m ago`;
    } else if (diffHours < 24) {
        return `${diffHours}h ago`;
    } else if (diffDays < 7) {
        return `${diffDays}d ago`;
    } else {
        return date.toLocaleDateString();
    }
}

// ============================================
// Cache Browser Functions
// ============================================

let currentCachePath = '';
let cachedItems = [];
let cacheSortColumn = 'size';
let cacheSortAsc = false; // false = descending (largest first)

async function loadCacheContents(path = '') {
    const loading = document.getElementById('cache-loading');
    const empty = document.getElementById('cache-empty');
    const error = document.getElementById('cache-error');
    const table = document.getElementById('cache-table');
    const tbody = document.getElementById('cache-contents');

    // Show loading state
    if (loading) loading.classList.remove('hidden');
    if (empty) empty.classList.add('hidden');
    if (error) error.classList.add('hidden');
    if (table) table.classList.add('hidden');

    try {
        const url = '/api/cache-contents' + (path ? `?path=${encodeURIComponent(path)}` : '');
        const response = await fetch(url);

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Failed to load directory');
        }

        const data = await response.json();
        currentCachePath = path;

        // Update breadcrumb
        updateBreadcrumb(path);

        // Hide loading
        if (loading) loading.classList.add('hidden');

        // Check if empty
        if (data.items.length === 0) {
            if (empty) empty.classList.remove('hidden');
            return;
        }

        // Store items for sorting
        cachedItems = data.items;

        // Render sorted items
        renderCacheItems(path);

        if (table) table.classList.remove('hidden');

        // Set up sort header click handlers (only once)
        setupCacheSortHandlers();

    } catch (err) {
        if (loading) loading.classList.add('hidden');
        if (error) {
            const errorMsg = document.getElementById('cache-error-message');
            if (errorMsg) errorMsg.textContent = err.message;
            error.classList.remove('hidden');
        }
        console.error('Failed to load cache contents:', err);
    }
}

function updateBreadcrumb(path) {
    const breadcrumb = document.getElementById('cache-breadcrumb');
    if (!breadcrumb) return;

    breadcrumb.innerHTML = '';

    // Root link
    const rootLink = document.createElement('a');
    rootLink.href = '#';
    rootLink.className = 'breadcrumb-item' + (path === '' ? ' active' : '');
    rootLink.textContent = 'Cache';
    rootLink.onclick = (e) => { e.preventDefault(); loadCacheContents(''); };
    breadcrumb.appendChild(rootLink);

    if (path) {
        const parts = path.split('/');
        let currentPath = '';

        for (let i = 0; i < parts.length; i++) {
            const part = parts[i];
            currentPath = currentPath ? `${currentPath}/${part}` : part;

            // Add separator
            const separator = document.createElement('span');
            separator.className = 'breadcrumb-separator';
            separator.textContent = '/';
            breadcrumb.appendChild(separator);

            // Add path segment
            const link = document.createElement('a');
            link.href = '#';
            link.className = 'breadcrumb-item' + (i === parts.length - 1 ? ' active' : '');
            link.textContent = part;
            const linkPath = currentPath;
            link.onclick = (e) => { e.preventDefault(); loadCacheContents(linkPath); };
            breadcrumb.appendChild(link);
        }
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function sortCacheItems(items) {
    return [...items].sort((a, b) => {
        let comparison = 0;

        switch (cacheSortColumn) {
            case 'name':
                comparison = a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
                break;
            case 'size':
                comparison = a.size_bytes - b.size_bytes;
                break;
            case 'items':
                // Treat null/files as -1 so they sort to the end
                const aItems = a.item_count !== null ? a.item_count : -1;
                const bItems = b.item_count !== null ? b.item_count : -1;
                comparison = aItems - bItems;
                break;
        }

        return cacheSortAsc ? comparison : -comparison;
    });
}

function renderCacheItems(path) {
    const tbody = document.getElementById('cache-contents');
    if (!tbody) return;

    const sortedItems = sortCacheItems(cachedItems);

    tbody.innerHTML = '';
    for (const item of sortedItems) {
        const row = document.createElement('tr');
        const itemPath = path ? `${path}/${item.name}` : item.name;

        if (item.type === 'folder') {
            row.innerHTML = `
                <td class="cache-col-name">
                    <div class="cache-item-name">
                        <span class="cache-item-icon">📁</span>
                        <a class="cache-item-link" onclick="loadCacheContents('${itemPath.replace(/'/g, "\\'")}')">${escapeHtml(item.name)}</a>
                    </div>
                </td>
                <td class="cache-col-size">${formatSizeBytes(item.size_bytes)}</td>
                <td class="cache-col-items">${item.item_count !== null ? item.item_count : '—'}</td>
            `;
        } else {
            row.innerHTML = `
                <td class="cache-col-name">
                    <div class="cache-item-name">
                        <span class="cache-item-icon">📄</span>
                        <span class="cache-item-file">${escapeHtml(item.name)}</span>
                    </div>
                </td>
                <td class="cache-col-size">${formatSizeBytes(item.size_bytes)}</td>
                <td class="cache-col-items">—</td>
            `;
        }
        tbody.appendChild(row);
    }

    updateSortIndicators();
}

function updateSortIndicators() {
    const headers = document.querySelectorAll('.cache-table th.sortable');
    headers.forEach(th => {
        th.classList.remove('active', 'asc');
        if (th.dataset.sort === cacheSortColumn) {
            th.classList.add('active');
            if (cacheSortAsc) {
                th.classList.add('asc');
            }
        }
    });
}

let sortHandlersInitialized = false;

function setupCacheSortHandlers() {
    if (sortHandlersInitialized) {
        updateSortIndicators();
        return;
    }

    const headers = document.querySelectorAll('.cache-table th.sortable');
    headers.forEach(th => {
        th.addEventListener('click', () => {
            const column = th.dataset.sort;
            if (cacheSortColumn === column) {
                // Toggle direction
                cacheSortAsc = !cacheSortAsc;
            } else {
                // New column - default to descending for size/items, ascending for name
                cacheSortColumn = column;
                cacheSortAsc = column === 'name';
            }
            renderCacheItems(currentCachePath);
        });
    });

    sortHandlersInitialized = true;
    updateSortIndicators();
}

// ============================================
// Page Initialization
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    const path = window.location.pathname;

    // Highlight active nav link
    document.querySelectorAll('.nav-links a').forEach(link => {
        if (link.getAttribute('href') === path) {
            link.classList.add('active');
        }
    });

    // Global: Check run status on ALL pages (shows indicator in nav)
    checkGlobalRunStatus();

    // Dashboard page
    if (path === '/' || path === '/dashboard') {
        loadCacheUsage();
        loadRunStatus();
        loadRecentLogs();

        // Auto-refresh cache usage every 30 seconds
        setInterval(loadCacheUsage, 30000);
    }

    // Logs page
    if (path === '/logs') {
        loadRunHistory();
        loadLogs();
    }

    // Cache browser page
    if (path === '/cache') {
        loadCacheContents();
    }
});
