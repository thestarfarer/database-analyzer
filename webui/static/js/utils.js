// Utility functions for the WebUI

// WebSocket connection
let socket = null;

// Auto-refresh callbacks registry
const autoRefreshCallbacks = {
    global: [],      // Callbacks for all file changes
    sessions: {}     // Callbacks for specific session IDs
};

// Initialize WebSocket connection
function initializeWebSocket() {
    socket = io();

    socket.on('connect', function() {
        console.log('Connected to server');
        updateConnectionStatus('connected', 'Connected');
    });

    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        updateConnectionStatus('disconnected', 'Disconnected');
    });

    socket.on('connected', function(data) {
        console.log('Server says:', data.status);
    });

    socket.on('session_update', function(data) {
        console.log('Session update:', data);
        handleSessionUpdate(data);
    });

    // Centralized file_changed event handler
    socket.on('file_changed', function(data) {
        console.log('[DEBUG] File changed:', data);

        // Execute global callbacks (for sessions list page)
        autoRefreshCallbacks.global.forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                console.error('[DEBUG] Global callback error:', error);
            }
        });

        // Execute session-specific callbacks
        if (data.session_id && autoRefreshCallbacks.sessions[data.session_id]) {
            autoRefreshCallbacks.sessions[data.session_id].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error('[DEBUG] Session callback error:', error);
                }
            });
        }
    });
}

// Register auto-refresh callback for all file changes (e.g., sessions list)
function registerGlobalAutoRefresh(callback) {
    if (typeof callback === 'function') {
        autoRefreshCallbacks.global.push(callback);
        console.log('[DEBUG] Registered global auto-refresh callback');
    }
}

// Register auto-refresh callback for specific session
function registerSessionAutoRefresh(sessionId, callback) {
    if (typeof callback === 'function' && sessionId) {
        if (!autoRefreshCallbacks.sessions[sessionId]) {
            autoRefreshCallbacks.sessions[sessionId] = [];
        }
        autoRefreshCallbacks.sessions[sessionId].push(callback);
        console.log('[DEBUG] Registered auto-refresh for session:', sessionId);
    }
}

// Unregister all callbacks for a session (cleanup on page unload)
function unregisterSessionAutoRefresh(sessionId) {
    if (sessionId && autoRefreshCallbacks.sessions[sessionId]) {
        delete autoRefreshCallbacks.sessions[sessionId];
        console.log('[DEBUG] Unregistered auto-refresh for session:', sessionId);
    }
}

// Update connection status indicator
function updateConnectionStatus(status, text) {
    const statusIcon = document.getElementById('status-icon');
    const statusText = document.getElementById('status-text');

    if (statusIcon && statusText) {
        statusIcon.className = `fas fa-circle ${status}`;

        // Use translation if available
        if (window.t) {
            const translationKey = status === 'connected' ? 'status.connected' :
                                   status === 'disconnected' ? 'status.disconnected' :
                                   'status.connecting';
            statusText.textContent = window.t(translationKey);
        } else {
            statusText.textContent = text;
        }
    }
}

// Format timestamp
function formatTimestamp(timestamp) {
    if (!timestamp) return 'Unknown';
    
    let date;
    if (typeof timestamp === 'number') {
        date = new Date(timestamp * 1000);
    } else {
        date = new Date(timestamp);
    }
    
    return date.toLocaleString();
}

// Format relative time
function formatRelativeTime(timestamp) {
    if (!timestamp) {
        return window.t ? window.t('common.unknown') : 'Unknown';
    }

    // Use i18n if available, otherwise fallback to English
    if (window.i18n && window.i18n.formatRelativeTime) {
        return window.i18n.formatRelativeTime(timestamp);
    }

    let date;
    if (typeof timestamp === 'number') {
        date = new Date(timestamp * 1000);
    } else {
        date = new Date(timestamp);
    }

    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
}

// Format duration
function formatDuration(startTime, endTime) {
    if (!startTime) {
        return window.t ? window.t('common.unknown') : 'Unknown';
    }

    // Use i18n if available, otherwise fallback to English
    if (window.i18n && window.i18n.formatDuration) {
        return window.i18n.formatDuration(startTime, endTime);
    }

    let start, end;
    if (typeof startTime === 'number') {
        start = new Date(startTime * 1000);
    } else {
        start = new Date(startTime);
    }

    if (endTime) {
        if (typeof endTime === 'number') {
            end = new Date(endTime * 1000);
        } else {
            end = new Date(endTime);
        }
    } else {
        end = new Date();
    }

    const diffMs = end - start;
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);

    if (diffSecs < 60) return `${diffSecs}s`;
    if (diffMins < 60) return `${diffMins}m ${diffSecs % 60}s`;
    return `${diffHours}h ${diffMins % 60}m`;
}

