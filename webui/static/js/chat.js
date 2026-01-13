// Chat view page functionality

let sessionData = null;

// DOM elements
let chatMessages;
let chatLoading;
let liveIndicator;

// Input elements
let chatInputArea;
let chatInputForm;
let chatInputText;
let chatSubmitBtn;
let chatProcessing;
let chatInputStatus;

// Get session ID from body data attribute
const SESSION_ID = WebUIUtils.getSessionId();

// Refresh tracking (prefixed to avoid conflict with utils.js)
let chatLastRefreshTime = Date.now();
let chatRefreshCounterInterval;

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    if (!SESSION_ID) {
        console.error('SESSION_ID not defined');
        return;
    }

    initializeDOMElements();
    initializeSidebarControls();
    loadSessionData();
    setupSessionFileWatching();
    startRefreshCounter();
});

function setupSessionFileWatching() {
    console.log('[DEBUG] Setting up chat file watching for', SESSION_ID);

    if (typeof io === 'undefined') {
        console.warn('[DEBUG] Socket.io not available, file watching disabled');
        return;
    }

    if (window.WebUIUtils && window.WebUIUtils.registerSessionAutoRefresh) {
        window.WebUIUtils.registerSessionAutoRefresh(SESSION_ID, function(data) {
            if (data.event_type === 'modified') {
                console.log('[DEBUG] Reloading chat data due to file change');
                loadSessionData();
            }
        });

        window.addEventListener('beforeunload', function() {
            if (window.WebUIUtils && window.WebUIUtils.unregisterSessionAutoRefresh) {
                window.WebUIUtils.unregisterSessionAutoRefresh(SESSION_ID);
            }
        });
    }
}

function initializeDOMElements() {
    chatMessages = document.getElementById('chat-messages');
    chatLoading = document.getElementById('chat-loading');
    liveIndicator = document.getElementById('live-indicator');

    // Input elements
    chatInputArea = document.getElementById('chat-input-area');
    chatInputForm = document.getElementById('chat-input-form');
    chatInputText = document.getElementById('chat-input-text');
    chatSubmitBtn = document.getElementById('chat-submit-btn');
    chatProcessing = document.getElementById('chat-processing');
    chatInputStatus = document.getElementById('chat-input-status');

    // Set up input event listeners
    setupInputEventListeners();
}

