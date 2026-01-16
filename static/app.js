// SheetSmith Frontend Application

class SheetSmithApp {
    constructor() {
        this.spreadsheetId = null;
        this.pendingPatchId = null;
        this.init();
    }

    init() {
        // DOM Elements
        this.elements = {
            spreadsheetInput: document.getElementById('spreadsheet-id'),
            connectBtn: document.getElementById('connect-btn'),
            spreadsheetInfo: document.getElementById('spreadsheet-info'),
            chatMessages: document.getElementById('chat-messages'),
            chatInput: document.getElementById('chat-input'),
            sendBtn: document.getElementById('send-btn'),
            resetBtn: document.getElementById('reset-btn'),
            diffPanel: document.getElementById('diff-panel'),
            diffContent: document.getElementById('diff-content'),
            closeDiff: document.getElementById('close-diff'),
            approveBtn: document.getElementById('approve-btn'),
            rejectBtn: document.getElementById('reject-btn'),
            searchModal: document.getElementById('search-modal'),
            searchResults: document.getElementById('search-results'),
            activityLog: document.getElementById('activity-log'),
            quickActions: document.querySelectorAll('.quick-action'),
        };

        this.bindEvents();
    }

    bindEvents() {
        // Connect button
        this.elements.connectBtn.addEventListener('click', () => this.connectSpreadsheet());

        // Send message
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
        this.elements.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Reset chat
        this.elements.resetBtn.addEventListener('click', () => this.resetChat());

        // Diff panel
        this.elements.closeDiff.addEventListener('click', () => this.hideDiffPanel());
        this.elements.approveBtn.addEventListener('click', () => this.approveChanges());
        this.elements.rejectBtn.addEventListener('click', () => this.rejectChanges());

        // Modal close
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', () => this.closeModal());
        });

        // Quick actions
        this.elements.quickActions.forEach(btn => {
            btn.addEventListener('click', (e) => this.handleQuickAction(e.target.dataset.action));
        });

        // Click outside modal to close
        this.elements.searchModal.addEventListener('click', (e) => {
            if (e.target === this.elements.searchModal) {
                this.closeModal();
            }
        });
    }

    async connectSpreadsheet() {
        const id = this.elements.spreadsheetInput.value.trim();
        if (!id) {
            this.showError('Please enter a spreadsheet ID');
            return;
        }

        this.elements.connectBtn.classList.add('loading');
        this.elements.connectBtn.disabled = true;

        try {
            const response = await fetch('/api/sheets/info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ spreadsheet_id: id })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to connect');
            }

            const info = await response.json();
            this.spreadsheetId = id;
            this.displaySpreadsheetInfo(info);
            this.addActivity(`Connected to: ${info.title}`);
            this.addAssistantMessage(`Connected to spreadsheet: **${info.title}**\n\nSheets found: ${info.sheets.map(s => s.title).join(', ')}\n\nHow can I help you with this spreadsheet?`);
        } catch (error) {
            this.showError(error.message);
        } finally {
            this.elements.connectBtn.classList.remove('loading');
            this.elements.connectBtn.disabled = false;
        }
    }

    displaySpreadsheetInfo(info) {
        this.elements.spreadsheetInfo.classList.remove('hidden');
        this.elements.spreadsheetInfo.innerHTML = `
            <p><span class="label">Title:</span> ${info.title}</p>
            <p><span class="label">Sheets:</span> ${info.sheets.length}</p>
            <p><span class="label">ID:</span> ${info.id.substring(0, 12)}...</p>
        `;
    }

    async sendMessage() {
        const message = this.elements.chatInput.value.trim();
        if (!message) return;

        // Add user message to chat
        this.addUserMessage(message);
        this.elements.chatInput.value = '';

        // Disable input while processing
        this.elements.sendBtn.disabled = true;
        this.elements.chatInput.disabled = true;

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    spreadsheet_id: this.spreadsheetId
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to send message');
            }

            const data = await response.json();
            this.addAssistantMessage(data.response);

            // Check for patch in response
            this.checkForPatch(data.response);
        } catch (error) {
            this.addAssistantMessage(`Error: ${error.message}`);
        } finally {
            this.elements.sendBtn.disabled = false;
            this.elements.chatInput.disabled = false;
            this.elements.chatInput.focus();
        }
    }

    addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.innerHTML = `<div class="message-content">${this.escapeHtml(text)}</div>`;
        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addAssistantMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        messageDiv.innerHTML = `<div class="message-content">${this.formatMessage(text)}</div>`;
        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatMessage(text) {
        // Convert markdown-like syntax to HTML
        let html = this.escapeHtml(text);

        // Code blocks
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');

        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Line breaks
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    scrollToBottom() {
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }

    checkForPatch(response) {
        // Look for patch ID in the response
        const patchMatch = response.match(/patch_id["\s:]+([a-f0-9-]{36})/i);
        if (patchMatch) {
            this.pendingPatchId = patchMatch[1];
        }

        // Look for diff content
        const diffMatch = response.match(/```diff\n([\s\S]*?)```/);
        if (diffMatch || response.includes('---') && response.includes('+++')) {
            this.showDiffPanel(response);
        }
    }

    showDiffPanel(content) {
        // Extract and format diff
        const lines = content.split('\n');
        let diffHtml = '';

        for (const line of lines) {
            if (line.startsWith('+++') || line.startsWith('---')) {
                diffHtml += `<div class="diff-line header">${this.escapeHtml(line)}</div>`;
            } else if (line.startsWith('+')) {
                diffHtml += `<div class="diff-line add">${this.escapeHtml(line)}</div>`;
            } else if (line.startsWith('-')) {
                diffHtml += `<div class="diff-line remove">${this.escapeHtml(line)}</div>`;
            } else {
                diffHtml += `<div class="diff-line">${this.escapeHtml(line)}</div>`;
            }
        }

        this.elements.diffContent.innerHTML = diffHtml;
        this.elements.diffPanel.classList.remove('hidden');
    }

    hideDiffPanel() {
        this.elements.diffPanel.classList.add('hidden');
        this.pendingPatchId = null;
    }

    async approveChanges() {
        if (!this.pendingPatchId) {
            // Send approval message through chat
            this.elements.chatInput.value = 'approve';
            this.sendMessage();
        } else {
            // Direct API call
            try {
                const response = await fetch('/api/patches/apply', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ patch_id: this.pendingPatchId })
                });

                const data = await response.json();
                this.addAssistantMessage(data.success ?
                    `Changes applied successfully! Updated ${data.updated_cells} cells.` :
                    `Error applying changes: ${data.error}`);
            } catch (error) {
                this.addAssistantMessage(`Error: ${error.message}`);
            }
        }
        this.hideDiffPanel();
        this.addActivity('Applied formula changes');
    }

    async rejectChanges() {
        this.addAssistantMessage('Changes rejected. No modifications were made.');
        this.hideDiffPanel();
        this.addActivity('Rejected formula changes');
    }

    async resetChat() {
        try {
            await fetch('/api/chat/reset', { method: 'POST' });
            this.elements.chatMessages.innerHTML = `
                <div class="message assistant">
                    <div class="message-content">
                        <p>Conversation reset. How can I help you?</p>
                    </div>
                </div>
            `;
        } catch (error) {
            this.showError('Failed to reset chat');
        }
    }

    handleQuickAction(action) {
        const prompts = {
            search: 'What pattern would you like to search for?',
            audit: 'I\'ll help you audit formulas. What pattern or function should I look for?',
            rules: 'Let me show you the stored rules for this project.'
        };

        if (action === 'rules') {
            this.loadRules();
        } else if (prompts[action]) {
            this.elements.chatInput.value = '';
            this.elements.chatInput.placeholder = prompts[action];
            this.elements.chatInput.focus();
        }
    }

    async loadRules() {
        try {
            const response = await fetch('/api/rules');
            const data = await response.json();

            if (data.count === 0) {
                this.addAssistantMessage('No rules stored yet. You can ask me to store rules about formula conventions or known logic patterns.');
            } else {
                let message = `Found ${data.count} stored rules:\n\n`;
                for (const rule of data.rules) {
                    message += `**${rule.name}** (${rule.rule_type})\n${rule.description}\n\n`;
                }
                this.addAssistantMessage(message);
            }
        } catch (error) {
            this.showError('Failed to load rules');
        }
    }

    showError(message) {
        // Could use a toast notification, for now just add to chat
        this.addAssistantMessage(`**Error:** ${message}`);
    }

    addActivity(text) {
        const placeholder = this.elements.activityLog.querySelector('.placeholder-text');
        if (placeholder) {
            placeholder.remove();
        }

        const item = document.createElement('div');
        item.className = 'activity-item';
        item.textContent = text;

        this.elements.activityLog.insertBefore(item, this.elements.activityLog.firstChild);

        // Keep only last 10 items
        const items = this.elements.activityLog.querySelectorAll('.activity-item');
        if (items.length > 10) {
            items[items.length - 1].remove();
        }
    }

    closeModal() {
        this.elements.searchModal.classList.add('hidden');
    }

    showSearchResults(results) {
        let html = '';

        if (results.matches.length === 0) {
            html = '<p>No matches found.</p>';
        } else {
            for (const match of results.matches) {
                const highlightedFormula = match.formula.replace(
                    new RegExp(`(${this.escapeRegex(match.matched_text)})`, 'gi'),
                    '<span class="matched">$1</span>'
                );

                html += `
                    <div class="search-result">
                        <div class="cell-ref">${match.sheet}!${match.cell}</div>
                        <div class="formula">${highlightedFormula}</div>
                    </div>
                `;
            }
        }

        this.elements.searchResults.innerHTML = html;
        this.elements.searchModal.classList.remove('hidden');
    }

    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new SheetSmithApp();
});