// Format execution time
function formatExecutionTime(seconds) {
    if (!seconds) {
        return window.t ? window.t('time.milliseconds_short', { count: 0 }) : '0ms';
    }

    if (seconds < 1) {
        const ms = Math.round(seconds * 1000);
        return window.t ? window.t('time.milliseconds_short', { count: ms }) : `${ms}ms`;
    } else if (seconds < 60) {
        const secs = seconds.toFixed(2);
        return window.t ? window.t('time.seconds_short', { count: secs }) : `${secs}s`;
    } else {
        const mins = Math.floor(seconds / 60);
        const secs = (seconds % 60).toFixed(2);
        const minsText = window.t ? window.t('time.minutes_short', { count: mins }) : `${mins}m`;
        const secsText = window.t ? window.t('time.seconds_short', { count: secs }) : `${secs}s`;
        return `${minsText} ${secsText}`;
    }
}

// Copy text to clipboard
function copyToClipboard(button) {
    const targetSelector = button.dataset.copyTarget;
    let targetElement = button.closest('.tool-call-content').querySelector(targetSelector);

    // If not found in tool-call-content, try searching in the immediate parent (for memory content)
    if (!targetElement) {
        targetElement = button.closest('.memory-field-simple').querySelector(targetSelector);
    }

    if (targetElement) {
        // For memory input, copy the original JSON if available
        let text;
        if (targetElement.dataset.originalJson) {
            text = targetElement.dataset.originalJson;
        } else {
            text = targetElement.textContent || targetElement.innerText;
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(() => {
                showCopyFeedback(button);
            }).catch(err => {
                console.error('Failed to copy:', err);
                fallbackCopyToClipboard(text);
                showCopyFeedback(button);
            });
        } else {
            fallbackCopyToClipboard(text);
            showCopyFeedback(button);
        }
    }
}

// Fallback copy method for older browsers
function fallbackCopyToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
    } catch (err) {
        console.error('Fallback copy failed:', err);
    }
    
    document.body.removeChild(textArea);
}

// Show copy feedback
function showCopyFeedback(button) {
    const originalIcon = button.querySelector('i').className;
    const originalText = button.textContent;
    
    button.querySelector('i').className = 'fas fa-check';
    button.style.background = '#28a745';
    
    setTimeout(() => {
        button.querySelector('i').className = originalIcon;
        button.style.background = '';
    }, 1500);
}

// Format SQL query with basic syntax highlighting
function formatSQL(query) {
    if (!query) return '';
    
    // Simple SQL formatting
    const keywords = [
        'SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING', 
        'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'ON',
        'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER',
        'AND', 'OR', 'NOT', 'IN', 'BETWEEN', 'LIKE', 'IS', 'NULL'
    ];
    
    let formatted = query;
    keywords.forEach(keyword => {
        const regex = new RegExp(`\\b${keyword}\\b`, 'gi');
        formatted = formatted.replace(regex, `<span class="sql-keyword">${keyword}</span>`);
    });
    
    return formatted;
}

// Truncate text
function truncateText(text, maxLength) {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Unified toast notification system
function showToast(message, type = 'info', options = {}) {
    const {
        duration = type === 'error' ? 10000 : 5000,
        showClose = true
    } = options;

    // Create toast container if it doesn't exist
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    // Icon mapping
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-triangle',
        warning: 'fa-exclamation-circle',
        info: 'fa-info-circle'
    };

    const icon = icons[type] || icons.info;
    const closeBtn = showClose ? `<button class="toast-close" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>` : '';

    toast.innerHTML = `
        <div class="toast-content">
            <i class="fas ${icon} toast-icon"></i>
            <span class="toast-message">${message}</span>
            ${closeBtn}
        </div>
    `;

    // Add to container
    container.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
        toast.classList.add('toast-show');
    });

    // Auto-remove after duration
    setTimeout(() => {
        toast.classList.remove('toast-show');
        toast.classList.add('toast-hide');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
            // Remove container if empty
            if (container.children.length === 0) {
                container.remove();
            }
        }, 300);
    }, duration);
}

// Show error message (now uses toast)
function showError(message) {
    console.error(message);
    showToast(message, 'error');
}

// Show success message (now uses toast)
function showSuccess(message) {
    console.log(message);
    showToast(message, 'success');
}

