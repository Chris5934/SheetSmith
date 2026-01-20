// Cost Tracking UI Component for SheetSmith

class CostTracker {
    constructor() {
        this.isMinimized = false;
        this.updateInterval = null;
        this.init();
    }

    init() {
        this.createCostPanel();
        this.startAutoUpdate();
    }

    createCostPanel() {
        // Create cost panel HTML
        const panel = document.createElement('div');
        panel.id = 'cost-panel';
        panel.className = 'cost-panel';
        panel.innerHTML = `
            <div class="cost-panel-header">
                <h3>💰 Cost Monitor</h3>
                <div class="cost-panel-controls">
                    <button class="btn-icon" id="cost-refresh" title="Refresh">🔄</button>
                    <button class="btn-icon" id="cost-minimize" title="Minimize">−</button>
                </div>
            </div>
            <div class="cost-panel-content">
                <div class="cost-metric">
                    <span class="cost-label">Session Cost:</span>
                    <span class="cost-value" id="session-cost">$0.0000</span>
                </div>
                <div class="cost-metric">
                    <span class="cost-label">Last Request:</span>
                    <span class="cost-value" id="last-cost">$0.0000</span>
                </div>
                <div class="cost-metric">
                    <span class="cost-label">Total Calls:</span>
                    <span class="cost-value" id="total-calls">0</span>
                </div>
                <div class="cost-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" id="budget-progress"></div>
                    </div>
                    <span class="progress-text" id="budget-text">Budget: 0% used</span>
                </div>
                <div class="cost-actions">
                    <button class="btn btn-secondary btn-small" id="cost-details">Details</button>
                    <button class="btn btn-secondary btn-small" id="cost-reset">Reset</button>
                </div>
            </div>
        `;

        // Insert panel into DOM
        document.body.appendChild(panel);

        // Bind events
        this.bindEvents();
    }

    bindEvents() {
        document.getElementById('cost-refresh').addEventListener('click', () => this.updateCostData());
        document.getElementById('cost-minimize').addEventListener('click', () => this.toggleMinimize());
        document.getElementById('cost-details').addEventListener('click', () => this.showDetails());
        document.getElementById('cost-reset').addEventListener('click', () => this.resetCosts());
    }

    toggleMinimize() {
        this.isMinimized = !this.isMinimized;
        const panel = document.getElementById('cost-panel');
        const content = panel.querySelector('.cost-panel-content');
        const minimizeBtn = document.getElementById('cost-minimize');
        
        if (this.isMinimized) {
            content.style.display = 'none';
            minimizeBtn.textContent = '+';
            minimizeBtn.title = 'Expand';
        } else {
            content.style.display = 'block';
            minimizeBtn.textContent = '−';
            minimizeBtn.title = 'Minimize';
        }
    }

    async updateCostData() {
        try {
            const response = await fetch('/api/costs/summary');
            if (!response.ok) throw new Error('Failed to fetch cost data');
            
            const data = await response.json();
            this.displayCostData(data);
        } catch (error) {
            console.error('Error updating cost data:', error);
        }
    }

    displayCostData(data) {
        // Update session cost
        const sessionCost = (data.total_cost_cents || 0) / 100;
        document.getElementById('session-cost').textContent = `$${sessionCost.toFixed(4)}`;

        // Update last request cost
        if (data.last_call) {
            const lastCost = (data.last_call.cost_cents || 0) / 100;
            document.getElementById('last-cost').textContent = `$${lastCost.toFixed(4)}`;
        }

        // Update total calls
        document.getElementById('total-calls').textContent = data.total_calls || 0;

        // Update budget progress
        if (data.budget_status) {
            const budgetUsed = data.budget_status.budget_used_percent || 0;
            const progressFill = document.getElementById('budget-progress');
            const budgetText = document.getElementById('budget-text');
            
            progressFill.style.width = `${Math.min(budgetUsed, 100)}%`;
            
            // Change color based on usage
            if (budgetUsed >= 90) {
                progressFill.className = 'progress-fill danger';
            } else if (budgetUsed >= 70) {
                progressFill.className = 'progress-fill warning';
            } else {
                progressFill.className = 'progress-fill';
            }
            
            budgetText.textContent = `Budget: ${budgetUsed.toFixed(1)}% used`;
            
            // Show warning if budget is high
            if (budgetUsed >= 80) {
                this.showBudgetWarning(budgetUsed);
            }
        }
    }

    showBudgetWarning(percentUsed) {
        const panel = document.getElementById('cost-panel');
        if (!panel.querySelector('.cost-warning')) {
            const warning = document.createElement('div');
            warning.className = 'cost-warning';
            warning.innerHTML = `⚠️ High budget usage: ${percentUsed.toFixed(1)}%`;
            panel.querySelector('.cost-panel-content').insertBefore(
                warning,
                panel.querySelector('.cost-actions')
            );
        }
    }

    async showDetails() {
        try {
            const response = await fetch('/api/costs/details?limit=20');
            if (!response.ok) throw new Error('Failed to fetch cost details');
            
            const data = await response.json();
            this.displayDetailsModal(data.calls);
        } catch (error) {
            console.error('Error fetching cost details:', error);
            alert('Failed to load cost details');
        }
    }

    displayDetailsModal(calls) {
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.id = 'cost-details-modal';
        
        const callsHtml = calls.map((call, idx) => `
            <div class="cost-detail-row">
                <div class="cost-detail-header">
                    <strong>#${calls.length - idx}: ${call.operation}</strong>
                    <span class="cost-detail-time">${new Date(call.timestamp).toLocaleTimeString()}</span>
                </div>
                <div class="cost-detail-info">
                    <span>Model: ${call.model}</span>
                    <span>Tokens: ${call.input_tokens}/${call.output_tokens}</span>
                    <span>Cost: $${(call.cost_cents / 100).toFixed(4)}</span>
                </div>
            </div>
        `).join('');
        
        modal.innerHTML = `
            <div class="modal-content cost-details-content">
                <div class="modal-header">
                    <h2>Cost Details</h2>
                    <button class="modal-close" onclick="this.closest('.modal').remove()">&times;</button>
                </div>
                <div class="modal-body">
                    ${calls.length > 0 ? callsHtml : '<p>No cost data available</p>'}
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="this.closest('.modal').remove()">Close</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }

    async resetCosts() {
        if (!confirm('Reset session cost tracking? This will clear the current session cost data but preserve the log file.')) {
            return;
        }
        
        try {
            const response = await fetch('/api/costs/reset', { method: 'POST' });
            if (!response.ok) throw new Error('Failed to reset costs');
            
            await this.updateCostData();
            
            // Remove warning if present
            const warning = document.querySelector('.cost-warning');
            if (warning) warning.remove();
            
            alert('Cost tracking reset successfully');
        } catch (error) {
            console.error('Error resetting costs:', error);
            alert('Failed to reset cost tracking');
        }
    }

    startAutoUpdate() {
        // Update every 10 seconds
        this.updateInterval = setInterval(() => this.updateCostData(), 10000);
        
        // Initial update
        this.updateCostData();
    }

    stopAutoUpdate() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
}

// Initialize cost tracker when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.costTracker = new CostTracker();
    });
} else {
    window.costTracker = new CostTracker();
}
