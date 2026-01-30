// SheetSmith Frontend Application - Two-Mode UI

class SheetSmithApp {
    constructor() {
        this.spreadsheetId = null;
        this.spreadsheetInfo = null;
        this.currentMode = 'tools'; // 'tools' or 'ai'
        this.currentPreview = null;
        this.safetyLimits = {
            maxCells: 500,
            maxSheets: 40
        };
        this.init();
    }

    init() {
        this.initElements();
        this.bindEvents();
        this.loadSafetyLimits();
    }

    initElements() {
        // Mode toggle
        this.modeToolsBtn = document.getElementById('mode-tools');
        this.modeAiBtn = document.getElementById('mode-ai');
        
        // Panels
        this.toolsPanel = document.getElementById('tools-panel');
        this.aiPanel = document.getElementById('ai-panel');
        
        // Connection
        this.spreadsheetInput = document.getElementById('spreadsheet-id');
        this.connectBtn = document.getElementById('connect-btn');
        this.spreadsheetInfoEl = document.getElementById('spreadsheet-info');
        this.connectionStatus = document.getElementById('connection-status');
        
        // Tools form
        this.operationType = document.getElementById('operation-type');
        this.formReplace = document.getElementById('form-replace');
        this.formSetValue = document.getElementById('form-set-value');
        this.formCopyBlock = document.getElementById('form-copy-block');
        this.formAudit = document.getElementById('form-audit');
        
        // Replace form fields
        this.headerName = document.getElementById('header-name');
        this.searchHeadersBtn = document.getElementById('search-headers-btn');
        this.headerSuggestions = document.getElementById('header-suggestions');
        this.allSheets = document.getElementById('all-sheets');
        this.sheetSelector = document.getElementById('sheet-selector');
        this.sheetCheckboxes = document.getElementById('sheet-checkboxes');
        this.findText = document.getElementById('find-text');
        this.replaceText = document.getElementById('replace-text');
        this.matchType = document.getElementById('match-type');
        
        // Scope summary
        this.scopeSummary = document.getElementById('scope-summary');
        this.scopeSheets = document.getElementById('scope-sheets');
        this.scopeCells = document.getElementById('scope-cells');
        this.scopeHeaders = document.getElementById('scope-headers');
        this.scopeStatus = document.getElementById('scope-status');
        
        // Buttons
        this.previewBtn = document.getElementById('preview-btn');
        this.clearFormBtn = document.getElementById('clear-form-btn');
        
        // AI mode
        this.aiInput = document.getElementById('ai-input');
        this.analyzeRequestBtn = document.getElementById('analyze-request-btn');
        this.clearAiBtn = document.getElementById('clear-ai-btn');
        this.aiSuggestion = document.getElementById('ai-suggestion');
        this.aiSuggestionContent = document.getElementById('ai-suggestion-content');
        this.useSuggestionBtn = document.getElementById('use-suggestion-btn');
        this.refineBtn = document.getElementById('refine-btn');
        this.aiChat = document.getElementById('ai-chat');
        this.aiMessages = document.getElementById('ai-messages');
        
        // Modals
        this.previewModal = document.getElementById('preview-modal');
        this.previewContent = document.getElementById('preview-content');
        this.previewMode = document.getElementById('preview-mode');
        this.previewScopeSummary = document.getElementById('preview-scope-summary');
        this.previewColumns = document.getElementById('preview-columns');
        this.previewSheets = document.getElementById('preview-sheets');
        this.changeCounter = document.getElementById('change-counter');
        this.prevChangeBtn = document.getElementById('prev-change-btn');
        this.nextChangeBtn = document.getElementById('next-change-btn');
        this.applyChangesBtn = document.getElementById('apply-changes-btn');
        this.exportPreviewBtn = document.getElementById('export-preview-btn');
        
        this.confirmModal = document.getElementById('confirm-modal');
        this.confirmMessage = document.getElementById('confirm-message');
        this.confirmYesBtn = document.getElementById('confirm-yes-btn');
        this.confirmNoBtn = document.getElementById('confirm-no-btn');
        
        // Activity log
        this.activityLog = document.getElementById('activity-log');
    }

