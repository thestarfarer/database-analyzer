// Sessions page functionality

let allSessions = [];
let filteredSessions = [];
let isActualInitialLoad = true;
let shouldUseSporopediaAnimation = false;

// DOM elements
let sessionsGrid;
let searchInput;
let statusFilter;
let sortOrder;
let sessionsStats;
let emptyState;

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    console.log('[DEBUG] DOM Content Loaded - Initializing sessions page');

    // Disable browser's default scroll restoration to prevent interference
    if ('scrollRestoration' in history) {
        history.scrollRestoration = 'manual';
    }

    // Restore scroll position immediately before any content loads
    restoreScrollPositionImmediately();


    initializeDOMElements();
    setupEventListeners();

    // Check if this is a page refresh (not initial visit)
    // If user has navigated before and is coming back or refreshing, use animation
    const hasVisitedBefore = sessionStorage.getItem('webui_visited');
    const isPageRefresh = performance.navigation && performance.navigation.type === 1;

    if (hasVisitedBefore || isPageRefresh) {
        console.log('[DEBUG] Page refresh or return visit detected, enabling Sporopedia animation');
        shouldUseSporopediaAnimation = true;
    }

    // Mark that we've visited this page
    sessionStorage.setItem('webui_visited', 'true');

    loadSessions();

    // Set up file change listening for real-time updates
    setupFileChangeListening();

    // Set up dropdown click outside handler
    setupDropdownHandlers();

    // Set up scroll position preservation
    setupScrollPositionPreservation();
});

function setupDropdownHandlers() {
    // Close dropdown when clicking outside
    document.addEventListener('click', function(event) {
        // If click is not inside a dropdown, close all dropdowns
        if (!event.target.closest('.dropdown')) {
            document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
                menu.classList.remove('show');
            });
        }
    });
}

function setupScrollPositionPreservation() {
    console.log('[DEBUG] Setting up scroll position preservation');

    // Save scroll position on scroll events (original mechanism)
    window.addEventListener('scroll', function() {
        const scrollY = window.pageYOffset;
        sessionStorage.setItem('webui_scroll_position', scrollY.toString());
    });

    console.log('[DEBUG] Scroll position preservation enabled');
}


function restoreScrollPosition() {
    const savedScrollY = sessionStorage.getItem('webui_scroll_position');
    if (savedScrollY && savedScrollY !== 'undefined' && savedScrollY !== 'null') {
        const scrollPosition = parseInt(savedScrollY, 10);
        console.log(`[DEBUG] Restoring scroll position: ${scrollPosition}px`);

        // Delay depends on whether Sporopedia animation is running
        const delay = shouldUseSporopediaAnimation ? 800 : 150; // Wait for animation completion

        setTimeout(() => {
            window.scrollTo(0, scrollPosition);
            console.log('[DEBUG] Scroll position restored');
        }, delay);
    } else {
        console.log('[DEBUG] No saved scroll position found');
    }
}


function restoreScrollPositionImmediately() {
    // Only restore on actual page reload, not navigation
    const isReload = performance.navigation && performance.navigation.type === 1; // TYPE_RELOAD

    if (!isReload) {
        console.log('[DEBUG] Navigation detected - starting at top, clearing saved position');
        sessionStorage.removeItem('webui_scroll_position');
        return false;
    }

    const savedScrollY = sessionStorage.getItem('webui_scroll_position');
    if (savedScrollY && savedScrollY !== 'undefined' && savedScrollY !== 'null') {
        const scrollPosition = parseInt(savedScrollY, 10);
        console.log(`[DEBUG] Reload detected - immediate scroll restore to: ${scrollPosition}px`);
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
                console.log(`[DEBUG] Adjusting scroll position from ${currentScroll} to ${scrollPosition}`);
                window.scrollTo(0, scrollPosition);
            }
            console.log('[DEBUG] Scroll position restored');
        }, 100); // Small delay to allow content to render

        return true; // Indicate scroll was restored
    } else {
        // No saved position
        console.log('[DEBUG] No saved scroll position found for reload');
        return false;
    }
}

function setupFileChangeListening() {
    console.log('[DEBUG] Setting up file change listening');

    // Register global auto-refresh callback for sessions list
    if (window.WebUIUtils && window.WebUIUtils.registerGlobalAutoRefresh) {
        window.WebUIUtils.registerGlobalAutoRefresh(function(data) {
            // Use smart updates for all file changes to preserve animations and scroll position
            if (data.event_type === 'created') {
                console.log('[DEBUG] New session created, using smart update');
                loadSessions(false); // Use smart update for new sessions (green flash)
            } else if (data.event_type === 'modified') {
                console.log('[DEBUG] Session modified, using smart update');
                loadSessions(false); // Use smart update for modifications (yellow flash)
            } else if (data.event_type === 'deleted') {
                console.log('[DEBUG] Session deleted, using smart update');
                loadSessions(false); // Use smart update for deletions (red flash)
            }
        });
    } else {
        console.warn('[DEBUG] WebUIUtils not available, auto-refresh disabled');
    }
}

function initializeDOMElements() {
    console.log('[DEBUG] Initializing DOM elements...');
    sessionsGrid = document.getElementById('sessions-grid');
    searchInput = document.getElementById('search-input');
    statusFilter = document.getElementById('status-filter');
    sortOrder = document.getElementById('sort-order');
    sessionsStats = document.getElementById('sessions-stats');
    emptyState = document.getElementById('empty-state');

    console.log('[DEBUG] DOM elements found:', {
        sessionsGrid: !!sessionsGrid,
        searchInput: !!searchInput,
        statusFilter: !!statusFilter,
        sortOrder: !!sortOrder,
        sessionsStats: !!sessionsStats,
        emptyState: !!emptyState
    });
}

