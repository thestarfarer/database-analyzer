// Session detail page functionality

let sessionData = null;
let iterationResponses = {}; // Cache: {iteration_num: {main, thinking, raw}}

// DOM elements
let sessionOverview;
let iterationsTimeline;
let liveIndicator;
let inputSection;
let inputForm;
let webuiInputBtn;
let consoleInputBtn;
let submitInputBtn;
let cancelInputBtn;
let userInputText;
let inputStatus;

// Get session ID from body data attribute
const SESSION_ID = WebUIUtils.getSessionId();

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    if (!SESSION_ID) {
        console.error('SESSION_ID not defined');
        return;
    }

    initializeDOMElements();
    loadSessionData();

    // Set up file change listening for this session
    setupSessionFileWatching();
});

function setupSessionFileWatching() {
    console.log('[DEBUG] Setting up session file watching for', SESSION_ID);

    // Check if socket.io is available
    if (typeof io === 'undefined') {
        console.warn('[DEBUG] Socket.io not available, file watching disabled');
        return;
    }

    // Register auto-refresh callback for this session
    if (window.WebUIUtils && window.WebUIUtils.registerSessionAutoRefresh) {
        window.WebUIUtils.registerSessionAutoRefresh(SESSION_ID, function(data) {
            if (data.event_type === 'modified') {
                console.log('[DEBUG] Reloading session data due to file change');
                loadSessionData();
            }
        });

        // Cleanup on page unload
        window.addEventListener('beforeunload', function() {
            if (window.WebUIUtils && window.WebUIUtils.unregisterSessionAutoRefresh) {
                window.WebUIUtils.unregisterSessionAutoRefresh(SESSION_ID);
            }
        });
    } else {
        console.warn('[DEBUG] WebUIUtils not available, auto-refresh disabled');
    }
}

function initializeDOMElements() {
    sessionOverview = document.getElementById('session-overview');
    iterationsTimeline = document.getElementById('iterations-timeline');
    liveIndicator = document.getElementById('live-indicator');

    // Input form elements
    inputSection = document.getElementById('input-section');
    inputForm = document.getElementById('input-form');
    webuiInputBtn = document.getElementById('webui-input-btn');
    consoleInputBtn = document.getElementById('console-input-btn');
    submitInputBtn = document.getElementById('submit-input-btn');
    cancelInputBtn = document.getElementById('cancel-input-btn');
    userInputText = document.getElementById('user-input-text');
    inputStatus = document.getElementById('input-status');

    // Set up input form event listeners
    setupInputFormEventListeners();
}

function setupInputFormEventListeners() {
    if (webuiInputBtn) {
        webuiInputBtn.addEventListener('click', showWebUIInputForm);
    }

    if (consoleInputBtn) {
        consoleInputBtn.addEventListener('click', openConsoleInput);
    }

    if (submitInputBtn) {
        submitInputBtn.addEventListener('click', submitUserInput);
    }

    if (cancelInputBtn) {
        cancelInputBtn.addEventListener('click', hideWebUIInputForm);
    }

    // Handle Enter key in textarea (Ctrl+Enter to submit)
    if (userInputText) {
        userInputText.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                submitUserInput();
            }
        });
    }
}