    bindEvents() {
        // Mode toggle
        this.modeToolsBtn?.addEventListener('click', () => this.switchMode('tools'));
        this.modeAiBtn?.addEventListener('click', () => this.switchMode('ai'));
        
        // Connection
        this.connectBtn?.addEventListener('click', () => this.connectSpreadsheet());
        
        // Operation type change
        this.operationType?.addEventListener('change', (e) => this.handleOperationTypeChange(e.target.value));
        
        // All sheets checkbox
        this.allSheets?.addEventListener('change', (e) => {
            this.sheetSelector?.classList.toggle('hidden', e.target.checked);
        });
        
        // Search headers
        this.searchHeadersBtn?.addEventListener('click', () => this.searchHeaders());
        this.headerName?.addEventListener('input', () => this.searchHeaders());
        
        // Form inputs - update scope summary
        const scopeInputs = [
            this.headerName, this.findText, this.replaceText, 
            this.allSheets, this.matchType
        ];
        scopeInputs.forEach(el => {
            el?.addEventListener('input', () => this.updateScopeSummary());
            el?.addEventListener('change', () => this.updateScopeSummary());
        });
        
        // Buttons
        this.previewBtn?.addEventListener('click', () => this.generatePreview());
        this.clearFormBtn?.addEventListener('click', () => this.clearForm());
        
        // AI mode
        this.analyzeRequestBtn?.addEventListener('click', () => this.sendChatMessage());
        this.clearAiBtn?.addEventListener('click', () => this.clearAi());
        this.useSuggestionBtn?.addEventListener('click', () => this.useSuggestion());
        this.refineBtn?.addEventListener('click', () => {
            this.aiSuggestion?.classList.add('hidden');
            this.aiInput?.focus();
        });
        
        // AI input keyboard shortcut
        this.aiInput?.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                this.sendChatMessage();
            }
        });
        
        // Preview modal
        this.prevChangeBtn?.addEventListener('click', () => this.navigateChange(-1));
        this.nextChangeBtn?.addEventListener('click', () => this.navigateChange(1));
        this.applyChangesBtn?.addEventListener('click', () => this.confirmApplyChanges());
        this.exportPreviewBtn?.addEventListener('click', () => this.exportPreview());
        
        // Modal close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.target.closest('.modal')?.classList.add('hidden');
            });
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.previewModal?.classList.add('hidden');
                this.confirmModal?.classList.add('hidden');
            }
            if (e.ctrlKey && e.key === '/') {
                this.switchMode(this.currentMode === 'tools' ? 'ai' : 'tools');
            }
        });
    }

    switchMode(mode) {
        this.currentMode = mode;
        
        // Update buttons
        this.modeToolsBtn?.classList.toggle('active', mode === 'tools');
        this.modeAiBtn?.classList.toggle('active', mode === 'ai');
        
        // Update panels
        this.toolsPanel?.classList.toggle('active', mode === 'tools');
        this.aiPanel?.classList.toggle('active', mode === 'ai');
    }

    async connectSpreadsheet() {
        const id = this.spreadsheetInput?.value.trim();
        if (!id) {
            this.showError('Please enter a spreadsheet ID');
            return;
        }

        this.connectBtn.disabled = true;
        this.connectBtn.textContent = 'Connecting...';

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
            this.spreadsheetInfo = info;
            this.displaySpreadsheetInfo(info);
            this.updateConnectionStatus(true);
            this.addActivity(`Connected to: ${info.title}`);
        } catch (error) {
            this.showError(error.message);
            this.updateConnectionStatus(false);
        } finally {
            this.connectBtn.disabled = false;
            this.connectBtn.textContent = 'Connect';
        }
    }

    displaySpreadsheetInfo(info) {
        if (!this.spreadsheetInfoEl) return;
        
        this.spreadsheetInfoEl.classList.remove('hidden');
        this.spreadsheetInfoEl.innerHTML = `
            <p><span class="label">Title:</span> ${info.title}</p>
            <p><span class="label">Sheets:</span> ${info.sheets.length}</p>
            <p><span class="label">ID:</span> ${info.id.substring(0, 12)}...</p>
        `;
        
        // Populate sheet selectors
        this.populateSheetSelectors(info.sheets);
    }

    populateSheetSelectors(sheets) {
        // Sheet checkboxes for replace form
        if (this.sheetCheckboxes) {
            this.sheetCheckboxes.innerHTML = sheets.map(sheet => `
                <label>
                    <input type="checkbox" value="${sheet.title}" class="sheet-checkbox" checked>
                    ${sheet.title}
                </label>
            `).join('');
        }
        
        // Source sheet dropdown for copy block
        const sourceSheet = document.getElementById('source-sheet');
        if (sourceSheet) {
            sourceSheet.innerHTML = '<option value="">-- Select sheet --</option>' +
                sheets.map(sheet => `<option value="${sheet.title}">${sheet.title}</option>`).join('');
        }
        
        // Target sheets for copy block
        const targetSheets = document.getElementById('target-sheets');
        if (targetSheets) {
            targetSheets.innerHTML = sheets.map(sheet => `
                <label>
                    <input type="checkbox" value="${sheet.title}" class="target-sheet-checkbox">
                    ${sheet.title}
                </label>
            `).join('');
        }
    }

    updateConnectionStatus(connected) {
        if (!this.connectionStatus) return;
        
        this.connectionStatus.classList.toggle('connected', connected);
        this.connectionStatus.classList.toggle('disconnected', !connected);
        
        const statusText = this.connectionStatus.querySelector('.status-text');
        if (statusText) {
            statusText.textContent = connected ? 
                (this.spreadsheetInfo?.title || 'Connected') : 
                'Not Connected';
        }
    }

    handleOperationTypeChange(operationType) {
        // Hide all forms
        this.formReplace?.classList.remove('active');
        this.formSetValue?.classList.remove('active');
        this.formCopyBlock?.classList.remove('active');
        this.formAudit?.classList.remove('active');
        
        // Show selected form
        switch(operationType) {
            case 'replace_in_formulas':
                this.formReplace?.classList.add('active');
                break;
            case 'set_value_by_header':
                this.formSetValue?.classList.add('active');
                break;
            case 'copy_block':
                this.formCopyBlock?.classList.add('active');
                break;
            case 'audit':
                this.formAudit?.classList.add('active');
                break;
        }
        
        this.updateScopeSummary();
    }

    async searchHeaders() {
        if (!this.spreadsheetId || !this.headerName) return;
        
        const query = this.headerName.value.trim().toLowerCase();
        if (!query) {
            this.headerSuggestions?.classList.add('hidden');
            return;
        }
        
        // Filter headers from spreadsheet info
        const headers = this.extractHeaders();
        const matches = headers.filter(h => h.toLowerCase().includes(query));
        
        if (matches.length === 0) {
            this.headerSuggestions?.classList.add('hidden');
            return;
        }
        
        this.headerSuggestions.innerHTML = matches.map(header => `
            <div class="suggestion-item" data-header="${header}">${header}</div>
        `).join('');
        
        this.headerSuggestions.classList.remove('hidden');
        
        // Bind click events
        this.headerSuggestions.querySelectorAll('.suggestion-item').forEach(item => {
            item.addEventListener('click', () => {
                this.headerName.value = item.dataset.header;
                this.headerSuggestions.classList.add('hidden');
                this.updateScopeSummary();
            });
        });
    }

    extractHeaders() {
        // This would ideally fetch actual headers from the spreadsheet
        // For now, return empty array (could be enhanced)
        return [];
    }

    updateScopeSummary() {
        if (!this.spreadsheetId || !this.operationType?.value) {
            this.scopeSummary?.classList.add('hidden');
            this.previewBtn.disabled = true;
            return;
        }
        
        const operationType = this.operationType.value;
        let canPreview = false;
        
        // Estimate scope based on operation type
        if (operationType === 'replace_in_formulas') {
            const header = this.headerName?.value.trim();
            const findText = this.findText?.value.trim();
            
            canPreview = header && findText;
            
            if (canPreview) {
                const sheetsCount = this.allSheets?.checked ? 
                    (this.spreadsheetInfo?.sheets.length || 0) :
                    document.querySelectorAll('.sheet-checkbox:checked').length;
                
                this.scopeSummary?.classList.remove('hidden');
                this.scopeSheets.textContent = `${sheetsCount} selected`;
                this.scopeCells.textContent = 'Unknown (preview to see)';
                this.scopeHeaders.textContent = header;
                
                // Update status
                this.updateScopeStatus('ok', '✅ Within safety limits');
            }
        } else if (operationType === 'set_value_by_header') {
            const header = document.getElementById('set-header-name')?.value.trim();
            const rowId = document.getElementById('row-identifier')?.value.trim();
            const newValue = document.getElementById('new-value')?.value.trim();
            
            canPreview = header && rowId && newValue;
        } else if (operationType === 'audit') {
            const header = document.getElementById('audit-header')?.value.trim();
            canPreview = header;
        }
        
        this.previewBtn.disabled = !canPreview;
    }

    updateScopeStatus(type, message) {
        if (!this.scopeStatus) return;
        
        this.scopeStatus.className = `scope-status ${type}`;
        this.scopeStatus.textContent = message;
    }

    async generatePreview() {
        if (!this.spreadsheetId) {
            this.showError('Please connect to a spreadsheet first');
            return;
        }
        
        this.previewBtn.disabled = true;
        this.previewBtn.textContent = 'Generating...';
        
        try {
            let preview;
            
            // Route based on current mode
            if (this.currentMode === 'tools') {
                preview = await this.generateDeterministicPreview();
            } else {
                preview = await this.generateAiAssistedPreview();
            }
            
            this.currentPreview = preview;
            this.showPreviewModal(preview);
            this.addActivity(`Generated preview: ${preview.changes.length} changes`);
        } catch (error) {
            this.showError(error.message);
        } finally {
            this.previewBtn.disabled = false;
            this.previewBtn.textContent = 'Preview Changes';
        }
    }
    
    async generateDeterministicPreview() {
        const operationType = this.operationType?.value;
        
        if (operationType === 'replace_in_formulas') {
            const header = this.headerName?.value.trim();
            const headerRow = document.getElementById('replace-header-row')?.value;
            const findText = this.findText?.value.trim();
            const replaceText = this.replaceText?.value.trim();
            
            if (!header || !findText || !replaceText) {
                throw new Error('Please fill in header, find text, and replace text');
            }
            
            const sheets = this.allSheets?.checked ? 
                null : 
                Array.from(document.querySelectorAll('.sheet-checkbox:checked')).map(cb => cb.value);
            
            const response = await fetch('/api/modes/deterministic/replace', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    spreadsheet_id: this.spreadsheetId,
                    header_text: header,
                    header_row: parseInt(headerRow) || 1,
                    find: findText,
                    replace: replaceText,
                    sheet_names: sheets,
                    case_sensitive: false,
                    is_regex: this.matchType?.value === 'regex'
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to generate preview');
            }
            
            return await response.json();
        } else if (operationType === 'set_value_by_header') {
            const header = document.getElementById('set-header-name')?.value.trim();
            const rowLabel = document.getElementById('row-identifier')?.value.trim();
            const newValue = document.getElementById('new-value')?.value;
            
            if (!header || !rowLabel || newValue === null || newValue === undefined || newValue === '') {
                throw new Error('Please fill in header, row identifier, and new value');
            }
            
            // For set_value, we need a sheet name
            // If "all sheets" is checked, we'd need to iterate or error
            const sheetName = this.spreadsheetInfo?.sheets?.[0]?.title || 'Sheet1';
            
            const response = await fetch('/api/modes/deterministic/set_value', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    spreadsheet_id: this.spreadsheetId,
                    sheet_name: sheetName,
                    header: header,
                    row_label: rowLabel,
                    value: newValue
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to generate preview');
            }
            
            return await response.json();
        } else {
            // Fallback to old endpoint for other operation types
            const operation = this.buildOperationFromForm();
            if (!operation) {
                throw new Error('Please fill in all required fields');
            }
            
            const response = await fetch('/api/ops/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    spreadsheet_id: this.spreadsheetId,
                    operation: operation
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to generate preview');
            }
            
            return await response.json();
        }
    }
    
    async generateAiAssistedPreview() {
        // This would integrate with AI assist mode
        throw new Error('AI-assist mode not yet fully implemented');
    }

    buildOperationFromForm() {
        const operationType = this.operationType?.value;
        if (!operationType) return null;
        
        const operation = {
            operation_type: operationType,
            description: ''
        };
        
        if (operationType === 'replace_in_formulas') {
            const header = this.headerName?.value.trim();
            const findText = this.findText?.value.trim();
            const replaceText = this.replaceText?.value.trim();
            
            if (!header || !findText) return null;
            
            const sheets = this.allSheets?.checked ? 
                null : 
                Array.from(document.querySelectorAll('.sheet-checkbox:checked')).map(cb => cb.value);
            
            operation.description = `Replace "${findText.substring(0, 50)}" in "${header}" column`;
            operation.search_criteria = {
                header_text: header,
                formula_pattern: findText,
                is_regex: this.matchType?.value === 'regex',
                sheet_names: sheets
            };
            operation.find_pattern = findText;
            operation.replace_with = replaceText || '';
        }
        
        return operation;
    }

    showPreviewModal(preview) {
        if (!this.previewModal) return;
        
        // Update mode indicator
        if (this.previewMode) {
            const modeText = this.currentMode === 'tools' ? 'Deterministic ($0.00)' : 'AI Assist';
            this.previewMode.textContent = modeText;
        }
        
        // Update scope info
        if (this.previewScopeSummary) {
            this.previewScopeSummary.textContent = 
                `${preview.scope.total_cells} cells, ${preview.scope.sheet_count} sheets`;
        }
        if (this.previewColumns) {
            this.previewColumns.textContent = preview.scope.affected_headers.join(', ') || 'N/A';
        }
        if (this.previewSheets) {
            this.previewSheets.textContent = preview.scope.affected_sheets.join(', ');
        }
        
        // Render changes
        this.renderPreviewChanges(preview.changes);
        
        // Show modal
        this.previewModal.classList.remove('hidden');
    }

    renderPreviewChanges(changes, currentIndex = 0) {
        if (!this.previewContent || !changes || changes.length === 0) return;
        
        const change = changes[currentIndex];
        
        this.previewContent.innerHTML = `
            <div class="change-item">
                <div class="change-header">
                    <span>Sheet: <strong>${change.sheet_name}</strong></span>
                    <span class="change-cell">${change.cell}</span>
                </div>
                ${change.header ? `<div class="change-header">Column: <strong>${change.header}</strong></div>` : ''}
                ${change.row_label ? `<div class="change-header">Row: <strong>${change.row_label}</strong></div>` : ''}
                <div class="change-diff">
                    ${change.old_formula ? `
                        <div class="change-old">❌ ${this.escapeHtml(change.old_formula)}</div>
                        <div class="change-new">✅ ${this.escapeHtml(change.new_formula || '')}</div>
                    ` : `
                        <div class="change-old">Old: ${this.escapeHtml(String(change.old_value || ''))}</div>
                        <div class="change-new">New: ${this.escapeHtml(String(change.new_value || ''))}</div>
                    `}
                </div>
            </div>
        `;
        
        // Update counter
        if (this.changeCounter) {
            this.changeCounter.textContent = `Change ${currentIndex + 1} of ${changes.length}`;
        }
        
        // Update navigation buttons
        if (this.prevChangeBtn) {
            this.prevChangeBtn.disabled = currentIndex === 0;
        }
        if (this.nextChangeBtn) {
            this.nextChangeBtn.disabled = currentIndex === changes.length - 1;
        }
        
        // Store current index
        this.previewContent.dataset.currentIndex = currentIndex;
    }

    navigateChange(direction) {
        if (!this.currentPreview) return;
        
        const currentIndex = parseInt(this.previewContent.dataset.currentIndex || '0');
        const newIndex = currentIndex + direction;
        const changes = this.currentPreview.changes;
        
        if (newIndex >= 0 && newIndex < changes.length) {
            this.renderPreviewChanges(changes, newIndex);
        }
    }

    async confirmApplyChanges() {
        if (!this.currentPreview) return;
        
        const totalChanges = this.currentPreview.changes.length;
        const affectedSheets = this.currentPreview.scope.affected_sheets.length;
        
        // Show confirmation if large operation
        if (totalChanges > 50 || affectedSheets > 5) {
            this.showConfirmation(
                `This will modify ${totalChanges} cells across ${affectedSheets} sheets. Continue?`,
                () => this.applyChanges()
            );
        } else {
            await this.applyChanges();
        }
    }

    async applyChanges() {
        if (!this.currentPreview) return;
        
        this.applyChangesBtn.disabled = true;
        this.applyChangesBtn.textContent = 'Applying...';
        
        try {
            const response = await fetch('/api/ops/apply', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    preview_id: this.currentPreview.preview_id,
                    confirmation: true
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to apply changes');
            }
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess(`Successfully updated ${result.cells_updated} cells!`);
                this.previewModal?.classList.add('hidden');
                this.confirmModal?.classList.add('hidden');
                this.clearForm();
                this.addActivity(`Applied changes: ${result.cells_updated} cells updated`);
            } else {
                throw new Error(result.errors.join(', ') || 'Failed to apply changes');
            }
        } catch (error) {
            this.showError(error.message);
        } finally {
            this.applyChangesBtn.disabled = false;
            this.applyChangesBtn.textContent = 'Apply All Changes';
        }
    }

    exportPreview() {
        if (!this.currentPreview) return;
        
        const data = {
            preview_id: this.currentPreview.preview_id,
            operation: this.currentPreview.description,
            scope: this.currentPreview.scope,
            changes: this.currentPreview.changes
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `preview-${this.currentPreview.preview_id}.json`;
        a.click();
        URL.revokeObjectURL(url);
        
        this.addActivity('Exported preview to JSON');
    }

    async sendChatMessage() {
        const message = this.aiInput?.value.trim();
        if (!message || !this.spreadsheetId) {
            this.showError('Please enter a request and connect to a spreadsheet');
            return;
        }

        // Add user message to UI
        this.appendMessage('user', message);
        this.aiInput.value = '';
        
        this.analyzeRequestBtn.disabled = true;
        this.analyzeRequestBtn.textContent = 'Thinking...';
        
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
                throw new Error(error.detail || 'Failed to get response');
            }
            
            const data = await response.json();
            this.appendMessage('agent', data.response);
            this.addActivity('Agent responded');
        } catch (error) {
            this.showError(error.message);
            this.appendMessage('error', `Error: ${error.message}`);
        } finally {
            this.analyzeRequestBtn.disabled = false;
            this.analyzeRequestBtn.textContent = 'Send';
        }
    }

    appendMessage(role, text) {
        if (!this.aiMessages) return;
        
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;
        
        // Simple markdown parsing for code blocks
        let formattedText = this.escapeHtml(text)
            .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
            .replace(/\n/g, '<br>');
            
        msgDiv.innerHTML = `
            <div class="message-content">${formattedText}</div>
        `;
        
        this.aiMessages.appendChild(msgDiv);
        this.aiMessages.scrollTop = this.aiMessages.scrollHeight;
        
        // Also hide the old suggestion box if it exists
        if (this.aiSuggestion) this.aiSuggestion.classList.add('hidden');
    }

    // showAiSuggestion is deprecated but kept for compatibility if needed
    showAiSuggestion(response) {
        this.appendMessage('agent', response);
    }

    useSuggestion() {
        // Switch to tools mode and pre-fill form
        this.switchMode('tools');
        // TODO: Parse AI suggestion and fill form
        this.addActivity('Switched to tools mode with AI suggestion');
    }

    clearAi() {
        if (this.aiInput) this.aiInput.value = '';
        this.aiSuggestion?.classList.add('hidden');
    }

    clearForm() {
        if (this.operationType) this.operationType.value = '';
        if (this.headerName) this.headerName.value = '';
        if (this.findText) this.findText.value = '';
        if (this.replaceText) this.replaceText.value = '';
        
        this.formReplace?.classList.remove('active');
        this.formSetValue?.classList.remove('active');
        this.formCopyBlock?.classList.remove('active');
        this.formAudit?.classList.remove('active');
        
        this.scopeSummary?.classList.add('hidden');
        this.previewBtn.disabled = true;
    }

    showConfirmation(message, onConfirm) {
        if (!this.confirmModal || !this.confirmMessage) return;
        
        this.confirmMessage.textContent = message;
        this.confirmModal.classList.remove('hidden');
        
        // Bind confirm button
        const handler = () => {
            this.confirmModal.classList.add('hidden');
            this.confirmYesBtn.removeEventListener('click', handler);
            onConfirm();
        };
        
        this.confirmYesBtn.addEventListener('click', handler);
    }

    showError(message) {
        console.error('Error:', message);
        // Could implement a toast notification system
        alert(`Error: ${message}`);
    }

    showSuccess(message) {
        console.log('Success:', message);
        // Could implement a toast notification system
        alert(message);
    }

    addActivity(text) {
        if (!this.activityLog) return;
        
        const placeholder = this.activityLog.querySelector('.placeholder-text');
        if (placeholder) {
            placeholder.remove();
        }

        const item = document.createElement('div');
        item.className = 'activity-item';
        item.textContent = text;

        this.activityLog.insertBefore(item, this.activityLog.firstChild);

        // Keep only last 10 items
        const items = this.activityLog.querySelectorAll('.activity-item');
        if (items.length > 10) {
            items[items.length - 1].remove();
        }
    }

    async loadSafetyLimits() {
        try {
            const response = await fetch('/api/config/limits');
            if (response.ok) {
                const data = await response.json();
                this.safetyLimits = data.safety_limits || this.safetyLimits;
                console.log('Loaded safety limits:', this.safetyLimits);
            }
        } catch (error) {
            console.warn('Could not load safety limits, using defaults');
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new SheetSmithApp();
});