// Load session data from API
async function loadSessionData() {
    try {
        const response = await fetch(`/api/sessions/${SESSION_ID}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        sessionData = await response.json();
        renderMessages();
        updateLiveIndicator();
        updateInputArea();

    } catch (error) {
        console.error('Error loading session data:', error);
        showError(error.message || 'Failed to load conversation');
    }
}

function showError(message) {
    if (chatLoading) chatLoading.style.display = 'none';

    chatMessages.innerHTML = `
        <div class="chat-empty">
            <i class="fas fa-exclamation-circle"></i>
            <p>${message}</p>
            <button class="btn btn-secondary" onclick="loadSessionData()">
                <i class="fas fa-redo"></i> Retry
            </button>
        </div>
    `;
}

function renderMessages() {
    if (!sessionData || !sessionData.iterations) {
        showEmpty();
        return;
    }

    const iterations = sessionData.iterations;

    if (iterations.length === 0) {
        showEmpty();
        return;
    }

    // Hide loading
    if (chatLoading) chatLoading.style.display = 'none';

    // Clear existing messages
    chatMessages.innerHTML = '';

    // Render each iteration as a conversation exchange
    iterations.forEach(iteration => {
        // Render user message if exists
        if (iteration.user_input) {
            const userMessage = createUserMessage(iteration);
            chatMessages.appendChild(userMessage);
        }

        // Render bot message if exists
        if (iteration.llm_response) {
            const botMessage = createBotMessage(iteration);
            chatMessages.appendChild(botMessage);
        }
    });

    // Scroll to bottom
    scrollToBottom();
}

function showEmpty() {
    if (chatLoading) chatLoading.style.display = 'none';

    chatMessages.innerHTML = `
        <div class="chat-empty">
            <i class="fas fa-comments"></i>
            <p data-i18n="chat.no_messages">No messages yet</p>
        </div>
    `;
}

function createUserMessage(iteration) {
    const template = document.getElementById('user-message-template');
    const message = template.content.cloneNode(true);

    const container = message.querySelector('.chat-message');
    const iterationMarker = message.querySelector('.iteration-marker');
    const messageTime = message.querySelector('.message-time');
    const messageContent = message.querySelector('.message-content');

    iterationMarker.textContent = `#${iteration.iteration}`;
    messageTime.textContent = WebUIUtils.formatTimestamp(iteration.start_time);
    messageContent.textContent = iteration.user_input;

    return container;
}

function createBotMessage(iteration) {
    const template = document.getElementById('bot-message-template');
    const message = template.content.cloneNode(true);

    const container = message.querySelector('.chat-message');
    const iterationMarker = message.querySelector('.iteration-marker');
    const messageTime = message.querySelector('.message-time');
    const messageContent = message.querySelector('.message-content');
    const toolCallsSection = message.querySelector('.tool-calls-section');
    const toolCallsCount = message.querySelector('.tool-calls-count');
    const toolCallsContent = message.querySelector('.tool-calls-content');

    iterationMarker.textContent = `#${iteration.iteration}`;
    messageTime.textContent = iteration.end_time
        ? WebUIUtils.formatTimestamp(iteration.end_time)
        : 'Processing...';

    // Render markdown content
    const llmResponse = iteration.llm_response || '';
    messageContent.innerHTML = renderMarkdown(llmResponse);

    // Render tool calls if present
    const toolCalls = iteration.tool_calls || [];
    if (toolCalls.length > 0) {
        toolCallsSection.style.display = 'block';

        const sqlCount = toolCalls.filter(tc => tc.tool === 'execute_sql').length;
        const memoryCount = toolCalls.filter(tc => tc.tool === 'memory').length;

        let countText = [];
        if (sqlCount > 0) countText.push(`${sqlCount} SQL`);
        if (memoryCount > 0) countText.push(`${memoryCount} Memory`);
        toolCallsCount.textContent = `Tools: ${countText.join(', ')}`;

        // Render tool call items
        toolCalls.forEach(tc => {
            const toolCallEl = createToolCallItem(tc);
            toolCallsContent.appendChild(toolCallEl);
        });
    }

    return container;
}

function createToolCallItem(toolCall) {
    const template = document.getElementById('tool-call-item-template');
    const item = template.content.cloneNode(true);

    const container = item.querySelector('.tool-call-item');
    const badge = item.querySelector('.tool-type-badge');
    const execTime = item.querySelector('.tool-execution-time');
    const inputCode = item.querySelector('.tool-call-input code');
    const outputCode = item.querySelector('.tool-call-output code');

    // Set badge style based on tool type
    if (toolCall.tool === 'execute_sql') {
        badge.classList.add('sql');
        badge.innerHTML = '<i class="fas fa-database"></i> SQL';

        // Format SQL input
        const query = toolCall.input?.query || JSON.stringify(toolCall.input);
        inputCode.textContent = query;
    } else if (toolCall.tool === 'memory') {
        const action = toolCall.input?.action || 'update';
        if (action === 'remove') {
            badge.classList.add('memory-remove');
            badge.innerHTML = '<i class="fas fa-trash"></i> Memory Remove';
        } else {
            badge.classList.add('memory');
            badge.innerHTML = '<i class="fas fa-brain"></i> Memory';
        }

        // Format memory input
        inputCode.textContent = JSON.stringify(toolCall.input, null, 2);
    } else {
        badge.textContent = toolCall.tool;
        inputCode.textContent = JSON.stringify(toolCall.input, null, 2);
    }

    // Execution time
    if (toolCall.execution_time) {
        execTime.textContent = `${(toolCall.execution_time * 1000).toFixed(0)}ms`;
    }

    // Output (truncate if very long)
    let output = toolCall.output || '';
    if (output.length > 2000) {
        output = output.substring(0, 2000) + '\n... (truncated)';
    }
    outputCode.textContent = output;

    return container;
}

function renderMarkdown(text) {
    if (!text) return '';

    try {
        // Configure marked
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                breaks: true,
                gfm: true
            });

            const html = marked.parse(text);

            // Sanitize with DOMPurify if available
            if (typeof DOMPurify !== 'undefined') {
                return DOMPurify.sanitize(html, {
                    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li',
                                   'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'a',
                                   'table', 'thead', 'tbody', 'tr', 'th', 'td'],
                    ALLOWED_ATTR: ['href', 'target', 'rel']
                });
            }
            return html;
        }
    } catch (e) {
        console.warn('Markdown rendering failed:', e);
    }

    // Fallback: escape HTML and preserve newlines
    return escapeHtml(text).replace(/\n/g, '<br>');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function toggleToolCalls(button) {
    const content = button.nextElementSibling;
    const isExpanded = content.style.display !== 'none';

    content.style.display = isExpanded ? 'none' : 'block';
    button.classList.toggle('expanded', !isExpanded);
}

function scrollToBottom() {
    // Scroll the page to the bottom (uses main page scroll)
    window.scrollTo({
        top: document.body.scrollHeight,
        behavior: 'smooth'
    });
}