// Show error state in a container (consolidated from sessions.js, session.js, iteration.js)
function showErrorState(containerSelector, message, options = {}) {
    const container = typeof containerSelector === 'string'
        ? document.querySelector(containerSelector)
        : containerSelector;

    if (!container) {
        console.error('[showErrorState] Container not found:', containerSelector);
        return;
    }

    const {
        errorType = 'general',
        onlyIfEmpty = false,
        showRetry = true,
        retryCallback = null,
        retryText = window.t ? window.t('errors.retry') : 'Retry'
    } = options;

    // If onlyIfEmpty is true, only show error if container has no items
    if (onlyIfEmpty) {
        const hasItems = container.querySelector('.session-card, .iteration-item, .tool-call-item');
        if (hasItems) {
            showErrorToast(message);
            return;
        }
    }

    const errorTitle = window.t
        ? window.t('errors.loading_error', { type: errorType })
        : `Error Loading ${errorType}`;

    const retryBtn = showRetry
        ? `<button class="btn btn-primary" onclick="${retryCallback || 'location.reload()'}">
               <i class="fas fa-retry"></i> ${retryText}
           </button>`
        : '';

    container.innerHTML = `
        <div class="error-state">
            <i class="fas fa-exclamation-triangle"></i>
            <h3>${errorTitle}</h3>
            <p>${message}</p>
            ${retryBtn}
        </div>
    `;
}

