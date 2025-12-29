// Iteration detail page functionality

let iterationData = null;
let isInitialPageLoad = true;

// Get session/iteration data from body data attributes
const SESSION_ID = WebUIUtils.getSessionId();
const ITERATION_NUM = WebUIUtils.getIterationNum();

// DOM elements
let iterationHeaderInfo;
let toolCallsTimeline;
let toolCallsCount;

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    if (!SESSION_ID || !ITERATION_NUM) {
        console.error('SESSION_ID or ITERATION_NUM not defined');
        return;
    }

    // Disable browser's default scroll restoration to prevent interference
    if ('scrollRestoration' in history) {
        history.scrollRestoration = 'manual';
    }

    // Restore scroll position immediately before any content loads
    restoreScrollPositionImmediately();


    initializeDOMElements();
    loadIterationData();

    // Set up file change listening for real-time updates
    setupFileChangeListening();

    // Set up scroll position preservation
    setupScrollPositionPreservation();
});

function initializeDOMElements() {
    iterationHeaderInfo = document.getElementById('iteration-header-info');
    toolCallsTimeline = document.getElementById('tool-calls-timeline');
    toolCallsCount = document.getElementById('tool-calls-count');
}

function setupFileChangeListening() {
    console.log('[DEBUG] Setting up file change listening for iteration', ITERATION_NUM, 'of session', SESSION_ID);

    // Check if socket.io is available
    if (typeof io === 'undefined') {
        console.warn('[DEBUG] Socket.io not available, file watching disabled');
        return;
    }

    // Register auto-refresh callback for this session
    if (window.WebUIUtils && window.WebUIUtils.registerSessionAutoRefresh) {
        window.WebUIUtils.registerSessionAutoRefresh(SESSION_ID, function(data) {
            console.log('[DEBUG] Reloading iteration data due to session file change');
            loadIterationData();
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

function setupScrollPositionPreservation() {
    console.log('[DEBUG] Setting up scroll position preservation for iteration page');

    // Save scroll position on scroll events (original mechanism)
    window.addEventListener('scroll', function() {
        const scrollY = window.pageYOffset;
        sessionStorage.setItem('webui_iteration_scroll_position', scrollY.toString());
    });

    console.log('[DEBUG] Scroll position preservation enabled for iteration page');
}



function restoreScrollPositionImmediately() {
    // Only restore on actual page reload, not navigation
    const isReload = performance.navigation && performance.navigation.type === 1; // TYPE_RELOAD

    if (!isReload) {
        console.log('[DEBUG] Navigation detected - starting at top, clearing saved iteration position');
        sessionStorage.removeItem('webui_iteration_scroll_position');
        return false;
    }

    const savedScrollY = sessionStorage.getItem('webui_iteration_scroll_position');
    if (savedScrollY && savedScrollY !== 'undefined' && savedScrollY !== 'null') {
        const scrollPosition = parseInt(savedScrollY, 10);
        console.log(`[DEBUG] Reload detected - immediate iteration scroll restore to: ${scrollPosition}px`);
        window.scrollTo(0, scrollPosition);

        // Safety check: verify scroll position after content loads and adjust if needed
        setTimeout(() => {
            const currentScroll = window.pageYOffset || document.documentElement.scrollTop;
            const documentHeight = Math.max(
                document.body.scrollHeight,
                document.body.offsetHeight,
                document.documentElement.clientHeight,
                document.documentElement.scrollHeight,
                document.documentElement.offsetHeight
            );

            // If we couldn't scroll to the right position (content too short) or position changed
            if (Math.abs(currentScroll - scrollPosition) > 5 && scrollPosition <= documentHeight) {
                console.log(`[DEBUG] Adjusting iteration scroll position from ${currentScroll} to ${scrollPosition}`);
                window.scrollTo(0, scrollPosition);
            }
            console.log('[DEBUG] Iteration scroll position restored');
        }, 100); // Small delay to allow content to render

        return true; // Indicate scroll was restored
    } else {
        // No saved position
        console.log('[DEBUG] No saved iteration scroll position found for reload');
        return false;
    }
}


// Load iteration data from API
async function loadIterationData() {
    try {
        const response = await fetch(`/api/sessions/${SESSION_ID}/iteration/${ITERATION_NUM}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        iterationData = await response.json();
        renderIterationHeader();
        renderToolCalls();
        renderLLMResponse();


    } catch (error) {
        console.error('Error loading iteration data:', error);
        const errorType = window.t ? window.t('iteration.title', { number: '' }).trim() : 'Iteration Data';
        WebUIUtils.showErrorState('#iteration-header-info', error.message || 'Failed to load iteration data', {
            errorType,
            retryCallback: 'loadIterationData()'
        });
    }
}

function renderIterationHeader() {
    if (!iterationHeaderInfo || !iterationData) return;
    
    const template = document.getElementById('iteration-header-template');
    if (!template) {
        console.error('Iteration header template not found');
        return;
    }
    
    const headerElement = template.content.cloneNode(true);
    
    // Basic iteration info
    const iterationNumber = headerElement.querySelector('.iteration-number');
    const statusIcon = headerElement.querySelector('.status-icon');
    const statusText = headerElement.querySelector('.status-text');
    const statusBadge = headerElement.querySelector('.status-badge');
    const startTime = headerElement.querySelector('.start-time');
    const duration = headerElement.querySelector('.duration');
    
    iterationNumber.textContent = iterationData.iteration;
    statusIcon.className = `status-icon fas ${getStatusIcon(iterationData.status)}`;
    statusText.textContent = window.t ? window.t('status.' + iterationData.status.toLowerCase()) : iterationData.status;
    statusBadge.className = `status-badge ${getStatusClass(iterationData.status)}`;
    
    if (iterationData.start_time) {
        startTime.textContent = WebUIUtils.formatTimestamp(iterationData.start_time);
    }
    
    if (iterationData.start_time && iterationData.end_time) {
        duration.textContent = WebUIUtils.formatDuration(iterationData.start_time, iterationData.end_time);
        headerElement.querySelector('.duration-item').style.display = 'block';
    } else {
        headerElement.querySelector('.duration-item').style.display = 'none';
    }
    
    // Tool call summary
    const toolCalls = iterationData.tool_calls || [];
    const sqlCalls = toolCalls.filter(call => call.tool === 'execute_sql');
    const memoryCalls = toolCalls.filter(call => call.tool === 'memory');
    
    headerElement.querySelector('.total-calls').textContent = toolCalls.length;
    headerElement.querySelector('.sql-calls').textContent = sqlCalls.length;
    headerElement.querySelector('.memory-calls').textContent = memoryCalls.length;
    
    // Translate all elements with data-i18n attributes in the cloned template
    if (window.translateElement) {
        window.translateElement(headerElement);
    }

    // Clear and append
    iterationHeaderInfo.innerHTML = '';
    iterationHeaderInfo.appendChild(headerElement);
}

function renderToolCallsSequentially(toolCalls, template) {
    const totalDuration = 1000; // 1 second total
    const animationDuration = 400; // Keep individual animation speed consistent
    const maxDelay = totalDuration - animationDuration; // 600ms maximum delay

    // Calculate delay between items for dynamic scaling
    const delayBetweenItems = toolCalls.length > 1
        ? maxDelay / (toolCalls.length - 1)
        : 0;

    console.log(`[DEBUG] Rendering ${toolCalls.length} tool calls sequentially with ${delayBetweenItems.toFixed(1)}ms intervals (1s total)`);

    toolCalls.forEach((toolCall, index) => {
        const toolCallElement = createToolCallElement(toolCall, template, iterationData.start_time);
        const item = toolCallElement.querySelector('.tool-call-item');

        // Calculate dynamic delay
        const delay = Math.round(index * delayBetweenItems);
        item.style.setProperty('--slide-delay', `${delay}ms`);
        item.classList.add('tool-call-item-sequential');

        console.log(`[DEBUG] Tool call ${toolCall.id} will animate with ${delay}ms delay`);

        // Remove animation class after animation completes
        const totalDelay = delay + animationDuration;
        setTimeout(() => {
            item.classList.remove('tool-call-item-sequential');
            item.style.removeProperty('--slide-delay');
            console.log(`[DEBUG] Removed sequential animation class for tool call: ${toolCall.id}`);
        }, totalDelay);

        toolCallsTimeline.appendChild(toolCallElement);
    });

    // Apply syntax highlighting after all elements are added
    if (typeof hljs !== 'undefined') {
        setTimeout(() => {
            // Debug: Check SQL containers before highlighting
            const sqlContainers = document.querySelectorAll('.sql-query pre code.sql');
            sqlContainers.forEach((el, i) => {
                console.log(`🔍 DEBUG: Before hljs - SQL container ${i}:`, el.innerHTML);
            });

            hljs.highlightAll();

            // Debug: Check SQL containers after highlighting
            setTimeout(() => {
                sqlContainers.forEach((el, i) => {
                    console.log(`🔍 DEBUG: After hljs - SQL container ${i}:`, el.innerHTML);
                });
            }, 10);
        }, 50); // Small delay to ensure DOM is updated
    }
}

function renderToolCalls() {
    if (!toolCallsTimeline || !iterationData) return;

    const toolCalls = iterationData.tool_calls || [];

    // Update tool calls count
    if (toolCallsCount) {
        toolCallsCount.textContent = `(${toolCalls.length})`;
    }

    const template = document.getElementById('tool-call-template');
    if (!template) {
        console.error('Tool call template not found');
        return;
    }

    // Get existing tool call IDs to avoid duplicates
    const existingCallIds = new Set();
    const existingItems = toolCallsTimeline.querySelectorAll('.tool-call-item');
    existingItems.forEach(item => {
        if (item.dataset.callId) {
            existingCallIds.add(item.dataset.callId);
        }
    });

    console.log(`[DEBUG] Found ${existingCallIds.size} existing tool calls, ${toolCalls.length} total tool calls`);

    // Determine if this is initial page load (all items are new)
    const isFullRefresh = existingCallIds.size === 0 && toolCalls.length > 0;

    if (toolCalls.length === 0) {
        // Handle empty state - preserve header, only replace content after it
        const header = toolCallsTimeline.querySelector('.tool-calls-header');
        toolCallsTimeline.innerHTML = '';
        if (header) {
            toolCallsTimeline.appendChild(header);
        }

        const emptyState = document.createElement('div');
        emptyState.className = 'empty-state';
        const noToolCallsTitle = window.t ? window.t('iteration.no_tool_calls') : 'No Tool Calls';
        const noToolCallsMessage = window.t ? window.t('iteration.no_tool_calls_message') : 'No tool calls were made in this iteration.';

        emptyState.innerHTML = `
            <i class="fas fa-tools"></i>
            <h3>${noToolCallsTitle}</h3>
            <p>${noToolCallsMessage}</p>
        `;
        toolCallsTimeline.appendChild(emptyState);
        return;
    }

    if (isFullRefresh && isInitialPageLoad) {
        // Clear timeline for clean sequential animation (preserve header)
        const header = toolCallsTimeline.querySelector('.tool-calls-header');
        toolCallsTimeline.innerHTML = '';
        if (header) {
            toolCallsTimeline.appendChild(header);
        }

        console.log('[DEBUG] Full refresh detected - applying sequential animation');
        renderToolCallsSequentially(toolCalls, template);
        isInitialPageLoad = false;
    } else {
        // Existing logic for autorefresh (immediate slide-in) - DON'T clear existing items
        toolCalls.forEach(toolCall => {
            if (!existingCallIds.has(toolCall.id)) {
                console.log(`[DEBUG] Adding new tool call: ${toolCall.id}`);
                const toolCallElement = createToolCallElement(toolCall, template, iterationData.start_time);
                const item = toolCallElement.querySelector('.tool-call-item');

                // Add slide-in animation class for new items
                item.classList.add('tool-call-item-sliding');

                // Remove animation class after animation completes
                setTimeout(() => {
                    item.classList.remove('tool-call-item-sliding');
                    console.log(`[DEBUG] Removed slide-in animation class for tool call: ${toolCall.id}`);
                }, 400);

                toolCallsTimeline.appendChild(toolCallElement);
            }
        });

        // Apply syntax highlighting only for new elements
        if (typeof hljs !== 'undefined') {
            const newElements = toolCallsTimeline.querySelectorAll('.tool-call-item-sliding .code-block');
            newElements.forEach(element => {
                // Debug: Check if this is a SQL element before highlighting
                const sqlCode = element.querySelector('pre code.sql');
                if (sqlCode) {
                    console.log('🔍 DEBUG: Before individual hljs - SQL element:', sqlCode.innerHTML);
                    hljs.highlightElement(element);
                    setTimeout(() => {
                        console.log('🔍 DEBUG: After individual hljs - SQL element:', sqlCode.innerHTML);
                    }, 10);
                } else {
                    hljs.highlightElement(element);
                }
            });
        }
    }
}

function createToolCallElement(toolCall, template, iterationStartTime) {
    const toolCallElement = template.content.cloneNode(true);
    const item = toolCallElement.querySelector('.tool-call-item');

    // Set tool call ID and tool type
    item.dataset.callId = toolCall.id;
    item.dataset.tool = toolCall.tool;

    // Set additional data attributes for memory tools to enable category-specific icon colors
    if (toolCall.tool === 'memory') {
        const action = toolCall.input?.action || 'unknown';
        const category = toolCall.input?.key || toolCall.input?.category || 'unknown';

        item.dataset.action = action;
        item.dataset.category = category;
    }

    // Tool header
    const toolIcon = item.querySelector('.tool-icon');
    const toolName = item.querySelector('.tool-name');
    const callId = item.querySelector('.call-id');
    const executionTime = item.querySelector('.execution-time');
    const timestamp = item.querySelector('.timestamp');

    toolIcon.className = `tool-icon fas ${getToolIcon(toolCall.tool)}`;
    toolName.textContent = getToolDisplayName(toolCall.tool, toolCall);
    callId.textContent = getToolCallDisplayText(toolCall);

    if (toolCall.execution_time && toolCall.tool !== 'memory') {
        executionTime.textContent = WebUIUtils.formatExecutionTime(toolCall.execution_time);
    } else if (toolCall.tool === 'memory') {
        // Add invisible placeholder to maintain two-line layout
        executionTime.innerHTML = '&nbsp;';
    }

    if (toolCall.timestamp && iterationStartTime) {
        timestamp.textContent = formatTimeSinceIterationStart(iterationStartTime, toolCall.timestamp);
    }
    
    // Input section
    const inputSection = item.querySelector('.input-section');
    const inputContent = item.querySelector('.input-content');
    const inputHeader = item.querySelector('.input-section .section-header');
    renderToolInput(toolCall, inputContent);

    // Set up input section toggle
    const inputId = `input-${toolCall.id}`;
    inputContent.id = inputId;
    inputContent.style.display = 'none'; // Will be expanded by default when tool call expands
    if (inputHeader) {
        inputHeader.style.cursor = 'pointer';

        // For memory tools, set initial state to collapsed (down arrow)
        if (toolCall.tool === 'memory') {
            const inputToggleIcon = inputHeader.querySelector('.section-toggle-icon');
            if (inputToggleIcon) {
                inputToggleIcon.className = 'fas fa-chevron-down section-toggle-icon';
            }
            inputHeader.title = 'Click to show input';
        } else {
            inputHeader.title = 'Click to hide input';
        }

        inputHeader.onclick = (e) => {
            // Don't toggle when clicking the copy button
            if (!e.target.closest('.copy-btn')) {
                toggleSection(inputId);
            }
        };
    }

    // Output section
    const outputSection = item.querySelector('.output-section');
    const outputContent = item.querySelector('.output-content');
    const outputHeader = item.querySelector('.output-section .section-header');
    renderToolOutput(toolCall, outputContent);

    // Set up output section toggle
    const outputId = `output-${toolCall.id}`;
    outputContent.id = outputId;
    outputContent.style.display = 'none'; // Will be expanded by default when tool call expands
    if (outputHeader) {
        outputHeader.style.cursor = 'pointer';
        outputHeader.title = 'Click to hide output';
        outputHeader.onclick = (e) => {
            // Don't toggle when clicking the copy button
            if (!e.target.closest('.copy-btn')) {
                toggleSection(outputId);
            }
        };
    }

    // Metadata section
    const metadataSection = item.querySelector('.metadata-section');
    const metadataContent = item.querySelector('.metadata-content');
    const metadataHeader = item.querySelector('.metadata-header');

    if (toolCall.metadata && Object.keys(toolCall.metadata).length > 0) {
        metadataSection.style.display = 'block';
        metadataContent.innerHTML = formatMetadata(toolCall.metadata);

        // Set up toggle functionality
        const metadataId = `metadata-${toolCall.id}`;
        metadataContent.id = metadataId;
        metadataContent.style.display = 'none'; // Collapsed by default

        if (metadataHeader) {
            metadataHeader.style.cursor = 'pointer';
            metadataHeader.onclick = () => toggleSection(metadataId);
        }
    }

    // Set up tool call header toggle functionality
    const toolCallContent = item.querySelector('.tool-call-content');
    const toolCallHeader = item.querySelector('.tool-call-header');
    const contentId = `tool-content-${toolCall.id}`;

    toolCallContent.id = contentId;
    toolCallContent.style.display = 'none'; // Collapsed by default

    if (toolCallHeader) {
        toolCallHeader.style.cursor = 'pointer';
        toolCallHeader.onclick = (e) => {
            // Don't toggle if clicking on a button or link
            if (!e.target.closest('button') && !e.target.closest('a')) {
                toggleToolCall(contentId, inputId, outputId, toolCall.tool);
            }
        };
    }

    // Translate all elements with data-i18n attributes in the cloned template
    if (window.translateElement) {
        window.translateElement(toolCallElement);
    }

    return toolCallElement;
}

function renderToolInput(toolCall, container) {
    const input = toolCall.input || {};

    if (toolCall.tool === 'execute_sql') {
        const rawQuery = input.query || '';
        console.log('🔍 DEBUG: Raw query:', JSON.stringify(rawQuery));

        const parsedQuery = parseQueryFromInput(rawQuery);
        console.log('🔍 DEBUG: Parsed query:', JSON.stringify(parsedQuery));

        const formattedQuery = formatSQLForDisplay(parsedQuery);
        console.log('🔍 DEBUG: Formatted query:', JSON.stringify(formattedQuery));

        const escapedQuery = escapeHtml(formattedQuery);
        console.log('🔍 DEBUG: Escaped query:', JSON.stringify(escapedQuery));

        container.innerHTML = `<pre><code class="sql">${escapedQuery}</code></pre>`;
        console.log('🔍 DEBUG: Container innerHTML after set:', container.innerHTML);

        container.classList.add('sql-query');
    } else if (toolCall.tool === 'memory') {
        container.innerHTML = formatMemoryInput(input);
        container.classList.add('memory-input');
        // Store original JSON for the copy button to access
        container.dataset.originalJson = JSON.stringify(input, null, 2);
    } else {
        const inputStr = typeof input === 'string' ? input : JSON.stringify(input, null, 2);
        container.innerHTML = `<pre><code>${escapeHtml(inputStr)}</code></pre>`;
    }
}

function renderToolOutput(toolCall, container) {
    const output = toolCall.output || '';

    if (toolCall.tool === 'execute_sql') {
        // Format SQL results as table if possible
        container.innerHTML = `<pre>${escapeHtml(output)}</pre>`;
    } else if (toolCall.tool === 'memory') {
        // Memory output shows only key:value format (category shown in tool name)
        const rawValue = toolCall.input?.value || '';
        const memoryContent = rawValue || output;
        container.innerHTML = `<div class="memory-output">${escapeHtml(memoryContent)}</div>`;
        container.classList.add('memory-output-container');
    } else {
        container.innerHTML = `<pre>${escapeHtml(output)}</pre>`;
    }
}

function formatMemoryInput(input) {
    const action = input.action || input.key || 'unknown';
    const actionDisplayName = getMemoryActionDisplayName(action);
    const category = input.key || input.category || 'Unknown';
    const rawValue = input.value || '';

    // Parse key:value format used by memory tool
    let memoryKey = '';
    let actualContent = rawValue;

    if (rawValue.includes(':')) {
        const colonIndex = rawValue.indexOf(':');
        memoryKey = rawValue.substring(0, colonIndex).trim();
        actualContent = rawValue.substring(colonIndex + 1).trim();
    }

    return `
        <div class="memory-input-simple">
            <div class="memory-action-simple">
                <i class="fas ${getMemoryActionIcon(action)}"></i>
                <span class="action-name">${actionDisplayName}</span>
            </div>

            <div class="memory-field-simple">
                <span><strong>Category:</strong> ${escapeHtml(category)}</span>
            </div>

            ${memoryKey ? `
            <div class="memory-field-simple">
                <span><strong>Key:</strong> ${escapeHtml(memoryKey)}</span>
            </div>
            ` : ''}

            ${actualContent ? `
            <div class="memory-field-simple">
                <div class="memory-content-header">
                    <label>Content:</label>
                    <button class="btn btn-xs copy-btn" onclick="copyToClipboard(this)" data-copy-target=".memory-content">
                        <i class="fas fa-copy"></i>
                    </button>
                </div>
                <div class="memory-content">${escapeHtml(actualContent)}</div>
            </div>
            ` : ''}
        </div>
    `;
}


function getMemoryActionDisplayName(action) {
    switch (action) {
        case 'update': return 'Store Memory';
        case 'search': return 'Search Memory';
        case 'get': return 'Retrieve Memory';
        case 'remove': return 'Remove Memory';
        case 'delete': return 'Delete Memory';
        default: return action.charAt(0).toUpperCase() + action.slice(1);
    }
}

function getMemoryActionIcon(action) {
    switch (action) {
        case 'update': return 'fa-save';
        case 'search': return 'fa-search';
        case 'get': return 'fa-download';
        case 'remove': return 'fa-trash-alt';
        case 'delete': return 'fa-trash';
        default: return 'fa-cog';
    }
}



function formatMetadata(metadata) {
    let html = '<div class="metadata-grid">';

    for (const [key, value] of Object.entries(metadata)) {
        html += `
            <div class="metadata-item">
                <strong>${escapeHtml(key)}:</strong>
                <span>${escapeHtml(String(value))}</span>
            </div>
        `;
    }

    html += '</div>';
    return html;
}

function renderLLMResponse() {
    if (!iterationData) return;

    const llmResponseButton = document.querySelector('.llm-response-metric');
    if (!llmResponseButton) return;

    const response = iterationData.llm_response || iterationData.content || '';
    const thinking = iterationData.llm_thinking || '';
    const rawResponse = iterationData.llm_response_raw || response;

    if (response || thinking) {
        llmResponseButton.style.display = 'flex';
        llmResponseButton.classList.remove('muted');

        // Set up click handler to use shared modal
        llmResponseButton.setAttribute('onclick', 'openLLMResponseModal()');

        // Override openLLMResponseModal for this page
        window.openLLMResponseModal = function() {
            if (window.LLMResponseModal) {
                window.LLMResponseModal.open(response, thinking, rawResponse);
            }
        };
    } else {
        llmResponseButton.style.display = 'flex';
        llmResponseButton.classList.add('muted');
        llmResponseButton.removeAttribute('onclick');
    }
}

// Note: LLM Response Modal functions are now in llm-response-modal.js

// Note: getStatusClass and getStatusIcon are now global functions from utils.js

function getToolIcon(tool) {
    switch (tool) {
        case 'execute_sql': return 'fa-database';
        case 'memory': return 'fa-brain';
        default: return 'fa-tools';
    }
}

function getToolDisplayName(tool, toolCall = null) {
    if (tool === 'memory' && toolCall) {
        // For memory tools, show the category name instead of "Memory Operation"
        const category = toolCall.input?.key || toolCall.input?.category || 'Memory';
        return getCategoryDisplayName(category);
    }

    if (window.t) {
        switch (tool) {
            case 'execute_sql': return window.t('iteration.sql_tool');
            case 'memory': return window.t('iteration.memory_tool');
            case 'file': return window.t('iteration.file_tool');
            case 'search': return window.t('iteration.search_tool');
            default: return window.t('iteration.unknown_tool');
        }
    } else {
        switch (tool) {
            case 'execute_sql': return 'SQL Query';
            case 'memory': return 'Memory Operation';
            default: return tool;
        }
    }
}

function getCategoryDisplayName(category) {
    if (window.t) {
        return window.t(`memory.categories.${category}`) ||
               category.charAt(0).toUpperCase() + category.slice(1).replace(/_/g, ' ');
    }
    return category.charAt(0).toUpperCase() + category.slice(1).replace(/_/g, ' ');
}

function getToolCallDisplayText(toolCall) {
    switch (toolCall.tool) {
        case 'execute_sql':
            const rawQuery = toolCall.input?.query || '';
            const parsedQuery = parseQueryFromInput(rawQuery);
            return formatSQLForHeader(parsedQuery);
        case 'memory':
            return formatMemoryInputForHeader(toolCall.input || {});
        default:
            return toolCall.id; // Fallback to original call_ID
    }
}

function formatTimeSinceIterationStart(iterationStartTime, toolCallTimestamp) {
    const diffSeconds = toolCallTimestamp - iterationStartTime;
    const hours = Math.floor(diffSeconds / 3600);
    const minutes = Math.floor((diffSeconds % 3600) / 60);
    const seconds = Math.floor(diffSeconds % 60);

    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

function parseQueryFromInput(query) {
    if (!query) return '';

    // Handle JSON-encoded queries from qwen-agent
    if (typeof query === 'string' && query.trim().startsWith('{"query":')) {
        try {
            const parsed = JSON.parse(query);
            return parsed.query || query;
        } catch (e) {
            // If JSON parsing fails, use original query
            console.warn('Failed to parse SQL query JSON:', e);
            return query;
        }
    }

    return query;
}

function formatSQLForDisplay(query) {
    if (!query) return '';

    // Normalize whitespace first
    let formatted = query.replace(/\s+/g, ' ').trim();

    // Major keywords on new lines with proper indentation
    formatted = formatted
        // Main clauses
        .replace(/\b(SELECT)\b/gi, '\n$1')
        .replace(/\b(FROM)\b/gi, '\n$1')
        .replace(/\b(WHERE)\b/gi, '\n$1')
        .replace(/\b(GROUP BY)\b/gi, '\n$1')
        .replace(/\b(HAVING)\b/gi, '\n$1')
        .replace(/\b(ORDER BY)\b/gi, '\n$1')
        // Joins
        .replace(/\b(INNER JOIN|LEFT JOIN|RIGHT JOIN|FULL JOIN|JOIN)\b/gi, '\n$1')
        // Subqueries and unions
        .replace(/\b(UNION ALL|UNION)\b/gi, '\n$1')
        .replace(/\b(WITH)\b/gi, '\n$1');

    // Format column lists (comma-separated items after SELECT)
    formatted = formatted.replace(
        /(SELECT\s+)(.*?)(\s+FROM)/gsi,
        (match, select, columns, from) => {
            const columnList = columns
                .split(',')
                .map(col => '    ' + col.trim()) // 4-space indent
                .join(',\n');
            return select + '\n' + columnList + from;
        }
    );

    // Format WHERE conditions (AND/OR on new lines)
    formatted = formatted
        .replace(/\b(AND)\b/gi, '\n    $1')  // 4-space indent
        .replace(/\b(OR)\b/gi, '\n    $1');

    // Add spaces around operators
    formatted = formatted
        .replace(/([=<>!]+)/g, ' $1 ')
        .replace(/\s+([=<>!]+)\s+/g, ' $1 '); // Clean up multiple spaces

    // Clean up formatting
    formatted = formatted
        .replace(/\n+/g, '\n')        // Remove double newlines
        .replace(/^\n/, '')           // Remove leading newline
        .replace(/\n\s*\n/g, '\n')    // Remove empty lines
        .replace(/[ ]+/g, ' ');       // Clean up multiple spaces

    // Multiply leading spaces after newlines by 4 to compensate for HTML/highlighter collapse
    formatted = formatted.replace(/\n( +)/g, (match, spaces) => {
        return '\n' + spaces.repeat(4);
    });

    return formatted;
}

function formatSQLForHeader(query) {
    if (!query) return '';

    // Remove extra whitespace and newlines, normalize to single line
    return query
        .replace(/\s+/g, ' ')  // Replace multiple whitespace with single space
        .trim();               // Remove leading/trailing whitespace
}

function formatMemoryOutputForHeader(output) {
    if (!output) return '';

    // Clean up memory output text for single line display
    return output
        .replace(/\n+/g, ' ')  // Replace newlines with spaces
        .replace(/\s+/g, ' ')  // Replace multiple whitespace with single space
        .trim();               // Remove leading/trailing whitespace
}

function formatMemoryInputForHeader(input) {
    if (!input || !input.value) return '';

    // Show only key:value format (category now shown in tool name)
    const rawValue = input.value;

    // Clean up memory content text for single line display
    return rawValue
        .replace(/\n+/g, ' ')  // Replace newlines with spaces
        .replace(/\s+/g, ' ')  // Replace multiple whitespace with single space
        .trim();               // Remove leading/trailing whitespace
}

function toggleSection(sectionId) {
    const sectionContent = document.getElementById(sectionId);
    const sectionHeader = sectionContent.parentElement.querySelector('.section-header, .metadata-header');
    const toggleIcon = sectionHeader.querySelector('.section-toggle-icon, .metadata-toggle-icon');

    if (sectionContent.style.display === 'none') {
        sectionContent.style.display = 'block';
        if (toggleIcon) {
            toggleIcon.className = toggleIcon.className.replace('fa-chevron-down', 'fa-chevron-up');
        }
        if (sectionId.includes('metadata')) {
            sectionHeader.title = 'Click to hide metadata';
        } else if (sectionId.includes('input')) {
            sectionHeader.title = 'Click to hide input';
        } else if (sectionId.includes('output')) {
            sectionHeader.title = 'Click to hide output';
        }
    } else {
        sectionContent.style.display = 'none';
        if (toggleIcon) {
            toggleIcon.className = toggleIcon.className.replace('fa-chevron-up', 'fa-chevron-down');
        }
        if (sectionId.includes('metadata')) {
            sectionHeader.title = 'Click to show metadata';
        } else if (sectionId.includes('input')) {
            sectionHeader.title = 'Click to show input';
        } else if (sectionId.includes('output')) {
            sectionHeader.title = 'Click to show output';
        }
    }
}

function toggleToolCall(contentId, inputId, outputId, toolType) {
    const content = document.getElementById(contentId);
    const header = content.parentElement.querySelector('.tool-call-header');
    const toggleIcon = header.querySelector('.tool-call-toggle-icon');

    if (content.style.display === 'none') {
        // Expanding: show content and set default states
        content.style.display = 'block';

        // Expand sections based on tool type
        const inputContent = document.getElementById(inputId);
        const outputContent = document.getElementById(outputId);

        // For memory tools, keep Input collapsed by default
        if (inputContent && toolType !== 'memory') {
            inputContent.style.display = 'block';
            const inputToggleIcon = inputContent.parentElement.querySelector('.section-toggle-icon');
            if (inputToggleIcon) {
                inputToggleIcon.className = inputToggleIcon.className.replace('fa-chevron-down', 'fa-chevron-up');
            }
        }

        // Always expand Output by default for all tools
        if (outputContent) {
            outputContent.style.display = 'block';
            const outputToggleIcon = outputContent.parentElement.querySelector('.section-toggle-icon');
            if (outputToggleIcon) {
                outputToggleIcon.className = outputToggleIcon.className.replace('fa-chevron-down', 'fa-chevron-up');
            }
        }

        // Update tool call toggle icon
        if (toggleIcon) {
            toggleIcon.className = toggleIcon.className.replace('fa-chevron-down', 'fa-chevron-up');
        }
        header.title = 'Click to collapse tool call';
    } else {
        // Collapsing: hide content
        content.style.display = 'none';

        // Update tool call toggle icon
        if (toggleIcon) {
            toggleIcon.className = toggleIcon.className.replace('fa-chevron-up', 'fa-chevron-down');
        }
        header.title = 'Click to expand tool call';
    }

    // Update expand all button state based on current state
    updateExpandAllButtonState();
}

function updateExpandAllButtonState() {
    const toolCallItems = document.querySelectorAll('.tool-call-item');
    const expandedCount = Array.from(toolCallItems).filter(item => {
        const callId = item.dataset.callId;
        const content = document.getElementById(`tool-content-${callId}`);
        return content && content.style.display !== 'none';
    }).length;

    const expandAllBtn = document.getElementById('expand-all-btn');
    if (!expandAllBtn) return;

    const expandAllText = expandAllBtn.querySelector('.expand-all-text');
    const expandAllIcon = expandAllBtn.querySelector('i');

    if (expandedCount === toolCallItems.length && toolCallItems.length > 0) {
        // All expanded
        allExpanded = true;
        expandAllText.textContent = window.t ? window.t('session.collapse_all') : 'Collapse All';
        expandAllIcon.className = 'fas fa-compress-alt';
    } else {
        // Not all expanded
        allExpanded = false;
        expandAllText.textContent = window.t ? window.t('session.expand_all') : 'Expand All';
        expandAllIcon.className = 'fas fa-expand-alt';
    }
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };

    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

// Copy to clipboard function (uses the global utility)
function copyToClipboard(button) {
    if (window.WebUIUtils && window.WebUIUtils.copyToClipboard) {
        window.WebUIUtils.copyToClipboard(button);
    }
}

// File change listening is now handled by setupFileChangeListening() function above

// Expand All functionality
let allExpanded = false;

function toggleExpandAll() {
    const expandAllIndicator = document.getElementById('expand-all-indicator');
    const expandText = expandAllIndicator.querySelector('.expand-text');
    const expandAllIcon = expandAllIndicator.querySelector('i');

    const toolCallItems = document.querySelectorAll('.tool-call-item');

    if (!allExpanded) {
        // Expand all tool calls
        toolCallItems.forEach(item => {
            const callId = item.dataset.callId;
            const toolType = item.dataset.tool;
            const contentId = `tool-content-${callId}`;
            const inputId = `input-${callId}`;
            const outputId = `output-${callId}`;

            const content = document.getElementById(contentId);
            if (content && content.style.display === 'none') {
                toggleToolCall(contentId, inputId, outputId, toolType);
            }
        });

        // Update indicator state
        allExpanded = true;
        expandText.textContent = window.t ? window.t('session.collapse_all') : 'Collapse All';
        expandAllIcon.className = 'fas fa-compress-alt';

    } else {
        // Collapse all tool calls
        toolCallItems.forEach(item => {
            const callId = item.dataset.callId;
            const toolType = item.dataset.tool;
            const contentId = `tool-content-${callId}`;
            const inputId = `input-${callId}`;
            const outputId = `output-${callId}`;

            const content = document.getElementById(contentId);
            if (content && content.style.display !== 'none') {
                toggleToolCall(contentId, inputId, outputId, toolType);
            }
        });

        // Update indicator state
        allExpanded = false;
        expandText.textContent = window.t ? window.t('session.expand_all') : 'Expand All';
        expandAllIcon.className = 'fas fa-expand-alt';
    }
}

// Make functions globally available
window.copyToClipboard = copyToClipboard;
window.toggleExpandAll = toggleExpandAll;