// Load session data from API
async function loadSessionData() {
    try {
        const response = await fetch(`/api/sessions/${SESSION_ID}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        sessionData = await response.json();
        renderSessionOverview();
        renderIterations();
        updateLiveIndicator();
        updateInputSection();

    } catch (error) {
        console.error('Error loading session data:', error);
        const errorType = window.t ? window.t('session.session_details') : 'Session Data';
        WebUIUtils.showErrorState('#session-overview', error.message || 'Failed to load session data', {
            errorType,
            retryCallback: 'loadSessionData()'
        });
    }
}

function calculateSessionMetrics(sessionData) {
    // Calculate session metrics from raw tool calls data
    const metrics = {
        total_sql_queries: 0,
        memory_items_total: 0,
        total_tool_calls: 0,
        total_iterations: 0
    };

    const iterations = sessionData.iterations || [];
    metrics.total_iterations = iterations.length;

    for (const iteration of iterations) {
        const toolCalls = iteration.tool_calls || [];
        metrics.total_tool_calls += toolCalls.length;

        for (const toolCall of toolCalls) {
            const toolName = toolCall.tool || '';

            if (toolName === 'execute_sql') {
                metrics.total_sql_queries++;
            } else if (toolName === 'memory') {
                // Count memory operations that modify memory (update/remove), not reads (get)
                const inputData = toolCall.input || {};
                const action = inputData.action;
                if (action === 'update' || action === 'remove') {
                    metrics.memory_items_total++;
                }
            }
        }
    }

    return metrics;
}

function calculateIterationMetrics(iteration) {
    // Calculate iteration metrics from raw tool calls data
    const metrics = {
        total_tool_calls: 0,
        sql_queries: 0,
        memory_operations: 0,
        execution_time: null
    };

    const toolCalls = iteration.tool_calls || [];
    metrics.total_tool_calls = toolCalls.length;

    for (const toolCall of toolCalls) {
        const toolName = toolCall.tool || '';

        if (toolName === 'execute_sql') {
            metrics.sql_queries++;
        } else if (toolName === 'memory') {
            // Count memory operations that modify memory (update/remove), not reads (get)
            const inputData = toolCall.input || {};
            const action = inputData.action;
            if (action === 'update' || action === 'remove') {
                metrics.memory_operations++;
            }
        }
    }

    // Calculate execution time from start/end times if available
    if (iteration.start_time && iteration.end_time) {
        metrics.execution_time = iteration.end_time - iteration.start_time;
    }

    return metrics;
}

function renderSessionOverview() {
    if (!sessionOverview || !sessionData) return;

    const template = document.getElementById('session-overview-template');
    if (!template) {
        console.error('Session overview template not found');
        return;
    }
    
    const overviewElement = template.content.cloneNode(true);
    
    // Handle unified session format
    const metadata = sessionData.session_metadata || sessionData;
    const statistics = sessionData.statistics || {};

    // Status information
    const statusIcon = overviewElement.querySelector('.status-icon');
    const statusText = overviewElement.querySelector('.status-text');
    const statusBadge = overviewElement.querySelector('.status-badge');

    const status = metadata.status || sessionData.status || 'unknown';
    statusIcon.className = `status-icon fas ${getStatusIcon(status)}`;

    // Translate status text
    const statusKey = `status.${status}`;
    statusText.textContent = window.t ? window.t(statusKey) : status;
    statusBadge.className = `status-badge ${getStatusClass(status)}`;

    // Time information
    const startTime = overviewElement.querySelector('.start-time');
    const duration = overviewElement.querySelector('.duration');

    const start = metadata.start_time || sessionData.start_time;
    const end = metadata.end_time || sessionData.end_time;

    startTime.textContent = WebUIUtils.formatTimestamp(start);
    duration.textContent = WebUIUtils.formatDuration(start, end);

    // Backend information
    const backendDisplay = overviewElement.querySelector('.backend-display');
    if (backendDisplay) {
        const backend = metadata.llm_backend || 'qwen';
        // Text first, then icon (iconFirst: false)
        backendDisplay.innerHTML = `<span class="backend-badge ${WebUIUtils.getBackendClass(backend)}">${WebUIUtils.getBackendIcon(backend, { showText: true, iconFirst: false })}</span>`;
    }

    // Latest user input (fallback to initial task from metadata)
    const initialTask = overviewElement.querySelector('.initial-task');

    // Get latest user input from iterations
    let latestUserInput = '';
    if (sessionData.iterations && sessionData.iterations.length > 0) {
        // Find latest iteration with user input (iterate in reverse)
        for (let i = sessionData.iterations.length - 1; i >= 0; i--) {
            const iteration = sessionData.iterations[i];
            if (iteration.user_input && iteration.user_input.trim()) {
                latestUserInput = iteration.user_input.trim();
                break;
            }
        }
    }

    // Fallback to metadata initial_task or session latest_user_input
    const task = latestUserInput || metadata.initial_task || sessionData.latest_user_input;
    const noTaskText = window.t ? window.t('session.no_task') : 'No task description available';
    initialTask.textContent = task || noTaskText;

    // Calculate metrics from raw session data
    const calculatedMetrics = calculateSessionMetrics(sessionData);
    const iterationsCount = calculatedMetrics.total_iterations;
    const queriesCount = calculatedMetrics.total_sql_queries;
    const memoryItems = calculatedMetrics.memory_items_total;
    const toolCalls = calculatedMetrics.total_tool_calls;

    overviewElement.querySelector('.iterations-count').textContent = iterationsCount;
    overviewElement.querySelector('.queries-count').textContent = queriesCount;
    overviewElement.querySelector('.memory-items').textContent = memoryItems;

    // Update or add tool calls count if element exists
    const toolCallsElement = overviewElement.querySelector('.tool-calls-count');
    if (toolCallsElement) {
        toolCallsElement.textContent = toolCalls;
    }
    
    // Translate all elements with data-i18n attributes in the cloned template
    if (window.translateElement) {
        window.translateElement(overviewElement);
    }

    // Clear and append
    sessionOverview.innerHTML = '';
    sessionOverview.appendChild(overviewElement);
}

function renderIterations() {
    if (!iterationsTimeline || !sessionData) return;
    
    const iterations = sessionData.iterations || [];

    // For unified format, iterations already contain all necessary data
    const mergedIterations = iterations;
    
    if (mergedIterations.length === 0) {
        const noIterationsTitle = window.t ? window.t('session.no_iterations') : 'No Iterations Yet';
        const noIterationsMessage = window.t ? window.t('session.no_iterations_message') : 'Iterations will appear here as the analysis progresses.';

        iterationsTimeline.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-inbox"></i>
                <h3>${noIterationsTitle}</h3>
                <p>${noIterationsMessage}</p>
            </div>
        `;
        return;
    }
    
    const template = document.getElementById('iteration-item-template');
    if (!template) {
        console.error('Iteration item template not found');
        return;
    }
    
    iterationsTimeline.innerHTML = '';
    
    mergedIterations.forEach(iteration => {
        const iterationElement = createIterationElement(iteration, template);
        iterationsTimeline.appendChild(iterationElement);
    });
}


function createIterationElement(iteration, template) {
    const iterationElement = template.content.cloneNode(true);
    const item = iterationElement.querySelector('.iteration-item');
    
    // Set iteration number
    item.dataset.iteration = iteration.iteration;
    
    // Iteration header
    const iterationNum = item.querySelector('.iteration-num');
    const statusIcon = item.querySelector('.status-icon');
    const statusText = item.querySelector('.status-text');
    const iterationTime = item.querySelector('.iteration-time');
    
    iterationNum.textContent = iteration.iteration;
    statusIcon.className = `status-icon fas ${getStatusIcon(iteration.status)}`;

    // Translate status text
    const statusKey = `status.${iteration.status}`;
    statusText.textContent = window.t ? window.t(statusKey) : iteration.status;
    
    if (iteration.start_time) {
        iterationTime.textContent = WebUIUtils.formatRelativeTime(iteration.start_time);
    }

    // Add execution time if available (calculate from start/end times)
    const executionTime = item.querySelector('.execution-time');
    if (executionTime && iteration.start_time && iteration.end_time) {
        const execTime = iteration.end_time - iteration.start_time;
        executionTime.textContent = `${execTime.toFixed(2)}s`;
    }
    
    // Tool calls summary - handle both unified format and tool_calls array
    const callCount = item.querySelector('.call-count');
    const sqlCount = item.querySelector('.sql-count');
    const memoryCount = item.querySelector('.memory-count');

    // Calculate metrics from raw iteration data
    const iterationMetrics = calculateIterationMetrics(iteration);

    callCount.textContent = iterationMetrics.total_tool_calls;
    const sqlLabel = window.t ? window.t('session.sql_calls') : 'SQL';
    const memoryLabel = window.t ? window.t('session.memory_calls') : 'Memory';
    sqlCount.textContent = `${iterationMetrics.sql_queries} ${sqlLabel}`;
    memoryCount.textContent = `${iterationMetrics.memory_operations} ${memoryLabel}`;

    // Show user input if available
    const userInputContainer = item.querySelector('.iteration-user-input');
    const userInputTextEl = item.querySelector('.user-input-text');
    if (userInputContainer && userInputTextEl && iteration.user_input) {
        const fullInput = iteration.user_input;
        const truncatedInput = fullInput.length > 60
            ? fullInput.substring(0, 60) + '...'
            : fullInput;
        userInputTextEl.textContent = truncatedInput;
        userInputContainer.title = fullInput + '\n\nClick to copy';
        userInputContainer.style.display = 'flex';
        userInputContainer.onclick = function(e) {
            e.stopPropagation();
            e.preventDefault();
            // Fallback for non-HTTPS (clipboard API not available)
            const textarea = document.createElement('textarea');
            textarea.value = fullInput;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            if (window.WebUIUtils && window.WebUIUtils.showSuccess) {
                window.WebUIUtils.showSuccess('Copied to clipboard');
            }
            return false;
        };
    }
    
    // Show progress bar for running iterations
    const progressContainer = item.querySelector('.iteration-progress');
    if (iteration.status === 'running') {
        progressContainer.style.display = 'flex';
        const progressFill = progressContainer.querySelector('.progress-fill');
        progressFill.style.width = '60%'; // Simulated progress
    }

    // Cache LLM response and show button if available
    const llmResponse = iteration.llm_response || '';
    const llmThinking = iteration.llm_thinking || '';
    const llmResponseRaw = iteration.llm_response_raw || llmResponse;

    if (llmResponse || llmThinking) {
        iterationResponses[iteration.iteration] = {
            main: llmResponse,
            thinking: llmThinking,
            raw: llmResponseRaw
        };

        const llmResponseBtn = item.querySelector('.llm-response-btn');
        if (llmResponseBtn) {
            llmResponseBtn.classList.remove('muted');
        }
    }

    // Translate all elements with data-i18n attributes in the cloned template
    if (window.translateElement) {
        window.translateElement(iterationElement);
    }

    return iterationElement;
}

function updateLiveIndicator() {
    if (!liveIndicator || !sessionData) return;

    // Check status from metadata or root level
    const status = (sessionData.session_metadata && sessionData.session_metadata.status) || sessionData.status;

    if (status === 'running') {
        liveIndicator.style.display = 'inline-flex';
    } else {
        liveIndicator.style.display = 'none';
    }
}

// Note: getStatusClass and getStatusIcon are now global functions from utils.js

// Memory viewer functions
function viewMemory(sessionId) {
    const modal = document.getElementById('memory-viewer-modal');
    if (modal) {
        modal.style.display = 'flex';
        loadMemoryData(sessionId);
    }
}

function closeMemoryViewer() {
    const modal = document.getElementById('memory-viewer-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function refreshMemory() {
    if (typeof SESSION_ID !== 'undefined') {
        loadMemoryData(SESSION_ID);
    }
}

async function loadMemoryData(sessionId) {
    const memoryContent = document.getElementById('memory-content');
    if (!memoryContent) return;

    // Show loading state
    memoryContent.innerHTML = `
        <div class="loading-spinner">
            <i class="fas fa-spinner fa-spin"></i>
            <p>Loading memory data...</p>
        </div>
    `;

    try {
        const response = await fetch(`/api/sessions/${sessionId}/memory`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const memoryData = await response.json();
        renderMemoryData(memoryData);

    } catch (error) {
        console.error('Error loading memory data:', error);
        memoryContent.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Error Loading Memory</h3>
                <p>Failed to load memory data: ${error.message}</p>
                <button class="btn btn-primary" onclick="refreshMemory()">
                    <i class="fas fa-retry"></i> Retry
                </button>
            </div>
        `;
    }
}

let currentMemoryFilter = 'all';
let allMemoryItems = [];

function renderMemoryData(memoryData) {
    const memoryContent = document.getElementById('memory-content');
    if (!memoryContent) return;

    const categories = memoryData.memory_categories || {};

    if (Object.keys(categories).length === 0) {
        memoryContent.innerHTML = `
            <div class="empty-memory">
                <i class="fas fa-brain"></i>
                <h3>No Memory Data</h3>
                <p>No memory has been stored in this session yet.</p>
            </div>
        `;
        return;
    }

    // Collect all memory items into a flat array for feed display
    allMemoryItems = [];

    for (const [category, data] of Object.entries(categories)) {
        const items = data.items || [];
        const type = data.type || 'unknown';

        if (type === 'list' && Array.isArray(items)) {
            items.forEach(item => {
                let content, iteration, timestamp;

                if (typeof item === 'object' && item.content !== undefined) {
                    content = item.content;
                    iteration = item.iteration || 0;
                    timestamp = item.timestamp || '';
                } else {
                    content = String(item);
                    iteration = 0;
                    timestamp = '';
                }

                allMemoryItems.push({
                    category: category,
                    key: '',
                    content: content,
                    iteration: iteration,
                    timestamp: timestamp,
                    type: 'list'
                });
            });
        } else if (type === 'dict' && typeof items === 'object') {
            Object.entries(items).forEach(([key, value]) => {
                let content, iteration, timestamp;

                if (typeof value === 'object' && value.content !== undefined) {
                    content = value.content;
                    iteration = value.iteration || 0;
                    timestamp = value.timestamp || '';
                } else {
                    content = String(value);
                    iteration = 0;
                    timestamp = '';
                }

                allMemoryItems.push({
                    category: category,
                    key: key,
                    content: content,
                    iteration: iteration,
                    timestamp: timestamp,
                    type: 'dict'
                });
            });
        } else if (type === 'value') {
            allMemoryItems.push({
                category: category,
                key: '',
                content: String(items),
                iteration: 0,
                timestamp: '',
                type: 'value'
            });
        }
    }

    // Sort by iteration (newest first), then by category
    allMemoryItems.sort((a, b) => {
        if (a.iteration !== b.iteration) {
            return b.iteration - a.iteration; // Newest first
        }
        return a.category.localeCompare(b.category);
    });

    // Get unique categories for filters
    const uniqueCategories = [...new Set(allMemoryItems.map(item => item.category))];

    let html = `
        <div class="memory-summary">
            <div class="memory-stats">
                <div class="stat-item">
                    <span class="stat-number">${memoryData.total_items || 0}</span>
                    <span class="stat-label">Total Items</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number">${Object.keys(categories).length}</span>
                    <span class="stat-label">Categories</span>
                </div>
            </div>
        </div>

        <div class="memory-filters">
            <div class="filter-pill all ${currentMemoryFilter === 'all' ? 'active' : ''}" onclick="filterMemory('all')">
                <i class="fas fa-list"></i> All
            </div>
    `;

    uniqueCategories.forEach(category => {
        const categoryDisplayName = category.charAt(0).toUpperCase() + category.slice(1).replace(/_/g, ' ');
        html += `
            <div class="filter-pill ${category} ${currentMemoryFilter === category ? 'active' : ''}" onclick="filterMemory('${category}')">
                <i class="fas ${getCategoryIcon(category)}"></i>
                ${categoryDisplayName}
            </div>
        `;
    });

    html += `
        </div>

        <div class="memory-categories">
            <div class="memory-feed" id="memory-feed">
                ${renderMemoryFeed()}
            </div>
        </div>
    `;

    memoryContent.innerHTML = html;
}

function renderMemoryFeed() {
    const filteredItems = currentMemoryFilter === 'all'
        ? allMemoryItems
        : allMemoryItems.filter(item => item.category === currentMemoryFilter);

    if (filteredItems.length === 0) {
        return `
            <div class="empty-memory">
                <i class="fas fa-search"></i>
                <h3>No Items Found</h3>
                <p>No memory items match the selected filter.</p>
            </div>
        `;
    }

    return filteredItems.map(item => renderMemoryCard(item)).join('');
}

function renderMemoryCard(item) {
    const categoryDisplayName = item.category.charAt(0).toUpperCase() + item.category.slice(1).replace(/_/g, ' ');
    const iterationDisplay = item.iteration > 0 ? `<span class="iteration-badge">Iter ${item.iteration}</span>` : '';
    const timestamp = item.timestamp ? formatMemoryTimestamp(item.timestamp) : '';
    const keyText = (item.type === 'dict' && item.key) ? `${item.key}: ` : '';

    const metaParts = [
        `<span class="category-badge ${item.category}">${categoryDisplayName}</span>`,
        iterationDisplay,
        timestamp
    ].filter(Boolean);

    return `<div class="memory-item ${item.category}" onclick="copyMemoryItem('${escapeHtml(item.content)}')" title="Click to copy"><div class="memory-header"><i class="fas ${getCategoryIcon(item.category)}"></i><span class="memory-meta">${metaParts.join(' ')}</span></div><div class="memory-content">${keyText}${escapeHtml(item.content)}</div></div>`;
}

function formatMemoryTimestamp(timestamp) {
    try {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMinutes = Math.floor((now - date) / (1000 * 60));

        if (diffMinutes < 1) return 'Just now';
        if (diffMinutes < 60) return `${diffMinutes}m ago`;

        const diffHours = Math.floor(diffMinutes / 60);
        if (diffHours < 24) return `${diffHours}h ago`;

        const diffDays = Math.floor(diffHours / 24);
        if (diffDays < 7) return `${diffDays}d ago`;

        return date.toLocaleDateString();
    } catch (e) {
        return timestamp;
    }
}

function filterMemory(category) {
    currentMemoryFilter = category;

    // Update filter pills
    document.querySelectorAll('.filter-pill').forEach(pill => {
        pill.classList.remove('active');
    });
    document.querySelector(`.filter-pill.${category}`).classList.add('active');

    // Update feed
    const feedContainer = document.getElementById('memory-feed');
    if (feedContainer) {
        feedContainer.innerHTML = renderMemoryFeed();
    }
}

function copyMemoryItem(content) {
    navigator.clipboard.writeText(content).then(() => {
        // Could add a toast notification here
        console.log('Memory item copied to clipboard');
    }).catch(err => {
        console.error('Failed to copy memory item:', err);
    });
}

// Category rendering is now handled in renderMemoryData table format

function getCategoryIcon(category) {
    const icons = {
        'insights': 'fa-lightbulb',
        'patterns': 'fa-chart-line',
        'explored_areas': 'fa-map-marked',
        'key_findings': 'fa-star',
        'opportunities': 'fa-dollar-sign',
        'data_issues': 'fa-exclamation-triangle',
        'metrics': 'fa-chart-bar',
        'context': 'fa-info-circle',
        'data_milestones': 'fa-flag',
        'user_requests': 'fa-user-comment'
    };
    return icons[category] || 'fa-folder';
}

// Category expand/collapse no longer needed with table format

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Table format doesn't need expand/collapse functionality - all data is visible

// Global functions
function viewIteration(sessionId, iteration) {
    window.location.href = `/session/${sessionId}/iteration/${iteration}`;
}

function exportSession(sessionId) {
    if (sessionData) {
        const dataStr = JSON.stringify(sessionData, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
        
        const exportFileDefaultName = `session_${sessionId}_detailed.json`;
        
        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();
        
        WebUIUtils.showSuccess('Session exported successfully');
    }
}

// Override the global session update handler
window.WebUIUtils.handleSessionUpdate = function(data) {
    console.log('Session detail page received update:', data);
    
    if (data.session_id === SESSION_ID) {
        // Update our session data and re-render
        if (data.file_type === 'live_session' && data.data) {
            sessionData = { ...sessionData, ...data.data };
            renderSessionOverview();
            renderIterations();
            updateLiveIndicator();
        } else if (data.file_type === 'memory' && data.data) {
            // Update memory-related data
            if (sessionData) {
                // Memory data composed from tool calls
                renderSessionOverview();
            }
        }
    }
};

// Input Section Management
function updateInputSection() {
    if (!sessionData || !inputSection) return;

    const isAwaitingInput = sessionData.status === 'awaiting_input';

    if (isAwaitingInput) {
        inputSection.style.display = 'block';
    } else {
        inputSection.style.display = 'none';
        hideWebUIInputForm(); // Hide form if visible
    }
}

function showWebUIInputForm() {
    if (inputForm) {
        inputForm.style.display = 'block';
        userInputText.focus();
    }
}

function hideWebUIInputForm() {
    if (inputForm) {
        inputForm.style.display = 'none';
        userInputText.value = '';
        hideInputStatus();
    }
}

function openConsoleInput() {
    // Try to find the input server port from session data
    const inputServerPort = getInputServerPort();
    if (inputServerPort) {
        window.open(`http://127.0.0.1:${inputServerPort}`, '_blank');
    } else {
        showInputStatus('Input server not available. Please use console.', 'error');
    }
}

function getInputServerPort() {
    // Look for input server info in session metadata or try common ports
    if (sessionData && sessionData.input_server_port) {
        return sessionData.input_server_port;
    }
    // Default port range for input servers
    return 5001; // We'll try the first port
}

async function submitUserInput() {
    const userInput = userInputText.value.trim();

    if (!userInput) {
        showInputStatus('Please enter some input.', 'error');
        return;
    }

    const inputServerPort = getInputServerPort();
    if (!inputServerPort) {
        showInputStatus('Input server not available.', 'error');
        return;
    }

    showInputStatus('Submitting input...', 'info');
    submitInputBtn.disabled = true;

    try {
        const response = await fetch(`http://127.0.0.1:${inputServerPort}/input`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_input: userInput
            })
        });

        const result = await response.json();

        if (response.ok && result.status === 'success') {
            showInputStatus('✅ Input submitted successfully!', 'success');
            setTimeout(() => {
                hideWebUIInputForm();
                // Reload session data to update status
                loadSessionData();
            }, 2000);
        } else {
            showInputStatus(`❌ Error: ${result.message || 'Failed to submit input'}`, 'error');
        }
    } catch (error) {
        console.error('Failed to submit input:', error);
        showInputStatus('❌ Network error. Please try console input.', 'error');
    } finally {
        submitInputBtn.disabled = false;
    }
}

function showInputStatus(message, type) {
    if (inputStatus) {
        inputStatus.textContent = message;
        inputStatus.className = 'input-status ' + type;
        inputStatus.style.display = 'block';
    }
}

function hideInputStatus() {
    if (inputStatus) {
        inputStatus.style.display = 'none';
    }
}

// LLM Response Modal for iterations
function openIterationLLMResponse(event, iterationNum) {
    // Stop event propagation to prevent navigating to iteration detail
    event.stopPropagation();

    const response = iterationResponses[iterationNum];
    if (response && window.LLMResponseModal) {
        window.LLMResponseModal.open(response.main, response.thinking, response.raw);
    }
}

// Make functions globally available
window.viewIteration = viewIteration;
window.exportSession = exportSession;
window.viewMemory = viewMemory;
window.closeMemoryViewer = closeMemoryViewer;
window.refreshMemory = refreshMemory;
window.filterMemory = filterMemory;
window.copyMemoryItem = copyMemoryItem;
window.openIterationLLMResponse = openIterationLLMResponse;