function updateLiveIndicator() {
    if (!sessionData || !liveIndicator) return;

    const metadata = sessionData.session_metadata || sessionData;
    const status = metadata.status || sessionData.status;

    if (status === 'running') {
        liveIndicator.style.display = 'flex';
    } else {
        liveIndicator.style.display = 'none';
    }
}

// ============================================
// Sidebar Controls
// ============================================

function initializeSidebarControls() {
    initializeSidebarLanguageSelector();
    initializeSidebarPresetButton();
    initializeSidebarRefreshButton();
    updateSidebarConnectionStatus();
}

// Language Selector
async function initializeSidebarLanguageSelector() {
    const languageSelect = document.getElementById('sidebar-language-select');
    if (!languageSelect) return;

    const trigger = languageSelect.querySelector('.select-trigger');
    const optionsContainer = languageSelect.querySelector('.select-options');

    // Get current language
    const currentLang = window.i18n ? window.i18n.getCurrentLanguage() : 'en';

    // Load available languages
    try {
        const response = await fetch('/api/i18n/languages');
        if (response.ok) {
            const data = await response.json();
            const languages = data.languages || [{ code: 'en', name: 'English' }];

            optionsContainer.innerHTML = languages.map(lang => `
                <div class="select-option ${lang.code === currentLang ? 'selected' : ''}" data-value="${lang.code}">
                    <span>${lang.name}</span>
                </div>
            `).join('');

            // Attach click handlers
            languageSelect.querySelectorAll('.select-option').forEach(option => {
                option.addEventListener('click', function(e) {
                    e.stopPropagation();
                    const newLang = this.dataset.value;
                    if (newLang && newLang !== currentLang) {
                        changeSidebarLanguage(newLang);
                    }
                    languageSelect.classList.remove('open');
                });
            });
        }
    } catch (error) {
        console.error('Error loading languages:', error);
    }

    // Update selector display
    const selectText = languageSelect.querySelector('.select-text');
    if (selectText) {
        selectText.textContent = currentLang.toUpperCase();
    }

    // Toggle dropdown
    trigger.addEventListener('click', function(e) {
        e.stopPropagation();
        languageSelect.classList.toggle('open');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(event) {
        if (!languageSelect.contains(event.target)) {
            languageSelect.classList.remove('open');
        }
    });
}

function changeSidebarLanguage(newLang) {
    const currentPath = window.location.pathname;
    const currentParams = window.location.search;

    let newPath;
    if (newLang === 'en') {
        newPath = currentPath.replace(/^\/[a-z]{2}\//, '/');
    } else {
        if (currentPath.match(/^\/[a-z]{2}\//)) {
            newPath = currentPath.replace(/^\/[a-z]{2}\//, `/${newLang}/`);
        } else {
            newPath = `/${newLang}${currentPath}`;
        }
    }

    window.location.href = newPath + currentParams;
}

// Preset Button
function initializeSidebarPresetButton() {
    const presetBtn = document.getElementById('sidebar-preset-btn');
    if (!presetBtn) return;

    presetBtn.addEventListener('click', function(e) {
        e.preventDefault();
        // Open the preset editor modal (from preset-editor.js)
        const modal = document.getElementById('preset-editor-modal');
        if (modal) {
            modal.style.display = 'flex';
            // Trigger preset loading if available
            if (window.loadPresets) {
                window.loadPresets();
            }
        }
    });
}

// Refresh Button
function initializeSidebarRefreshButton() {
    const refreshBtn = document.getElementById('sidebar-refresh-btn');
    if (!refreshBtn) return;

    refreshBtn.addEventListener('click', function(e) {
        e.preventDefault();
        chatLastRefreshTime = Date.now();
        loadSessionData();
        updateRefreshCounter();
    });
}

function startRefreshCounter() {
    updateRefreshCounter();
    chatRefreshCounterInterval = setInterval(updateRefreshCounter, 1000);
}

function updateRefreshCounter() {
    const counter = document.getElementById('sidebar-refresh-counter');
    if (!counter) return;

    const elapsed = Math.floor((Date.now() - chatLastRefreshTime) / 1000);
    counter.textContent = `${elapsed}s ago`;
}

// Connection Status
function updateSidebarConnectionStatus() {
    const statusContainer = document.getElementById('sidebar-connection-status');
    const statusText = document.getElementById('sidebar-status-text');

    if (!statusContainer || !statusText) return;

    // Set up socket event listeners for real-time status updates
    if (typeof io !== 'undefined' && window.WebUIUtils && window.WebUIUtils.socket) {
        const socket = window.WebUIUtils.socket;

        // Check current state
        if (socket.connected) {
            setSidebarConnected();
        }

        // Listen for connection events
        socket.on('connect', setSidebarConnected);
        socket.on('disconnect', setSidebarDisconnected);
    } else {
        // Fallback: assume connected if io is available
        if (typeof io !== 'undefined') {
            setSidebarConnected();
        } else {
            setSidebarDisconnected();
        }
    }
}

function setSidebarConnected() {
    const statusContainer = document.getElementById('sidebar-connection-status');
    const statusText = document.getElementById('sidebar-status-text');
    if (!statusContainer || !statusText) return;

    statusContainer.classList.add('connected');
    statusContainer.classList.remove('disconnected');
    statusText.removeAttribute('data-i18n');  // Prevent i18n from overriding
    statusText.textContent = 'Connected';
}

function setSidebarDisconnected() {
    const statusContainer = document.getElementById('sidebar-connection-status');
    const statusText = document.getElementById('sidebar-status-text');
    if (!statusContainer || !statusText) return;

    statusContainer.classList.add('disconnected');
    statusContainer.classList.remove('connected');
    statusText.removeAttribute('data-i18n');  // Prevent i18n from overriding
    statusText.textContent = 'Disconnected';
}

// ============================================
// Input Handling
// ============================================

function setupInputEventListeners() {
    if (!chatSubmitBtn || !chatInputText) return;

    // Submit button click
    chatSubmitBtn.addEventListener('click', submitUserInput);

    // Ctrl+Enter to submit
    chatInputText.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            submitUserInput();
        }
    });

    // Auto-resize textarea
    chatInputText.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 150) + 'px';
    });
}