// Show error toast (non-disruptive overlay)
function showErrorToast(message, options = {}) {
    const {
        duration = 10000,
        retryCallback = null
    } = options;

    // Remove any existing error toast
    const existingToast = document.querySelector('.error-toast');
    if (existingToast) {
        existingToast.remove();
    }

    // Create error toast
    const toast = document.createElement('div');
    toast.className = 'error-toast';

    const retryBtn = retryCallback
        ? `<button class="toast-retry" onclick="${retryCallback}">
               <i class="fas fa-retry"></i> Retry
           </button>`
        : '';

    toast.innerHTML = `
        <div class="toast-content">
            <i class="fas fa-exclamation-triangle"></i>
            <span>${message}</span>
            ${retryBtn}
            <button class="toast-close" onclick="this.parentElement.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;

    // Add to page
    document.body.appendChild(toast);

    // Auto-remove after duration
    setTimeout(() => {
        if (toast.parentNode) {
            toast.remove();
        }
    }, duration);
}

// Generic session update handler (to be overridden in specific pages)
function handleSessionUpdate(data) {
    console.log('Session update received:', data);
    // This will be overridden in specific page scripts
}

// Status helper functions (consolidated from sessions.js, session.js, iteration.js)
function getStatusClass(status) {
    switch (status) {
        case 'running': return 'running';
        case 'completed': return 'completed';
        case 'interrupted': return 'interrupted';
        case 'awaiting_input': return 'awaiting_input';
        case 'error':
        case 'failed': return 'failed';
        case 'incomplete': return 'incomplete';
        default: return 'unknown';
    }
}

function getStatusIcon(status) {
    switch (status) {
        case 'running': return 'fa-play-circle';
        case 'completed': return 'fa-check-circle';
        case 'interrupted': return 'fa-pause-circle';
        case 'awaiting_input': return 'fa-keyboard';
        case 'error':
        case 'failed': return 'fa-times-circle';
        case 'incomplete': return 'fa-exclamation-triangle';
        default: return 'fa-question-circle';
    }
}

// Get session/iteration data from body attributes (consolidated pattern)
function getSessionId() {
    return document.body.dataset.sessionId || null;
}

function getIterationNum() {
    const num = document.body.dataset.iterationNum;
    return num ? parseInt(num, 10) : null;
}

// Refresh counter functionality
let lastRefreshTime = Date.now();
let refreshCounterInterval = null;

function initializeRefreshCounter() {
    const counter = document.getElementById('last-refresh-counter');
    if (!counter) return;

    // Update counter every second
    refreshCounterInterval = setInterval(() => {
        updateRefreshCounterDisplay();
    }, 1000);

    // Reset counter when page loads/refreshes
    resetRefreshCounter();

    // Update display when translations load
    document.addEventListener('translationsLoaded', () => {
        updateRefreshCounterDisplay();
    });
}

function resetRefreshCounter() {
    lastRefreshTime = Date.now();
    updateRefreshCounterDisplay();
}

function updateRefreshCounterDisplay() {
    const counter = document.getElementById('last-refresh-counter');
    if (!counter) return;

    const secondsAgo = Math.floor((Date.now() - lastRefreshTime) / 1000);
    const timeText = window.t ? window.t('time.seconds_short', { count: secondsAgo }) : `${secondsAgo}s`;
    const text = window.t ? window.t('time.last_refresh', { time: timeText }) : `Last refresh: ${secondsAgo}s ago`;
    counter.textContent = text;
}

function updateRefreshCounter() {
    resetRefreshCounter();
}

// Initialize the WebSocket connection when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeWebSocket();
    initializeRefreshCounter();

    // Add refresh button handler
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function(e) {
            e.preventDefault();
            location.reload();
        });
    }
});

// Claude SVG icon (from Bootstrap Icons, MIT License)
const CLAUDE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" viewBox="0 0 16 16"><path d="m3.127 10.604 3.135-1.76.053-.153-.053-.085H6.11l-.525-.032-1.791-.048-1.554-.065-1.505-.08-.38-.081L0 7.832l.036-.234.32-.214.455.04 1.009.069 1.513.105 1.097.064 1.626.17h.259l.036-.105-.089-.065-.068-.064-1.566-1.062-1.695-1.121-.887-.646-.48-.327-.243-.306-.104-.67.435-.48.585.04.15.04.593.456 1.267.981 1.654 1.218.242.202.097-.068.012-.049-.109-.181-.9-1.626-.96-1.655-.428-.686-.113-.411a2 2 0 0 1-.068-.484l.496-.674L4.446 0l.662.089.279.242.411.94.666 1.48 1.033 2.014.302.597.162.553.06.17h.105v-.097l.085-1.134.157-1.392.154-1.792.052-.504.25-.605.497-.327.387.186.319.456-.045.294-.19 1.23-.37 1.93-.243 1.29h.142l.161-.16.654-.868 1.097-1.372.484-.545.565-.601.363-.287h.686l.505.751-.226.775-.707.895-.585.759-.839 1.13-.524.904.048.072.125-.012 1.897-.403 1.024-.186 1.223-.21.553.258.06.263-.218.536-1.307.323-1.533.307-2.284.54-.028.02.032.04 1.029.098.44.024h1.077l2.005.15.525.346.315.424-.053.323-.807.411-3.631-.863-.872-.218h-.12v.073l.726.71 1.331 1.202 1.667 1.55.084.383-.214.302-.226-.032-1.464-1.101-.565-.497-1.28-1.077h-.084v.113l.295.432 1.557 2.34.08.718-.112.234-.404.141-.444-.08-.911-1.28-.94-1.44-.759-1.291-.093.053-.448 4.821-.21.246-.484.186-.403-.307-.214-.496.214-.98.258-1.28.21-1.016.19-1.263.112-.42-.008-.028-.092.012-.953 1.307-1.448 1.957-1.146 1.227-.274.109-.477-.247.045-.44.266-.39 1.586-2.018.956-1.25.617-.723-.004-.105h-.036l-4.212 2.736-.75.096-.324-.302.04-.496.154-.162 1.267-.871z"/></svg>';

/**
 * Get backend icon HTML with optional text
 * @param {string} backend - 'claude' or 'qwen'
 * @param {object} options - { showText: boolean, iconFirst: boolean }
 * @returns {string} HTML string
 */
function getBackendIcon(backend, options = {}) {
    const { showText = false, iconFirst = true } = options;
    const isClaudeBackend = backend === 'claude';
    const iconHtml = isClaudeBackend ? CLAUDE_SVG : '<i class="fas fa-server"></i>';
    const text = isClaudeBackend ? 'Claude' : 'Qwen';

    if (!showText) {
        return iconHtml;
    }

    return iconFirst
        ? `${iconHtml} ${text}`
        : `${text} ${iconHtml}`;
}

/**
 * Get backend CSS class
 * @param {string} backend - 'claude' or 'qwen'
 * @returns {string} CSS class name
 */
function getBackendClass(backend) {
    return backend === 'claude' ? 'backend-claude' : 'backend-qwen';
}

// Export functions for use in other scripts
window.WebUIUtils = {
    socket,
    formatTimestamp,
    formatRelativeTime,
    formatDuration,
    formatExecutionTime,
    copyToClipboard,
    formatSQL,
    truncateText,
    debounce,
    showToast,
    showError,
    showSuccess,
    showErrorState,
    showErrorToast,
    handleSessionUpdate,
    updateRefreshCounter,
    resetRefreshCounter,
    registerGlobalAutoRefresh,
    registerSessionAutoRefresh,
    unregisterSessionAutoRefresh,
    getStatusClass,
    getStatusIcon,
    getSessionId,
    getIterationNum,
    getBackendIcon,
    getBackendClass,
    CLAUDE_SVG
};