function setupEventListeners() {
    console.log('[DEBUG] Setting up event listeners...');
    console.log('[DEBUG] WebUIUtils available:', !!window.WebUIUtils);

    if (searchInput) {
        if (window.WebUIUtils && window.WebUIUtils.debounce) {
            searchInput.addEventListener('input', WebUIUtils.debounce(filterSessions, 300));
            console.log('[DEBUG] Search input listener added with debounce');
        } else {
            console.log('[DEBUG] WebUIUtils.debounce not available, adding direct listener');
            searchInput.addEventListener('input', filterSessions);
        }
    } else {
        console.log('[DEBUG] Search input element not found');
    }

    if (statusFilter) {
        statusFilter.addEventListener('change', filterSessions);
        console.log('[DEBUG] Status filter listener added');
    } else {
        console.log('[DEBUG] Status filter element not found');
    }

    if (sortOrder) {
        sortOrder.addEventListener('change', filterSessions);
        console.log('[DEBUG] Sort order listener added');
    } else {
        console.log('[DEBUG] Sort order element not found');
    }

    // New session button
    const newSessionBtn = document.getElementById('new-session-btn');
    if (newSessionBtn) {
        newSessionBtn.addEventListener('click', createNewSession);
        console.log('[DEBUG] New session button listener added');
    } else {
        console.log('[DEBUG] New session button not found');
    }
}

