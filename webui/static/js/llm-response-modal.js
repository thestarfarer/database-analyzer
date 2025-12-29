// LLM Response Modal - Shared Component
// Used by both session.js and iteration.js

const LLMResponseModal = {
    currentResponse: null,
    isThinkingExpanded: false,

    // DOM element references (set on first use)
    modal: null,
    content: null,
    thinkingSection: null,
    thinkingContent: null,
    thinkingIcon: null,
    copyWithThinkingBtn: null,
    thinkingKeyboardHint: null,

    init() {
        this.modal = document.getElementById('llm-response-modal');
        this.content = document.getElementById('llm-response-content');
        this.thinkingSection = document.getElementById('llm-thinking-section');
        this.thinkingContent = document.getElementById('thinking-content');
        this.thinkingIcon = document.getElementById('thinking-toggle-icon');
        this.copyWithThinkingBtn = document.getElementById('copy-with-thinking-btn');
        this.thinkingKeyboardHint = document.getElementById('thinking-keyboard-hint');
    },

    open(response, thinking, raw) {
        if (!this.modal) this.init();
        if (!this.modal) return;

        // Store response data for copy operations
        this.currentResponse = {
            main: response || '',
            thinking: thinking || '',
            raw: raw || response || ''
        };

        // Render content
        this.renderMarkdown(response);
        this.setupThinking(thinking);

        // Show modal
        this.modal.style.display = 'flex';

        // Add keyboard listener
        document.addEventListener('keydown', this._boundKeyHandler = this.handleKeyboard.bind(this));
    },

    close() {
        if (!this.modal) return;

        this.modal.style.display = 'none';

        // Remove keyboard listener
        if (this._boundKeyHandler) {
            document.removeEventListener('keydown', this._boundKeyHandler);
        }

        // Reset thinking state
        this.isThinkingExpanded = false;
        if (this.thinkingContent) this.thinkingContent.style.display = 'none';
        if (this.thinkingIcon) this.thinkingIcon.className = 'fas fa-chevron-right thinking-toggle-icon';
    },

    renderMarkdown(content) {
        if (!this.content) return;

        if (!content) {
            this.content.innerHTML = '<p class="no-content">No response content</p>';
            return;
        }

        try {
            // Configure marked options
            if (typeof marked !== 'undefined') {
                marked.setOptions({
                    breaks: true,
                    gfm: true,
                    tables: true,
                    headerIds: false,
                    mangle: false
                });

                // Parse markdown to HTML
                let html = marked.parse(content);

                // Sanitize the HTML to prevent XSS
                if (typeof DOMPurify !== 'undefined') {
                    html = DOMPurify.sanitize(html, {
                        ADD_ATTR: ['class', 'style'],
                        ALLOWED_TAGS: [
                            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                            'p', 'br', 'hr',
                            'ul', 'ol', 'li',
                            'table', 'thead', 'tbody', 'tr', 'th', 'td',
                            'strong', 'em', 'code', 'pre',
                            'blockquote', 'a', 'span', 'div'
                        ]
                    });
                }

                // Set the HTML content
                this.content.innerHTML = html;

                // Apply syntax highlighting to code blocks
                if (typeof hljs !== 'undefined') {
                    this.content.querySelectorAll('pre code').forEach((block) => {
                        // Try to detect SQL blocks
                        if (block.textContent.match(/\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN)\b/i)) {
                            block.classList.add('language-sql');
                        }
                        hljs.highlightElement(block);
                    });
                }
            } else {
                // Fallback to plain text
                this.content.textContent = content;
            }
        } catch (error) {
            console.error('Error rendering markdown:', error);
            this.content.textContent = content;
        }
    },

    setupThinking(thinking) {
        if (!this.thinkingSection) return;

        if (thinking) {
            this.thinkingSection.style.display = 'block';
            if (this.copyWithThinkingBtn) this.copyWithThinkingBtn.style.display = 'inline-flex';
            if (this.thinkingKeyboardHint) this.thinkingKeyboardHint.style.display = 'inline';

            // Render thinking content as monospace/code-like
            if (this.thinkingContent) {
                const sanitized = typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(thinking) : thinking;
                this.thinkingContent.innerHTML = `<pre class="thinking-pre">${sanitized}</pre>`;
            }

            // Reset expansion state
            this.isThinkingExpanded = false;
            if (this.thinkingContent) this.thinkingContent.style.display = 'none';
            if (this.thinkingIcon) this.thinkingIcon.className = 'fas fa-chevron-right thinking-toggle-icon';
        } else {
            this.thinkingSection.style.display = 'none';
            if (this.copyWithThinkingBtn) this.copyWithThinkingBtn.style.display = 'none';
            if (this.thinkingKeyboardHint) this.thinkingKeyboardHint.style.display = 'none';
        }
    },

    toggleThinking() {
        if (!this.thinkingContent || !this.thinkingIcon) return;

        this.isThinkingExpanded = !this.isThinkingExpanded;

        if (this.isThinkingExpanded) {
            this.thinkingContent.style.display = 'block';
            this.thinkingIcon.className = 'fas fa-chevron-down thinking-toggle-icon';
        } else {
            this.thinkingContent.style.display = 'none';
            this.thinkingIcon.className = 'fas fa-chevron-right thinking-toggle-icon';
        }
    },

    copy(includeThinking = false) {
        if (!this.currentResponse) return;

        let textToCopy = this.currentResponse.main || '';

        if (includeThinking && this.currentResponse.thinking) {
            textToCopy = `<think>\n${this.currentResponse.thinking}\n</think>\n\n${textToCopy}`;
        }

        // Use clipboard API
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(textToCopy).then(() => {
                const message = includeThinking ? 'Response copied with thinking' : 'Response copied';
                if (window.WebUIUtils && window.WebUIUtils.showSuccess) {
                    window.WebUIUtils.showSuccess(message);
                }
            }).catch(err => {
                console.error('Failed to copy:', err);
                this._fallbackCopy(textToCopy, includeThinking);
            });
        } else {
            this._fallbackCopy(textToCopy, includeThinking);
        }
    },

    _fallbackCopy(text, includeThinking) {
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
            const message = includeThinking ? 'Response copied with thinking' : 'Response copied';
            if (window.WebUIUtils && window.WebUIUtils.showSuccess) {
                window.WebUIUtils.showSuccess(message);
            }
        } catch (err) {
            console.error('Fallback copy failed:', err);
        }

        document.body.removeChild(textArea);
    },

    handleKeyboard(event) {
        // Don't handle if user is typing in an input field
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
            return;
        }

        switch(event.key.toLowerCase()) {
            case 'escape':
                this.close();
                event.preventDefault();
                break;
            case 't':
                // Only toggle if thinking section is visible
                if (this.thinkingSection && this.thinkingSection.style.display !== 'none') {
                    this.toggleThinking();
                    event.preventDefault();
                }
                break;
        }
    }
};

// Global functions for onclick handlers
window.openLLMResponseModal = function() {
    // This will be overridden by page-specific code
    console.warn('openLLMResponseModal not implemented for this page');
};

window.closeLLMResponseModal = function() {
    LLMResponseModal.close();
};

window.toggleThinking = function() {
    LLMResponseModal.toggleThinking();
};

window.copyLLMResponse = function(includeThinking) {
    LLMResponseModal.copy(includeThinking);
};

// Export for module use
window.LLMResponseModal = LLMResponseModal;