function updateInputArea() {
    if (!chatInputArea || !sessionData) return;

    const metadata = sessionData.session_metadata || sessionData;
    const status = metadata.status || sessionData.status;

    // Always show input area
    chatInputArea.style.display = 'block';
    chatInputForm.style.display = 'flex';

    if (status === 'running') {
        // Processing - show Stop button instead of submit
        chatInputText.disabled = true;
        chatInputText.placeholder = 'Processing...';
        chatSubmitBtn.disabled = false;
        chatSubmitBtn.innerHTML = '<i class="fas fa-stop"></i>';
        chatSubmitBtn.onclick = stopSession;
    } else if (status === 'interrupted') {
        // Session interrupted - show input for resume
        chatInputText.disabled = false;
        chatSubmitBtn.disabled = false;
        chatInputText.placeholder = 'Enter message to resume...';
        chatSubmitBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
        chatSubmitBtn.onclick = null;
    } else {
        // completed or other - ready for new iteration
        chatInputText.disabled = false;
        chatSubmitBtn.disabled = false;
        chatInputText.placeholder = 'Enter your message...';
        chatSubmitBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
        chatSubmitBtn.onclick = null;
        chatInputText.focus();
    }
}

async function submitUserInput() {
    const userInput = chatInputText.value.trim();

    if (!userInput) {
        showInputStatus('Please enter a message', 'warning');
        return;
    }

    // Disable input while submitting
    chatInputText.disabled = true;
    chatSubmitBtn.disabled = true;
    chatSubmitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    hideInputStatus();

    try {
        const sessionId = document.body.dataset.sessionId;
        const response = await fetch(`/api/sessions/${sessionId}/resume`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ resume_guidance: userInput })
        });

        if (response.ok) {
            chatInputText.value = '';
            chatInputText.style.height = 'auto';
            await loadSessionData();
        } else {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || 'Failed to send message');
        }
    } catch (error) {
        console.error('Error submitting input:', error);
        showInputStatus(error.message || 'Failed to send message', 'error');
        chatInputText.disabled = false;
        chatSubmitBtn.disabled = false;
        chatSubmitBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
    }
}

async function stopSession() {
    if (!confirm('Stop this running session?')) return;

    const sessionId = document.body.dataset.sessionId;
    const stopBtn = document.getElementById('sidebar-stop-btn');
    const originalContent = stopBtn.innerHTML;
    stopBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Stopping...</span>';

    try {
        const response = await fetch(`/api/sessions/${sessionId}/stop`, { method: 'POST' });
        if (response.ok) {
            WebUIUtils.showSuccess('Session stopped');
            await loadSessionData();
        } else {
            throw new Error('Failed to stop session');
        }
    } catch (error) {
        WebUIUtils.showError(error.message);
    } finally {
        stopBtn.innerHTML = originalContent;
    }
}

function showInputStatus(message, type = 'info') {
    if (!chatInputStatus) return;

    chatInputStatus.textContent = message;
    chatInputStatus.className = `chat-input-status ${type}`;
    chatInputStatus.style.display = 'block';
}

function hideInputStatus() {
    if (!chatInputStatus) return;
    chatInputStatus.style.display = 'none';
}