// Load sessions from API
async function loadSessions(forceRefresh = false) {
    console.log(`[DEBUG] loadSessions called: forceRefresh=${forceRefresh}, existing sessions=${allSessions.length}`);
    try {
        // Only show loading state on initial load or forced refresh
        const isInitialLoad = allSessions.length === 0;
        if (isInitialLoad || forceRefresh) {
            showLoadingState();
        }

        console.log(`[DEBUG] Fetching /api/sessions...`);
        const response = await fetch('/api/sessions');
        console.log(`[DEBUG] Response status: ${response.status}, ok: ${response.ok}`);

        if (!response.ok) {
            console.error(`[DEBUG] HTTP error! status: ${response.status}, statusText: ${response.statusText}`);
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const responseText = await response.text();
        console.log(`[DEBUG] Raw response text:`, responseText.substring(0, 200) + (responseText.length > 200 ? '...' : ''));

        let newSessions;
        try {
            newSessions = JSON.parse(responseText);
            console.log(`[DEBUG] Parsed JSON successfully: ${newSessions.length} sessions`);
        } catch (parseError) {
            console.error(`[DEBUG] JSON parse error:`, parseError);
            throw new Error(`Invalid JSON response: ${parseError.message}`);
        }

        console.log(`[DEBUG] API returned ${newSessions.length} sessions:`, newSessions.map(s => ({id: s.session_id, iterations: s.iterations_count})));

        // If we have existing sessions, do smart update instead of full replace
        if (!isInitialLoad && !forceRefresh && allSessions.length > 0) {
            updateAllSessions(newSessions);
        } else {
            // Full refresh for initial load or forced refresh
            allSessions = newSessions;

            // Enable Sporopedia animation for full refresh (not initial load)
            if (!isInitialLoad && forceRefresh) {
                console.log('[DEBUG] Force refresh detected, enabling Sporopedia animation');
                shouldUseSporopediaAnimation = true;
            }

            filterSessions();
        }

        // Mark that initial load is complete (but don't reset on force refresh)
        if (isActualInitialLoad && isInitialLoad) {
            isActualInitialLoad = false;
        }

        updateStats();

        // Reset refresh counter when data is successfully loaded
        if (window.WebUIUtils && window.WebUIUtils.resetRefreshCounter) {
            window.WebUIUtils.resetRefreshCounter();
        }


    } catch (error) {
        console.error('[DEBUG] Error loading sessions:', error);
        console.error('[DEBUG] Error stack:', error.stack);
        showErrorState(error.message || 'Failed to load sessions');
    }
}

function updateAllSessions(newSessions) {
    // Store previous sessions for deletion detection
    const previousSessions = [...allSessions];

    // Update the allSessions array with new data
    allSessions = newSessions;

    // Detect and handle deletions first
    const deletedCount = handleSessionDeletions(previousSessions, newSessions);

    if (deletedCount > 0) {
        // If sessions were deleted, delay the repositioning to let animation complete
        console.log(`[DEBUG] Delaying repositioning for ${deletedCount} deletion animations`);
        setTimeout(() => {
            console.log(`[DEBUG] Repositioning after deletion animation delay`);
            filterSessions();
        }, 350); // Slightly longer than 300ms animation duration
    } else {
        // No deletions, proceed immediately
        filterSessions();
    }
}

function handleSessionDeletions(previousSessions, newSessions) {
    if (!sessionsGrid) return 0;

    console.log(`[DEBUG] handleSessionDeletions: previous=${previousSessions.length}, new=${newSessions.length}`);
    console.log(`[DEBUG] Previous session IDs:`, previousSessions.map(s => s.session_id));
    console.log(`[DEBUG] New session IDs:`, newSessions.map(s => s.session_id));

    // Create sets for efficient lookup
    const newSessionIds = new Set(newSessions.map(s => s.session_id));
    const deletedSessions = previousSessions.filter(s => !newSessionIds.has(s.session_id));

    console.log(`[DEBUG] Handling deletions: ${deletedSessions.length} sessions deleted`);
    if (deletedSessions.length > 0) {
        console.log(`[DEBUG] Deleted session IDs:`, deletedSessions.map(s => s.session_id));
    }

    let actualDeletions = 0;

    // Apply red flash and removal animation to deleted session cards
    deletedSessions.forEach(deletedSession => {
        const existingCard = sessionsGrid.querySelector(`[data-session-id="${deletedSession.session_id}"]`);
        if (existingCard) {
            console.log(`[DEBUG] Found card in DOM for deleted session: ${deletedSession.session_id}`);
            console.log(`[DEBUG] Applying red flash to deleted session: ${deletedSession.session_id}`);
            removeSessionCard(existingCard);
            actualDeletions++;
        } else {
            console.log(`[DEBUG] Card not found in DOM for deleted session: ${deletedSession.session_id}`);
        }
    });

    return actualDeletions;
}

function showLoadingState() {
    if (sessionsGrid) {
        const loadingText = window.t ? window.t('sessions.loading') : 'Loading sessions...';
        sessionsGrid.innerHTML = `
            <div class="loading-spinner">
                <i class="fas fa-spinner fa-spin"></i>
                <p>${loadingText}</p>
            </div>
        `;
    }
}

function showErrorState(message) {
    const errorType = window.t ? window.t('navigation.sessions') : 'Sessions';
    const retryCallback = 'loadSessions(true)';

    if (allSessions.length === 0) {
        WebUIUtils.showErrorState('#sessions-grid', message, {
            errorType,
            retryCallback
        });
    } else {
        WebUIUtils.showErrorToast(message, { retryCallback });
    }
}

function filterSessions() {
    console.log(`[DEBUG] filterSessions called: allSessions count=${allSessions.length}`);
    const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    const statusValue = statusFilter ? statusFilter.value : '';
    const sortValue = sortOrder ? sortOrder.value : 'desc';

    console.log(`[DEBUG] Filter criteria: searchTerm='${searchTerm}', statusValue='${statusValue}', sortValue='${sortValue}'`);

    // Filter sessions
    filteredSessions = allSessions.filter(session => {
        const matchesSearch = !searchTerm ||
            (session.latest_user_input && session.latest_user_input.toLowerCase().includes(searchTerm)) ||
            session.session_id.includes(searchTerm);

        const matchesStatus = !statusValue || session.status === statusValue;

        return matchesSearch && matchesStatus;
    });

    console.log(`[DEBUG] Filtered to ${filteredSessions.length} sessions`);

    // Sort sessions
    filteredSessions.sort((a, b) => {
        const timeA = new Date(a.start_time).getTime();
        const timeB = new Date(b.start_time).getTime();

        return sortValue === 'desc' ? timeB - timeA : timeA - timeB;
    });

    console.log(`[DEBUG] Sorted sessions, calling renderSessions()`);
    renderSessions();
}

function createPlaceholderCards(count) {
    console.log(`[DEBUG] Creating ${count} placeholder cards`);
    const placeholders = [];

    for (let i = 0; i < count; i++) {
        const placeholder = document.createElement('div');
        placeholder.className = 'session-card session-card-placeholder';
        placeholder.dataset.placeholder = 'true';
        placeholders.push(placeholder);
        sessionsGrid.appendChild(placeholder);
    }

    return placeholders;
}

function removePlaceholderCards() {
    console.log('[DEBUG] Removing placeholder cards');
    const placeholders = sessionsGrid.querySelectorAll('.session-card-placeholder');
    placeholders.forEach(placeholder => placeholder.remove());
}

function renderSessionsWithSporopediaAnimation() {
    console.log('[DEBUG] renderSessionsWithSporopediaAnimation called - Card deck dealing');
    if (!sessionsGrid || filteredSessions.length === 0) {
        renderSessions();
        return;
    }

    // Clear ALL content from sessions grid to ensure clean positioning
    const loadingSpinner = sessionsGrid.querySelector('.loading-spinner');
    const errorState = sessionsGrid.querySelector('.error-state');
    const existingCards = sessionsGrid.querySelectorAll('.session-card');

    if (loadingSpinner) loadingSpinner.remove();
    if (errorState) errorState.remove();
    existingCards.forEach(card => card.remove());

    console.log('[DEBUG] Cleared all grid content for clean card dealing');

    // Get template
    const template = document.getElementById('session-card-template');
    if (!template) {
        console.error('[DEBUG] Session card template not found');
        return;
    }

    // Calculate grid layout to determine final positions
    const gridComputedStyle = window.getComputedStyle(sessionsGrid);
    const gridColumns = gridComputedStyle.getPropertyValue('grid-template-columns').split(' ').length;

    // Get deck origin point (bottom-right corner of screen)
    const deckOriginX = window.innerWidth - 100; // 100px from right edge
    const deckOriginY = window.innerHeight - 100; // 100px from bottom edge

    console.log(`[DEBUG] Deck origin: (${deckOriginX}, ${deckOriginY}), Grid columns: ${gridColumns}`);

    // Create all cards first, positioned at deck origin
    filteredSessions.forEach((session, index) => {
        const newCard = createSessionCard(session, template);
        if (!newCard) {
            console.error(`[DEBUG] Failed to create card for session ${session.session_id}`);
            return;
        }

        // Calculate final grid position
        const row = Math.floor(index / gridColumns);
        const col = index % gridColumns;

        // Insert card at correct DOM position but visually at deck origin
        sessionsGrid.appendChild(newCard);

        // Calculate trajectory from deck origin to final position
        requestAnimationFrame(() => {
            const cardRect = newCard.getBoundingClientRect();
            const sessionsRect = sessionsGrid.getBoundingClientRect();

            // Calculate relative position within the grid
            const targetX = cardRect.left + cardRect.width / 2;
            const targetY = cardRect.top + cardRect.height / 2;

            // Calculate distance from deck origin to target
            const deltaX = deckOriginX - targetX;
            const deltaY = deckOriginY - targetY;

            console.log(`[DEBUG] Card ${index}: from (${deckOriginX}, ${deckOriginY}) to (${targetX}, ${targetY}), delta: (${deltaX}, ${deltaY})`);

            // Set CSS variables for animation trajectory
            newCard.style.setProperty('--origin-x', `${deltaX}px`);
            newCard.style.setProperty('--origin-y', `${deltaY}px`);
            newCard.style.setProperty('--deal-z-index', `${1000 - index}`); // Higher z for cards dealt later
            newCard.style.setProperty('--animation-delay', `${index * 75}ms`); // 75ms between cards

            // Add dealing animation class
            newCard.classList.add('session-card-sporopedia');
        });
    });
}

function renderSessions() {
    console.log(`[DEBUG] renderSessions called: sessionsGrid exists=${!!sessionsGrid}, filteredSessions count=${filteredSessions.length}, shouldUseSporopediaAnimation=${shouldUseSporopediaAnimation}`);
    if (!sessionsGrid) {
        console.error('[DEBUG] sessionsGrid not found, cannot render');
        return;
    }

    if (filteredSessions.length === 0) {
        console.log('[DEBUG] No filtered sessions, showing empty state');
        sessionsGrid.style.display = 'none';
        if (emptyState) {
            emptyState.style.display = 'block';
        }
        return;
    }

    console.log('[DEBUG] Showing sessions grid and hiding empty state');
    sessionsGrid.style.display = 'grid';
    if (emptyState) {
        emptyState.style.display = 'none';
    }

    // Check if we should use Sporopedia animation
    if (shouldUseSporopediaAnimation) {
        console.log('[DEBUG] Using Sporopedia animation');
        shouldUseSporopediaAnimation = false; // Reset flag after use
        renderSessionsWithSporopediaAnimation();
        return;
    }

    const template = document.getElementById('session-card-template');
    if (!template) {
        console.error('[DEBUG] Session card template not found');
        return;
    }

    console.log('[DEBUG] Template found, calling updateSessionCards');
    // Smart update: compare existing cards with filtered sessions
    updateSessionCards(filteredSessions, template, isActualInitialLoad);
}

function updateSessionCards(targetSessions, template, skipAnimations = false) {
    console.log(`[DEBUG] updateSessionCards called with ${targetSessions.length} sessions, skipAnimations=${skipAnimations}`);
    // Clear any loading or error states first
    const loadingSpinner = sessionsGrid.querySelector('.loading-spinner');
    const errorState = sessionsGrid.querySelector('.error-state');
    if (loadingSpinner) loadingSpinner.remove();
    if (errorState) errorState.remove();

    const existingCards = sessionsGrid.querySelectorAll('.session-card');
    const existingSessionIds = new Set();
    const existingCardMap = new Map();

    // Map existing cards by session ID
    existingCards.forEach(card => {
        const sessionId = card.dataset.sessionId;
        if (sessionId) {  // Only add cards with valid session IDs
            existingSessionIds.add(sessionId);
            existingCardMap.set(sessionId, card);
        }
    });

    const targetSessionIds = new Set(targetSessions.map(s => s.session_id));

    // Remove cards that are no longer in filtered results
    // (but skip cards that were already handled by deletion logic)
    existingSessionIds.forEach(sessionId => {
        if (!targetSessionIds.has(sessionId)) {
            const card = existingCardMap.get(sessionId);
            if (card && !card.classList.contains('session-card-exiting')) {
                // Only remove if not already being removed by deletion handler
                removeSessionCard(card);
            }
        }
    });

    // Add or update cards for target sessions
    targetSessions.forEach((session, index) => {
        const existingCard = existingCardMap.get(session.session_id);

        if (existingCard) {
            // Update existing card
            updateSessionCard(existingCard, session);
            // Ensure correct order
            const currentIndex = Array.from(sessionsGrid.children).indexOf(existingCard);
            if (currentIndex !== index) {
                console.log(`[DEBUG] Repositioning card ${session.session_id} from index ${currentIndex} to ${index}`);
                // Move card to correct position
                if (index === sessionsGrid.children.length - 1) {
                    sessionsGrid.appendChild(existingCard);
                } else {
                    sessionsGrid.insertBefore(existingCard, sessionsGrid.children[index]);
                }
                // Mark card as repositioned to avoid false update detection
                existingCard.dataset.justRepositioned = 'true';
                setTimeout(() => {
                    delete existingCard.dataset.justRepositioned;
                }, 100);
            }
        } else {
            // Create new card
            const newCard = createSessionCard(session, template);
            if (!newCard) {
                console.error(`[DEBUG] Failed to create card for session ${session.session_id}, skipping`);
                return;
            }

            // Insert at correct position
            if (index === sessionsGrid.children.length) {
                sessionsGrid.appendChild(newCard);
            } else {
                sessionsGrid.insertBefore(newCard, sessionsGrid.children[index]);
            }

            // Add entrance animation only for live updates, not initial load
            if (!skipAnimations) {
                requestAnimationFrame(() => {
                    newCard.classList.add('session-card-entering');
                    setTimeout(() => {
                        newCard.classList.remove('session-card-entering');
                    }, 300);
                });
            }
        }
    });
}

function createSessionCard(session, template) {
    console.log(`[DEBUG] Creating card for session ${session.session_id}`);
    const cardElement = template.content.cloneNode(true);
    const card = cardElement.querySelector('.session-card');

    if (!card) {
        console.error(`[DEBUG] Failed to find .session-card element in template for session ${session.session_id}`);
        return null;
    }

    // Set session ID and raw status for comparison
    card.dataset.sessionId = session.session_id;
    card.dataset.rawStatus = session.status;
    card.dataset.sessionStatus = session.status;

    // Status
    const statusIcon = card.querySelector('.status-icon');
    const statusText = card.querySelector('.status-text');
    const statusClass = getStatusClass(session.status);

    card.classList.add(statusClass);
    statusIcon.className = `status-icon fas ${getStatusIcon(session.status)}`;

    // Translate status text
    const statusKey = `status.${session.status}`;
    statusText.textContent = window.t ? window.t(statusKey) : session.status;
    
    // Time
    const sessionTime = card.querySelector('.session-time');
    sessionTime.textContent = WebUIUtils.formatRelativeTime(session.start_time);
    
    // Title and task
    const sessionTitle = card.querySelector('.session-title');
    const sessionTask = card.querySelector('.session-task');
    
    sessionTitle.textContent = `Session ${session.session_id}`;
    const noTaskText = window.t ? window.t('session.no_task') : 'No task description';
    sessionTask.textContent = session.latest_user_input || noTaskText;

    // Backend icon
    const backendIcon = card.querySelector('.session-backend-icon');
    if (backendIcon) {
        const backend = session.llm_backend || 'qwen';
        backendIcon.classList.add(WebUIUtils.getBackendClass(backend));
        backendIcon.innerHTML = WebUIUtils.getBackendIcon(backend);
        if (backend === 'claude') {
            backendIcon.title = 'Claude (Anthropic API)';
        } else if (backend === 'claude-c') {
            backendIcon.title = 'Claude (claude-c CLI)';
        } else {
            backendIcon.title = 'Qwen (Local)';
        }
    }

    // Metrics
    console.log(`[DEBUG] Session ${session.session_id}: iterations_count=${session.iterations_count}, current_iteration=${session.current_iteration}`);
    card.querySelector('.iterations-count').textContent = session.iterations_count || 0;
    card.querySelector('.queries-count').textContent = session.queries_count || 0;
    card.querySelector('.memory-items').textContent = session.memory_items || 0;
    
    // Action buttons
    const stopButton = card.querySelector('.stop-session');
    const resumeButton = card.querySelector('.resume-session');
    const exportButton = card.querySelector('.export-session');
    const deleteButton = card.querySelector('.delete-session');

    // Set session IDs for all buttons
    stopButton.dataset.sessionId = session.session_id;
    resumeButton.dataset.sessionId = session.session_id;
    exportButton.dataset.sessionId = session.session_id;
    deleteButton.dataset.sessionId = session.session_id;

    // Show Stop button for running and awaiting_input sessions
    if (session.status === 'running' || session.status === 'awaiting_input') {
        stopButton.style.display = 'inline-flex';
    } else {
        stopButton.style.display = 'none';
    }

    // Show Resume button for completed/interrupted/awaiting_input sessions
    if (session.status === 'completed' || session.status === 'interrupted' || session.status === 'awaiting_input') {
        resumeButton.style.display = 'inline-flex';
    } else {
        resumeButton.style.display = 'none';
    }

    // Translate all elements with data-i18n attributes in the cloned template
    if (window.translateElement) {
        window.translateElement(cardElement);
    }

    console.log(`[DEBUG] Successfully created card for session ${session.session_id}`);
    return card;
}

function updateSessionCard(card, session) {
    // Only update if data has actually changed
    const currentSessionId = card.dataset.sessionId;
    if (currentSessionId !== session.session_id) {
        console.error('Session ID mismatch in updateSessionCard');
        return;
    }

    // Check if update is needed by comparing key data
    const statusText = card.querySelector('.status-text');
    const iterationsCount = card.querySelector('.iterations-count');
    const queriesCount = card.querySelector('.queries-count');
    const memoryItems = card.querySelector('.memory-items');
    const sessionTime = card.querySelector('.session-time');
    const sessionTask = card.querySelector('.session-task');

    let needsUpdate = false;
    let updatedFields = [];

    // Check status change (compare raw status, not translated text)
    const currentRawStatus = card.dataset.rawStatus;
    if (currentRawStatus !== session.status) {
        needsUpdate = true;
        updatedFields.push('status');
    }

    // Check metrics changes
    if (iterationsCount.textContent !== String(session.iterations_count || 0)) {
        needsUpdate = true;
        updatedFields.push('iterations');
    }

    if (queriesCount.textContent !== String(session.queries_count || 0)) {
        needsUpdate = true;
        updatedFields.push('queries');
    }

    if (memoryItems.textContent !== String(session.memory_items || 0)) {
        needsUpdate = true;
        updatedFields.push('memory');
    }

    // Check task/user input changes
    const noTaskText = window.t ? window.t('session.no_task') : 'No task description';
    const expectedTaskText = session.latest_user_input || noTaskText;
    if (sessionTask.textContent !== expectedTaskText) {
        needsUpdate = true;
        updatedFields.push('task');
    }

    // Update time (always update this as it's relative)
    const newTimeText = WebUIUtils.formatRelativeTime(session.start_time);
    if (sessionTime.textContent !== newTimeText) {
        sessionTime.textContent = newTimeText;
    }

    if (!needsUpdate) return;

    // Skip animation if card was just repositioned (not a real data update)
    if (card.dataset.justRepositioned === 'true') {
        console.log(`[DEBUG] Skipping yellow flash for repositioned card: ${session.session_id}`);
        return;
    }

    // Add update animation class
    card.classList.add('session-card-updating');

    // Update status
    if (updatedFields.includes('status')) {
        const statusIcon = card.querySelector('.status-icon');
        const oldStatusClass = getStatusClass(currentRawStatus);
        const newStatusClass = getStatusClass(session.status);

        // Remove old status class and add new one
        card.classList.remove(oldStatusClass);
        card.classList.add(newStatusClass);

        statusIcon.className = `status-icon fas ${getStatusIcon(session.status)}`;

        // Update raw status in dataset
        card.dataset.rawStatus = session.status;

        // Update Stop button visibility based on new status
        const stopButton = card.querySelector('.stop-session');
        if (session.status === 'running' || session.status === 'awaiting_input') {
            stopButton.style.display = 'inline-flex';
        } else {
            stopButton.style.display = 'none';
        }

        // Update Resume button visibility based on new status
        const resumeButton = card.querySelector('.resume-session');
        if (session.status === 'completed' || session.status === 'interrupted' || session.status === 'awaiting_input') {
            resumeButton.style.display = 'inline-flex';
        } else {
            resumeButton.style.display = 'none';
        }

        // Translate status text
        const statusKey = `status.${session.status}`;
        statusText.textContent = window.t ? window.t(statusKey) : session.status;
    }

    // Update metrics
    if (updatedFields.includes('iterations')) {
        console.log(`[DEBUG] Updating ${session.session_id}: iterations_count=${session.iterations_count}`);
        iterationsCount.textContent = session.iterations_count || 0;
    }
    if (updatedFields.includes('queries')) {
        queriesCount.textContent = session.queries_count || 0;
    }
    if (updatedFields.includes('memory')) {
        memoryItems.textContent = session.memory_items || 0;
    }
    if (updatedFields.includes('task')) {
        const noTaskText = window.t ? window.t('session.no_task') : 'No task description';
        sessionTask.textContent = session.latest_user_input || noTaskText;
    }

    // Remove animation class after animation completes
    setTimeout(() => {
        card.classList.remove('session-card-updating');
    }, 300);
}

function removeSessionCard(card) {
    console.log(`[DEBUG] removeSessionCard called for session: ${card.dataset.sessionId}`);

    // Clean up any leftover Sporopedia animation properties
    card.classList.remove('session-card-sporopedia');
    card.style.removeProperty('--origin-x');
    card.style.removeProperty('--origin-y');
    card.style.removeProperty('--deal-z-index');
    card.style.removeProperty('--animation-delay');

    // Reset transform-origin for proper slide-out
    card.style.transformOrigin = '';

    console.log(`[DEBUG] Cleaned up Sporopedia properties for proper slide-out`);

    // Add exit animation
    card.classList.add('session-card-exiting');
    console.log(`[DEBUG] Added session-card-exiting class`);

    // Remove after animation
    setTimeout(() => {
        if (card.parentNode) {
            console.log(`[DEBUG] Removing card from DOM after animation`);
            card.parentNode.removeChild(card);
        }
    }, 300);
}

// Note: getStatusClass and getStatusIcon are now global functions from utils.js

function updateStats() {
    if (!sessionsStats) return;
    
    const stats = {
        running: allSessions.filter(s => s.status === 'running').length,
        completed: allSessions.filter(s => s.status === 'completed').length,
        totalQueries: allSessions.reduce((sum, s) => sum + (s.queries_count || 0), 0)
    };
    
    const runningCount = document.getElementById('running-count');
    const completedCount = document.getElementById('completed-count');
    const totalQueries = document.getElementById('total-queries');
    
    if (runningCount) runningCount.textContent = stats.running;
    if (completedCount) completedCount.textContent = stats.completed;
    if (totalQueries) totalQueries.textContent = stats.totalQueries;
}

// Global functions for button handlers
function viewSession(sessionId) {
    window.location.href = `/session/${sessionId}`;
}

function exportSession(sessionId) {
    // Implement export functionality
    const session = allSessions.find(s => s.session_id === sessionId);
    if (session) {
        const dataStr = JSON.stringify(session, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);

        const exportFileDefaultName = `session_${sessionId}.json`;

        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();

        WebUIUtils.showSuccess('Session exported successfully');
    }
}

function deleteSession(sessionId) {
    // Make delete request to backend
    fetch(`/api/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (response.ok) {
            // Remove session card from UI with animation FIRST
            const sessionCard = document.querySelector(`[data-session-id="${sessionId}"]`);
            if (sessionCard) {
                removeSessionCard(sessionCard);
            }

            // Delay array modifications until after animation completes (350ms > 300ms animation)
            setTimeout(() => {
                // Remove from allSessions array
                const sessionIndex = allSessions.findIndex(s => s.session_id === sessionId);
                if (sessionIndex !== -1) {
                    allSessions.splice(sessionIndex, 1);
                }

                // Also remove from filteredSessions array manually to avoid re-filtering
                const filteredIndex = filteredSessions.findIndex(s => s.session_id === sessionId);
                if (filteredIndex !== -1) {
                    filteredSessions.splice(filteredIndex, 1);
                }

                // Only update stats - do NOT call filterSessions() to avoid re-rendering conflicts
                updateStats();
            }, 350);
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    })
    .catch(error => {
        console.error('Delete failed:', error);
        const errorText = window.t ? window.t('sessions.delete_failed') : 'Failed to delete session';
        WebUIUtils.showError(`${errorText}: ${error.message}`);
    });
}

function resumeSession(sessionId, sessionStatus) {
    console.log(`[DEBUG] Resuming session ${sessionId} with status: ${sessionStatus}`);
    openResumeSessionModal(sessionId, sessionStatus);
}

// Resume Session Modal functions
let resumeSessionModal = null;
let resumeSessionData = { sessionId: null, sessionStatus: null };

function openResumeSessionModal(sessionId, sessionStatus) {
    resumeSessionModal = document.getElementById('resume-session-modal');
    if (!resumeSessionModal) return;

    // Store session data for later use
    resumeSessionData = { sessionId, sessionStatus };

    // Set session ID display
    const sessionIdDisplay = document.getElementById('resume-session-id');
    if (sessionIdDisplay) {
        sessionIdDisplay.textContent = sessionId;
    }

    // Find session data to get backend info
    const session = allSessions.find(s => s.session_id === sessionId);
    const backend = session?.llm_backend || 'qwen';

    // Set backend badge
    const backendBadge = document.getElementById('resume-session-backend');
    if (backendBadge) {
        backendBadge.className = `backend-badge ${WebUIUtils.getBackendClass(backend)}`;
        backendBadge.innerHTML = WebUIUtils.getBackendIcon(backend, { showText: true, iconFirst: false });
    }

    // Clear and focus textarea
    const textarea = document.getElementById('resume-session-guidance');
    if (textarea) {
        textarea.value = '';
        setTimeout(() => textarea.focus(), 100);
    }

    // Show modal
    resumeSessionModal.style.display = 'flex';
    document.addEventListener('keydown', handleResumeSessionModalKeyboard);
}

function closeResumeSessionModal() {
    if (resumeSessionModal) {
        resumeSessionModal.style.display = 'none';
        document.removeEventListener('keydown', handleResumeSessionModalKeyboard);
        resumeSessionData = { sessionId: null, sessionStatus: null };
    }
}

function handleResumeSessionModalKeyboard(event) {
    if (event.key === 'Escape') {
        closeResumeSessionModal();
        event.preventDefault();
    } else if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        submitResumeSession();
        event.preventDefault();
    }
}

function submitResumeSession() {
    const { sessionId, sessionStatus } = resumeSessionData;
    if (!sessionId) return;

    const textarea = document.getElementById('resume-session-guidance');
    const resumeGuidance = textarea ? textarea.value.trim() : '';

    // Show loading state on Resume button
    const resumeBtn = document.getElementById('submit-resume-btn');
    const originalText = resumeBtn.innerHTML;
    resumeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Resuming...';
    resumeBtn.disabled = true;

    // Create the resume request
    fetch(`/api/sessions/${sessionId}/resume`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            resume_guidance: resumeGuidance
        })
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    })
    .then(data => {
        console.log('Resume successful:', data);
        const successText = window.t ? window.t('sessions.resume_success') : 'Session resumed successfully';
        WebUIUtils.showSuccess(successText);
        closeResumeSessionModal();

        // Reload sessions to get updated status
        setTimeout(() => {
            loadSessions();
        }, 1000);
    })
    .catch(error => {
        console.error('Resume failed:', error);
        const errorText = window.t ? window.t('sessions.resume_failed') : 'Failed to resume session';
        WebUIUtils.showError(`${errorText}: ${error.message}`);
    })
    .finally(() => {
        // Restore button state
        if (resumeBtn) {
            resumeBtn.innerHTML = originalText;
            resumeBtn.disabled = false;
        }
    });
}

function stopSession(sessionId) {
    console.log(`[DEBUG] Stopping session ${sessionId}`);

    // Simple confirmation dialog
    const confirmMessage = window.t ? window.t('sessions.confirm_stop') : 'Stop this running session?';
    if (!confirm(confirmMessage)) {
        return; // User cancelled
    }

    // Show loading state
    const stopBtn = document.querySelector(`[data-session-id="${sessionId}"] .stop-session`);
    if (stopBtn) {
        const originalText = stopBtn.innerHTML;
        stopBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Stopping...';
        stopBtn.disabled = true;

        // Create the stop request
        fetch(`/api/sessions/${sessionId}/stop`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
        })
        .then(data => {
            console.log('Stop successful:', data);
            const successText = window.t ? window.t('sessions.stop_success') : 'Session stopped successfully';
            WebUIUtils.showSuccess(successText);

            // Reload sessions to get updated status
            setTimeout(() => {
                loadSessions();
            }, 1000);
        })
        .catch(error => {
            console.error('Stop failed:', error);
            const errorText = window.t ? window.t('sessions.stop_failed') : 'Failed to stop session';
            WebUIUtils.showError(`${errorText}: ${error.message}`);
        })
        .finally(() => {
            // Restore button state
            if (stopBtn) {
                stopBtn.innerHTML = originalText;
                stopBtn.disabled = false;
            }
        });
    }
}

function toggleDropdown(button) {
    const dropdown = button.nextElementSibling;
    const isOpen = dropdown.classList.contains('show');

    // Close all other dropdowns first
    document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
        menu.classList.remove('show');
    });

    // Toggle current dropdown
    if (!isOpen) {
        dropdown.classList.add('show');
    }
}

function closeDropdown(item) {
    const dropdown = item.closest('.dropdown-menu');
    if (dropdown) {
        dropdown.classList.remove('show');
    }
}

// Override the global session update handler
window.WebUIUtils.handleSessionUpdate = function(data) {
    console.log('Sessions page received update:', data);

    // Update the session in our local data
    const sessionIndex = allSessions.findIndex(s => s.session_id === data.session_id);

    if (sessionIndex !== -1) {
        // Update existing session
        if (data.file_type === 'live_session' && data.data) {
            const oldSession = { ...allSessions[sessionIndex] };
            Object.assign(allSessions[sessionIndex], data.data);

            // Update the specific session card if it's currently visible
            const existingCard = sessionsGrid.querySelector(`[data-session-id="${data.session_id}"]`);
            if (existingCard) {
                // Check if session still matches current filter
                const updatedSession = allSessions[sessionIndex];
                if (sessionMatchesFilter(updatedSession)) {
                    // Update existing card
                    updateSessionCard(existingCard, updatedSession);
                } else {
                    // Remove card as it no longer matches filter
                    removeSessionCard(existingCard);
                    // Update filtered sessions array
                    filteredSessions = filteredSessions.filter(s => s.session_id !== data.session_id);
                }
            } else {
                // Card not currently visible, check if it should be added
                const updatedSession = allSessions[sessionIndex];
                if (sessionMatchesFilter(updatedSession)) {
                    // Re-filter to include this session
                    filterSessions();
                    return;
                }
            }
        }
    } else {
        // New session - reload all sessions
        loadSessions();
        return;
    }

    // Update stats (they might have changed)
    updateStats();
};

function sessionMatchesFilter(session) {
    const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    const statusValue = statusFilter ? statusFilter.value : '';

    const matchesSearch = !searchTerm ||
        (session.latest_user_input && session.latest_user_input.toLowerCase().includes(searchTerm)) ||
        session.session_id.includes(searchTerm);

    const matchesStatus = !statusValue || session.status === statusValue;

    return matchesSearch && matchesStatus;
}

// Subscribe to all session updates
document.addEventListener('DOMContentLoaded', function() {
    if (window.WebUIUtils && window.WebUIUtils.socket) {
        // Subscribe to updates for all sessions
        window.WebUIUtils.socket.emit('subscribe_session', { session_id: 'all' });
    }
});

// New Session Modal functions
let newSessionModal = null;

function createNewSession() {
    // Open modal instead of prompt
    openNewSessionModal();
}

function openNewSessionModal() {
    newSessionModal = document.getElementById('new-session-modal');
    if (newSessionModal) {
        newSessionModal.style.display = 'flex';
        const textarea = document.getElementById('new-session-task');
        if (textarea) {
            textarea.value = '';
            textarea.focus();
        }
        document.addEventListener('keydown', handleNewSessionModalKeyboard);

        // Load available LLM backends
        loadLLMBackends();
    }
}

// Backend dropdown state
let backendDropdownData = [];

async function loadLLMBackends() {
    const dropdown = document.getElementById('backend-dropdown');
    const menu = document.getElementById('backend-dropdown-menu');
    const toggle = document.getElementById('backend-dropdown-toggle');
    const hiddenInput = document.getElementById('llm-backend-select');
    const statusSpan = document.getElementById('backend-status');

    if (!dropdown || !menu) return;

    try {
        const response = await fetch('/api/llm/backends');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        backendDropdownData = data.backends || [];

        // Clear existing menu items
        menu.innerHTML = '';

        // Add items for each backend
        backendDropdownData.forEach(backend => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'backend-dropdown-item';
            item.dataset.value = backend.id;

            if (!backend.available) {
                item.classList.add('disabled');
            }

            // Icon based on backend type
            const isClaudeBackend = backend.id === 'claude' || backend.id === 'claude-c';
            const icon = isClaudeBackend ? 'fa-cloud' : 'fa-server';
            const badgeText = backend.id === 'claude' ? 'API' : (backend.id === 'claude-c' ? 'CLI' : 'Local');

            item.innerHTML = `
                <i class="fas ${icon}"></i>
                <span class="item-label">${backend.name}</span>
                <span class="item-badge">${badgeText}</span>
            `;

            if (!backend.available) {
                item.innerHTML += '<i class="fas fa-lock" style="color: var(--text-muted);"></i>';
            }

            item.addEventListener('click', () => selectBackend(backend.id, backend.name, backend.available));
            menu.appendChild(item);
        });

        // Restore last used backend from localStorage
        const lastBackend = localStorage.getItem('webui_llm_backend');
        let selectedBackend = backendDropdownData[0];

        if (lastBackend) {
            const found = backendDropdownData.find(b => b.id === lastBackend && b.available);
            if (found) {
                selectedBackend = found;
            }
        }

        if (selectedBackend) {
            selectBackend(selectedBackend.id, selectedBackend.name, selectedBackend.available, false);
        }

        // Setup dropdown toggle
        toggle.addEventListener('click', toggleBackendDropdown);

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!dropdown.contains(e.target)) {
                dropdown.classList.remove('open');
            }
        });

    } catch (error) {
        console.error('Failed to load LLM backends:', error);
        if (statusSpan) {
            statusSpan.textContent = 'Failed to load backends';
            statusSpan.className = 'backend-status backend-status-error';
        }
    }
}

function toggleBackendDropdown(e) {
    e.stopPropagation();
    const dropdown = document.getElementById('backend-dropdown');
    if (dropdown) {
        dropdown.classList.toggle('open');
    }
}

function selectBackend(id, name, available, saveToStorage = true) {
    if (!available) return;

    const dropdown = document.getElementById('backend-dropdown');
    const hiddenInput = document.getElementById('llm-backend-select');
    const toggleText = dropdown.querySelector('.backend-selected-text');
    const menuItems = dropdown.querySelectorAll('.backend-dropdown-item');

    // Update hidden input value
    if (hiddenInput) {
        hiddenInput.value = id;
    }

    // Update toggle button text
    if (toggleText) {
        toggleText.textContent = name;
    }

    // Update selected state in menu
    menuItems.forEach(item => {
        item.classList.toggle('selected', item.dataset.value === id);
    });

    // Close dropdown
    dropdown.classList.remove('open');

    // Save to localStorage
    if (saveToStorage) {
        localStorage.setItem('webui_llm_backend', id);
    }

    // Update status indicator
    updateBackendStatus();
}

function updateBackendStatus() {
    const hiddenInput = document.getElementById('llm-backend-select');
    const statusSpan = document.getElementById('backend-status');

    if (!hiddenInput || !statusSpan) return;

    const selectedId = hiddenInput.value;
    const backend = backendDropdownData.find(b => b.id === selectedId);

    if (backend && !backend.available) {
        statusSpan.textContent = 'API key required';
        statusSpan.className = 'backend-status backend-status-warning';
    } else if (selectedId === 'claude') {
        statusSpan.textContent = 'Claude API';
        statusSpan.className = 'backend-status backend-status-claude';
    } else if (selectedId === 'claude-c') {
        statusSpan.textContent = 'Claude CLI';
        statusSpan.className = 'backend-status backend-status-claude';
    } else {
        statusSpan.textContent = 'Local model';
        statusSpan.className = 'backend-status backend-status-local';
    }
}

function closeNewSessionModal() {
    if (newSessionModal) {
        newSessionModal.style.display = 'none';
        document.removeEventListener('keydown', handleNewSessionModalKeyboard);
        // Close backend dropdown if open
        const dropdown = document.getElementById('backend-dropdown');
        if (dropdown) {
            dropdown.classList.remove('open');
        }
    }
}

function handleNewSessionModalKeyboard(event) {
    if (event.key === 'Escape') {
        closeNewSessionModal();
        event.preventDefault();
    } else if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        submitNewSession();
        event.preventDefault();
    }
}

function submitNewSession() {
    const textarea = document.getElementById('new-session-task');
    const backendInput = document.getElementById('llm-backend-select');
    const initialTask = textarea ? textarea.value.trim() : '';

    if (!initialTask) {
        WebUIUtils.showError('Please enter a task description');
        if (textarea) textarea.focus();
        return;
    }

    // Get selected backend from hidden input
    const selectedBackend = backendInput ? backendInput.value : 'qwen';

    // Check if selected backend is available
    const backend = backendDropdownData.find(b => b.id === selectedBackend);
    if (backend && !backend.available) {
        WebUIUtils.showError('Selected backend is not available. Please configure the API key.');
        return;
    }

    // Show loading state on Create button
    const createBtn = document.getElementById('create-session-btn');
    const originalText = createBtn.innerHTML;
    createBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';
    createBtn.disabled = true;

    // Get default preset from localStorage
    const defaultPreset = localStorage.getItem('webui_default_preset') || 'default';

    // Save selected backend to localStorage for next time
    localStorage.setItem('webui_llm_backend', selectedBackend);

    // Create the session
    fetch('/api/sessions/new', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            first_user_input: initialTask,
            default_preset: defaultPreset,
            llm_backend: selectedBackend
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            closeNewSessionModal();
            WebUIUtils.showSuccess('New session started successfully! It will appear in the list shortly.');
            // Reload sessions after a short delay to show the new session
            setTimeout(() => {
                loadSessions(false);
            }, 2000);
        } else {
            throw new Error(data.error || 'Failed to create session');
        }
    })
    .catch(error => {
        console.error('Failed to create new session:', error);
        WebUIUtils.showError(`Failed to create session: ${error.message}`);
    })
    .finally(() => {
        // Restore button state
        createBtn.innerHTML = originalText;
        createBtn.disabled = false;
    });
}

// Make functions globally available
window.viewSession = viewSession;
window.exportSession = exportSession;
window.deleteSession = deleteSession;
window.stopSession = stopSession;
window.resumeSession = resumeSession;
window.toggleDropdown = toggleDropdown;
window.closeDropdown = closeDropdown;
window.createNewSession = createNewSession;
window.openNewSessionModal = openNewSessionModal;
window.closeNewSessionModal = closeNewSessionModal;
window.submitNewSession = submitNewSession;
window.openResumeSessionModal = openResumeSessionModal;
window.closeResumeSessionModal = closeResumeSessionModal;
window.submitResumeSession = submitResumeSession;