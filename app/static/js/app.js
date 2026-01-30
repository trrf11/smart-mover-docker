// Smart Mover - Frontend JavaScript

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
        loadLogs();
    }
});
