// Memory page functionality

// Get session ID from body data attribute
const SESSION_ID = WebUIUtils.getSessionId();

let currentMemoryFilter = 'all';
let allMemoryItems = [];

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    if (!SESSION_ID) {
        console.error('SESSION_ID not defined');
        return;
    }

    loadMemoryData();

    // Register auto-refresh callback for this session
    if (window.WebUIUtils && window.WebUIUtils.registerSessionAutoRefresh) {
        window.WebUIUtils.registerSessionAutoRefresh(SESSION_ID, function(data) {
            if (data.event_type === 'modified') {
                console.log('[DEBUG] Reloading memory data due to session file change');
                loadMemoryData();
            }
        });
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        if (window.WebUIUtils && window.WebUIUtils.unregisterSessionAutoRefresh) {
            window.WebUIUtils.unregisterSessionAutoRefresh(SESSION_ID);
        }
    });
});

// Load memory data from API
async function loadMemoryData() {
    const loadingState = document.getElementById('loading-state');
    const memoryContent = document.getElementById('memory-content');

    try {
        loadingState.style.display = 'block';
        memoryContent.style.display = 'none';

        const response = await fetch(`/api/sessions/${SESSION_ID}/memory`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const memoryData = await response.json();
        renderMemoryData(memoryData);

        loadingState.style.display = 'none';
        memoryContent.style.display = 'block';

    } catch (error) {
        console.error('Error loading memory data:', error);
        loadingState.style.display = 'none';
        const errorTitle = window.t ? window.t('errors.loading_error', { type: window.t('navigation.memory') }) : 'Error Loading Memory';
        const errorMessage = window.t ? window.t('errors.failed_to_load', { type: window.t('navigation.memory').toLowerCase(), message: error.message }) : `Failed to load memory data: ${error.message}`;
        const retryText = window.t ? window.t('errors.retry') : 'Retry';

        memoryContent.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>${errorTitle}</h3>
                <p>${errorMessage}</p>
                <button class="btn btn-primary" onclick="loadMemoryData()">
                    <i class="fas fa-retry"></i> ${retryText}
                </button>
            </div>
        `;
        memoryContent.style.display = 'block';
    }
}

function renderMemoryData(memoryData) {
    const memoryContent = document.getElementById('memory-content');
    if (!memoryContent) return;

    const categories = memoryData.memory_categories || {};

    if (Object.keys(categories).length === 0) {
        const noDataTitle = window.t ? window.t('memory.empty.no_data_title') : 'No Memory Data';
        const noDataMessage = window.t ? window.t('memory.empty.no_data_message') : 'No memory has been stored in this session yet.';

        memoryContent.innerHTML = `
            <div class="empty-memory">
                <i class="fas fa-brain"></i>
                <h3>${noDataTitle}</h3>
                <p>${noDataMessage}</p>
            </div>
        `;
        return;
    }

    // Collect all memory items into a flat array
    allMemoryItems = [];

    for (const [category, data] of Object.entries(categories)) {
        const items = data.items || {};

        // Items are objects with 'content', 'iteration', 'timestamp' properties
        Object.entries(items).forEach(([key, value]) => {
            allMemoryItems.push({
                category: category,
                key: key,
                content: value.content,
                iteration: value.iteration || 0,
                timestamp: value.timestamp || ''
            });
        });
    }

    // Sort by category first, then chronologically within category
    allMemoryItems.sort((a, b) => {
        if (a.category !== b.category) {
            return a.category.localeCompare(b.category);
        }
        if (a.iteration !== b.iteration) {
            return a.iteration - b.iteration; // Chronological order
        }
        return new Date(a.timestamp) - new Date(b.timestamp);
    });

    // Get unique categories for filters
    const uniqueCategories = [...new Set(allMemoryItems.map(item => item.category))];

    const itemsLabel = window.t ? window.t('memory.stats.items') : 'Items';
    const categoriesLabel = window.t ? window.t('memory.stats.categories') : 'Categories';
    const allCategoriesText = window.t ? window.t('memory.filter.all_categories') : 'All Categories';

    let html = `
        <div class="memory-controls">
            <div class="memory-stats">
                <div class="stat-item">
                    <span class="stat-number">${memoryData.total_items || 0}</span>
                    <span class="stat-label">${itemsLabel}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number">${Object.keys(categories).length}</span>
                    <span class="stat-label">${categoriesLabel}</span>
                </div>
            </div>
            <div class="memory-filter-dropdown">
                <div class="custom-select" id="memory-filter-select">
                    <div class="select-trigger">
                        <i class="fas fa-search"></i>
                        <span class="select-text">${allCategoriesText}</span>
                        <i class="fas fa-chevron-down select-arrow"></i>
                    </div>
                    <div class="select-options">
                        <div class="select-option ${currentMemoryFilter === 'all' ? 'selected' : ''}" data-value="all">
                            <i class="fas fa-search"></i>
                            <span>${allCategoriesText}</span>
                        </div>
    `;

    uniqueCategories.forEach(category => {
        const categoryDisplayName = getCategoryDisplayName(category);
        const categoryIcon = getCategoryIcon(category);
        html += `
                        <div class="select-option ${currentMemoryFilter === category ? 'selected' : ''}" data-value="${category}">
                            <i class="fas ${categoryIcon}"></i>
                            <span>${categoryDisplayName}</span>
                        </div>
        `;
    });

    html += `
                    </div>
                </div>
            </div>
        </div>

        <div class="memory-categories">
            <div class="memory-feed" id="memory-feed">
                ${renderMemoryFeed()}
            </div>
        </div>
    `;

    memoryContent.innerHTML = html;

    // Initialize custom dropdown
    initializeCustomDropdown();

    // Add click event listeners to memory cards
    addMemoryCardListeners();
}

function renderMemoryFeed() {
    const filteredItems = currentMemoryFilter === 'all'
        ? allMemoryItems
        : allMemoryItems.filter(item => item.category === currentMemoryFilter);

    if (filteredItems.length === 0) {
        const noItemsTitle = window.t ? window.t('memory.empty.no_items_title') : 'No Items Found';
        const noItemsMessage = window.t ? window.t('memory.empty.no_items_message') : 'No memory items match the selected filter.';

        return `
            <div class="empty-memory">
                <i class="fas fa-search"></i>
                <h3>${noItemsTitle}</h3>
                <p>${noItemsMessage}</p>
            </div>
        `;
    }

    return filteredItems.map(item => renderMemoryCard(item)).join('');
}

function renderMemoryCard(item) {
    const categoryDisplayName = getCategoryDisplayName(item.category);
    const iterationDisplay = item.iteration > 0 ? `<span class="iteration-badge">Iter ${item.iteration}</span>` : '';

    const keyDisplay = item.key ? `<div class="memory-key">${item.key}</div>` : '';

    const copyTooltip = window.t ? window.t('memory.actions.copy_tooltip') : 'Click to copy';
    const verifyButton = item.key ? `<button class="btn-verify" onclick="verifyMemoryItem('${escapeHtml(item.category)}', '${escapeHtml(item.key)}', event)" title="Verify this memory"><i class="fas fa-check-circle"></i></button>` : '';

    return `<div class="memory-item ${item.category}" title="${copyTooltip}"><div class="memory-header"><div class="memory-header-left"><i class="fas ${getCategoryIcon(item.category)}"></i><span class="category-badge ${item.category}">${categoryDisplayName}</span>${verifyButton}</div><div class="memory-header-right">${iterationDisplay}</div></div>${keyDisplay}<div class="memory-content">${escapeHtml(item.content)}</div></div>`;
}

function formatMemoryTimestamp(timestamp) {
    try {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMinutes = Math.floor((now - date) / (1000 * 60));

        if (diffMinutes < 1) return window.t ? window.t('time.just_now') : 'Just now';
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

function initializeCustomDropdown() {
    const customSelect = document.getElementById('memory-filter-select');
    if (!customSelect) return;

    const trigger = customSelect.querySelector('.select-trigger');
    const options = customSelect.querySelector('.select-options');
    const selectText = customSelect.querySelector('.select-text');
    const selectIcon = trigger.querySelector('i:first-child');

    // Toggle dropdown
    trigger.addEventListener('click', function() {
        customSelect.classList.toggle('open');
    });

    // Handle option selection
    customSelect.querySelectorAll('.select-option').forEach(option => {
        option.addEventListener('click', function() {
            const value = this.dataset.value;
            const text = this.querySelector('span').textContent;
            const icon = this.querySelector('i').className;

            // Update trigger
            selectText.textContent = text;
            selectIcon.className = icon;

            // Update selected state
            customSelect.querySelectorAll('.select-option').forEach(opt => opt.classList.remove('selected'));
            this.classList.add('selected');

            // Close dropdown
            customSelect.classList.remove('open');

            // Apply filter
            filterMemory(value);
        });
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(event) {
        if (!customSelect.contains(event.target)) {
            customSelect.classList.remove('open');
        }
    });
}

function filterMemory(category) {
    currentMemoryFilter = category;

    // Update feed
    const feedContainer = document.getElementById('memory-feed');
    if (feedContainer) {
        feedContainer.innerHTML = renderMemoryFeed();
        // Re-add event listeners after updating feed content
        addMemoryCardListeners();
    }
}

function copyMemoryItem(content) {
    // Try modern clipboard API first
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(content).then(() => {
            const successMessage = window.t ? window.t('memory.actions.copied') : 'Memory item copied to clipboard';
            WebUIUtils.showSuccess(successMessage);
        }).catch(err => {
            console.error('Failed to copy memory item (clipboard API):', err);
            // Fallback to legacy method
            copyMemoryItemFallback(content);
        });
    } else {
        // Use fallback method if clipboard API not available
        copyMemoryItemFallback(content);
    }
}

function copyMemoryItemFallback(content) {
    try {
        // Create temporary textarea element
        const textarea = document.createElement('textarea');
        textarea.value = content;
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        textarea.style.top = '-9999px';
        document.body.appendChild(textarea);

        // Select and copy
        textarea.focus();
        textarea.select();
        const successful = document.execCommand('copy');

        // Clean up
        document.body.removeChild(textarea);

        if (successful) {
            const successMessage = window.t ? window.t('memory.actions.copied') : 'Memory item copied to clipboard';
            WebUIUtils.showSuccess(successMessage);
        } else {
            throw new Error('execCommand copy failed');
        }
    } catch (err) {
        console.error('Failed to copy memory item (fallback):', err);
        const errorMessage = window.t ? window.t('memory.actions.copy_failed') : 'Failed to copy to clipboard';
        WebUIUtils.showError(errorMessage);
    }
}

function addMemoryCardListeners() {
    const memoryCards = document.querySelectorAll('.memory-item');

    memoryCards.forEach(card => {
        card.addEventListener('click', function(event) {
            // Don't copy if clicking on verify button
            if (event.target.closest('.btn-verify')) {
                return;
            }

            // Get content from the displayed content div
            const contentDiv = card.querySelector('.memory-content');
            if (contentDiv) {
                const content = contentDiv.textContent || contentDiv.innerText;
                if (content) {
                    copyMemoryItem(content);
                }
            }
        });
    });
}

function getCategoryDisplayName(category) {
    if (window.t) {
        return window.t(`memory.categories.${category}`) ||
               category.charAt(0).toUpperCase() + category.slice(1).replace(/_/g, ' ');
    }
    return category.charAt(0).toUpperCase() + category.slice(1).replace(/_/g, ' ');
}

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
        'user_requests': 'fa-comments'
    };
    return icons[category] || 'fa-folder';
}

function getCategoryEmoji(category) {
    const emojis = {
        'insights': '💡',
        'patterns': '📈',
        'explored_areas': '🗺️',
        'key_findings': '⭐',
        'opportunities': '💰',
        'data_issues': '⚠️',
        'metrics': '📊',
        'context': 'ℹ️',
        'data_milestones': '🚩',
        'user_requests': '💬'
    };
    return emojis[category] || '📁';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function refreshMemory() {
    loadMemoryData();
}

function exportMemory() {
    if (allMemoryItems && allMemoryItems.length > 0) {
        const dataStr = JSON.stringify(allMemoryItems, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);

        const exportFileDefaultName = `session_${SESSION_ID}_memory.json`;

        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();

        const successMessage = window.t ? window.t('memory.actions.export') + ' ' + window.t('common.success').toLowerCase() : 'Memory data exported successfully';
        WebUIUtils.showSuccess(successMessage);
    }
}

async function verifyMemoryItem(category, key, event) {
    event.stopPropagation();

    const button = event.target.closest('.btn-verify');
    const originalHTML = button.innerHTML;
    button.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i>';
    button.disabled = true;

    try {
        const response = await fetch(`/api/sessions/${SESSION_ID}/memory/verify`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({category, key})
        });

        const result = await response.json();

        if (response.ok) {
            showVerificationModal(result, category, key);
        } else {
            WebUIUtils.showError('Verification failed: ' + (result.error || 'Unknown error'));
        }

    } catch (error) {
        console.error('Verification error:', error);
        WebUIUtils.showError('Verification failed: ' + error.message);
    } finally {
        button.innerHTML = originalHTML;
        button.disabled = false;
    }
}

function showVerificationModal(result, category, key) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'verification-modal';
    modal.style.display = 'flex';

    const confidenceClass = result.confidence || 'low';
    const verifiedIcon = result.verified ? 'fa-check-circle' : 'fa-times-circle';
    const verifiedText = result.verified ? 'Verified' : 'Not Verified';

    const updateSection = result.recommendation === 'update' && result.updated_value ? `
        <div class="verification-update">
            <strong>Recommended Update:</strong>
            <div class="value-comparison">
                <div class="new-value">${escapeHtml(result.updated_value)}</div>
            </div>
        </div>
    ` : '';

    const applyButton = result.recommendation === 'update' && result.updated_value ? `
        <button class="btn btn-primary" onclick="applyMemoryUpdate('${escapeHtml(category)}', '${escapeHtml(key)}', \`${escapeHtml(result.updated_value)}\`)">
            <i class="fas fa-check"></i> Apply Update
        </button>
    ` : '';

    modal.innerHTML = `
        <div class="modal-content verification-modal-content">
            <div class="modal-header" onclick="closeVerificationModal()">
                <h3>
                    <i class="fas fa-search"></i>
                    <span>Memory Verification</span>
                </h3>
            </div>
            <div class="modal-body">
                <div class="verification-status ${confidenceClass}">
                    <i class="fas ${verifiedIcon}"></i>
                    <span>${verifiedText}</span>
                    <span class="confidence-badge">${(result.confidence || 'unknown').toUpperCase()}</span>
                </div>
                <div class="verification-reasoning">
                    <strong>Reasoning:</strong>
                    <p>${escapeHtml(result.reasoning || 'No reasoning provided')}</p>
                </div>
                <div class="verification-evidence">
                    <strong>Evidence:</strong>
                    <pre>${escapeHtml(result.evidence || 'No evidence provided')}</pre>
                </div>
                ${updateSection}
            </div>
            <div class="modal-footer">
                <div class="keyboard-hint">
                    <kbd>ESC</kbd> to close
                </div>
                ${applyButton}
                <button class="btn btn-secondary" onclick="closeVerificationModal()">Close</button>
            </div>
        </div>
        <div class="modal-backdrop" onclick="closeVerificationModal()"></div>
    `;

    // Add ESC key handler
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            closeVerificationModal();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);

    document.body.appendChild(modal);
}

async function applyMemoryUpdate(category, key, newValue) {
    try {
        const response = await fetch(`/api/sessions/${SESSION_ID}/memory/update`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({category, key, new_value: newValue})
        });

        if (response.ok) {
            WebUIUtils.showSuccess('Memory updated successfully');
            closeVerificationModal();
            loadMemoryData();
        } else {
            const error = await response.json();
            WebUIUtils.showError('Update failed: ' + (error.error || 'Unknown error'));
        }
    } catch (error) {
        WebUIUtils.showError('Update failed: ' + error.message);
    }
}

function closeVerificationModal() {
    const modal = document.getElementById('verification-modal');
    if (modal) modal.remove();
}

// Make functions globally available
window.filterMemory = filterMemory;
window.copyMemoryItem = copyMemoryItem;
window.refreshMemory = refreshMemory;
window.exportMemory = exportMemory;
window.verifyMemoryItem = verifyMemoryItem;
window.applyMemoryUpdate = applyMemoryUpdate;
window.closeVerificationModal = closeVerificationModal;