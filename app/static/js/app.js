// TaskPilot AI - Autonomous Productivity Agent Core JS

const TaskPilot = {
  activeApprovalId: null,

  init() {
    this.bindEvents();
    this.loadDashboardData();
  },

  bindEvents() {
    // Quick suggestion chips
    document.querySelectorAll('.suggestion-chip').forEach(chip => {
      chip.addEventListener('click', (e) => {
        const input = document.getElementById('goalInput');
        if (input) {
          input.value = e.target.getAttribute('data-goal') || e.target.innerText;
          input.focus();
        }
      });
    });

    // Run Agent Goal
    const runBtn = document.getElementById('btnRunGoal');
    if (runBtn) {
      runBtn.addEventListener('click', () => this.handleRunGoal());
    }

    // Enter key submit in textarea
    const goalInput = document.getElementById('goalInput');
    if (goalInput) {
      goalInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
          this.handleRunGoal();
        }
      });
    }

    // Simulate Delay / Couldn't study today button
    const delayBtn = document.getElementById('btnSimulateDelay');
    if (delayBtn) {
      delayBtn.addEventListener('click', () => this.handleSimulateDelay());
    }
  },

  showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';
    if (type === 'warning') icon = '⚠️';
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  },

  async handleRunGoal() {
    const input = document.getElementById('goalInput');
    if (!input || !input.value.trim()) {
      this.showToast("Please enter a goal or task request.", "warning");
      return;
    }

    const goal = input.value.trim();
    const runBtn = document.getElementById('btnRunGoal');
    if (runBtn) {
      runBtn.disabled = true;
      runBtn.innerHTML = `<span>⏳</span> Analyzing & Planning...`;
    }

    this.showToast("TaskPilot is analyzing intent and creating an execution plan...", "info");

    try {
      const resp = await fetch('/api/agent/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal })
      });

      const res = await resp.json();
      if (!resp.ok) {
        throw new Error(res.error || "Failed to process goal");
      }

      // Check if research intent
      if (res.type === 'RESEARCH') {
        this.showToast("Research synthesis complete!", "success");
        window.location.href = '/research';
        return;
      }

      // Check if replan intent
      if (res.type === 'REPLAN') {
        this.renderReplanModal(res.replan);
        return;
      }

      // Render Understanding & Approval section
      this.renderPlanResults(res);
      this.showToast("Execution plan created! Human approval required.", "info");

    } catch (err) {
      this.showToast(err.message, "error");
    } finally {
      if (runBtn) {
        runBtn.disabled = false;
        runBtn.innerHTML = `<span>🚀</span> Plan & Execute`;
      }
    }
  },

  renderPlanResults(data) {
    const section = document.getElementById('planResultsSection');
    if (!section) return;

    section.style.display = 'block';
    section.scrollIntoView({ behavior: 'smooth' });

    // 1. Understanding Breakdown
    const understandingBox = document.getElementById('understandingContent');
    if (understandingBox && data.analysis) {
      const a = data.analysis;
      understandingBox.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 0.6rem;">
          <div><strong>Intent:</strong> <span class="badge badge-medium">${a.intent.replace('_', ' ').toUpperCase()}</span></div>
          <div><strong>Total Effort:</strong> <span class="badge badge-low">${a.total_estimated_hours} hours total</span></div>
          <div><strong>Daily Capacity:</strong> <span class="badge badge-low">${a.constraints.daily_hours}h / day (${a.constraints.schedule_timing})</span></div>
          <div><strong>Detected Milestones:</strong></div>
          <ul style="padding-left: 1.25rem; font-size: 0.85rem; color: var(--text-secondary);">
            ${a.detected_tasks.map(t => `
              <li><strong>${t.title}</strong> — Due: <span style="color:#c7d2fe;">${t.deadline || t.deadline_text}</span> (${t.duration_hours}h, ${t.importance} importance)</li>
            `).join('')}
          </ul>
        </div>
      `;
    }

    // 2. Proposed Actions & Approval Banner
    const approvalBox = document.getElementById('approvalContent');
    if (approvalBox && data.approval) {
      this.activeApprovalId = data.approval.approval_id;
      const actions = data.approval.proposed_actions;
      approvalBox.innerHTML = `
        <div class="approval-banner">
          <div>
            <h4 style="color:#f59e0b; margin-bottom: 0.25rem; display: flex; align-items: center; gap: 0.5rem;">
              <span>🛡️</span> Human-in-the-Loop Sign-off Required
            </h4>
            <p style="font-size: 0.85rem; color: var(--text-secondary);">
              TaskPilot has formulated <strong>${actions.length}</strong> atomic actions. Review before executing:
            </p>
          </div>
          
          <table class="action-audit-table">
            <thead>
              <tr>
                <th>Category</th>
                <th>Tool</th>
                <th>Proposed Action</th>
              </tr>
            </thead>
            <tbody>
              ${actions.map(act => `
                <tr>
                  <td><span class="badge badge-pending">${act.category.replace('_', ' ')}</span></td>
                  <td><code>${act.tool_name}.${act.function_name}</code></td>
                  <td>${act.description}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>

          <div style="display: flex; align-items: center; justify-content: flex-end; gap: 0.75rem; margin-top: 0.5rem;">
            <button class="btn btn-secondary btn-sm" onclick="TaskPilot.rejectPlan(${this.activeApprovalId})">
              <span>✕</span> Reject
            </button>
            <button class="btn btn-success" onclick="TaskPilot.approvePlan(${this.activeApprovalId})">
              <span>✓</span> Approve & Execute (${actions.length} Actions)
            </button>
          </div>
        </div>
      `;
    }

    // 3. Multi-factor Priority Breakdown
    const priorityBox = document.getElementById('priorityContent');
    if (priorityBox && data.ranked_tasks) {
      priorityBox.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 0.75rem;">
          ${data.ranked_tasks.map(t => `
            <div class="task-item">
              <div class="task-item-header">
                <span class="task-title">${t.title}</span>
                <span class="badge badge-${t.priority.toLowerCase()}">${t.priority} (Score: ${t.priority_score})</span>
              </div>
              <div style="font-size: 0.8rem; color: #a5b4fc;">
                ${t.priority_explanation}
              </div>
              <div class="subtask-tree">
                ${(t.subtasks || []).map(st => `
                  <div>↳ ${st.title} (${st.duration_hours}h)</div>
                `).join('')}
              </div>
            </div>
          `).join('')}
        </div>
      `;
    }

    // 4. Generated Schedule Timeline
    const scheduleBox = document.getElementById('generatedScheduleContent');
    if (scheduleBox && data.plan) {
      scheduleBox.innerHTML = `
        <div class="timeline-list">
          ${data.plan.days.map(day => `
            <div class="day-block">
              <div class="day-header">
                <span>📅 ${day.day_name}, ${day.formatted_date}</span>
                <span class="badge badge-low">${day.total_hours} hrs scheduled</span>
              </div>
              <div>
                ${day.sessions.map(s => `
                  <div class="session-slot">
                    <span class="session-time">⏰ ${s.start_time} - ${s.end_time}</span>
                    <span style="font-weight: 500;">${s.title}</span>
                    <span class="badge badge-${s.priority.toLowerCase()}">${s.priority}</span>
                  </div>
                `).join('')}
              </div>
            </div>
          `).join('')}
        </div>
      `;
    }
  },

  async approvePlan(approvalId) {
    this.showToast("Executing approved actions via internal tools...", "info");
    try {
      const resp = await fetch('/api/agent/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approval_id: approvalId })
      });
      const res = await resp.json();
      if (!resp.ok) throw new Error(res.error || "Failed to execute approved actions");

      this.showToast(`Success! ${res.summary.successful_actions} actions executed by Agent.`, "success");

      // Replace approval banner with Audit Trail Confirmation
      const approvalBox = document.getElementById('approvalContent');
      if (approvalBox) {
        approvalBox.innerHTML = `
          <div class="card" style="border-color: var(--success); background: rgba(16, 185, 129, 0.05); margin-bottom: 1.5rem;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
              <h4 style="color: var(--success); display: flex; align-items: center; gap: 0.4rem;">
                <span>✓</span> Execution Verified & Recorded in Audit Trail
              </h4>
              <span class="badge badge-success">COMPLETED</span>
            </div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); display: flex; gap: 1.5rem; margin-bottom: 0.75rem;">
              <div><strong>User Approved:</strong> ${new Date(res.user_approved_at).toLocaleTimeString()}</div>
              <div><strong>Agent Executed:</strong> ${new Date(res.agent_executed_at).toLocaleTimeString()}</div>
            </div>
            <div style="font-size: 0.85rem; color: var(--text-primary);">
              All tasks and schedule sessions are now active in the system.
            </div>
          </div>
        `;
      }

      this.loadDashboardData();
    } catch (err) {
      this.showToast(err.message, "error");
    }
  },

  async rejectPlan(approvalId) {
    if (!confirm("Are you sure you want to reject this proposed action plan?")) return;
    try {
      const resp = await fetch('/api/agent/reject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approval_id: approvalId, comments: "Rejected by user" })
      });
      const res = await resp.json();
      this.showToast("Action plan rejected.", "warning");
      const section = document.getElementById('planResultsSection');
      if (section) section.style.display = 'none';
    } catch (err) {
      this.showToast(err.message, "error");
    }
  },

  async handleSimulateDelay() {
    this.showToast("Simulating missed study session: 'I couldn't study today'...", "warning");
    try {
      const resp = await fetch('/api/planner/simulate-delay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: "I couldn't study today" })
      });
      const res = await resp.json();
      if (!resp.ok) throw new Error(res.error || "Simulation failed");

      this.renderReplanModal(res);
    } catch (err) {
      this.showToast(err.message, "error");
    }
  },

  renderReplanModal(replanData) {
    const modal = document.getElementById('replanModal');
    const content = document.getElementById('replanModalBody');
    if (!modal || !content) return;

    this.activeApprovalId = replanData.approval_id;

    content.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 1rem;">
        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger); border-radius: var(--radius-md); padding: 0.85rem;">
          <h4 style="color: var(--danger); display: flex; align-items: center; gap: 0.5rem;">
            <span>⚠️</span> Scheduling Conflict Detected
          </h4>
          <p style="font-size: 0.85rem; margin-top: 0.25rem;">
            ${replanData.conflict_description}
          </p>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
          <div style="background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 0.75rem;">
            <h5 style="color: var(--text-secondary); margin-bottom: 0.5rem; text-transform: uppercase; font-size: 0.75rem;">
              Original Schedule (Obsolete)
            </h5>
            <div style="font-size: 0.8rem; color: var(--text-muted);">
              ${(replanData.old_plan.all_schedules || []).slice(0, 4).map(s => `
                <div style="text-decoration: line-through; margin-bottom: 0.25rem;">
                  ${s.date_str} (${s.start_time}): ${s.title}
                </div>
              `).join('')}
            </div>
          </div>

          <div style="background: var(--bg-input); border: 1px solid var(--success); border-radius: var(--radius-md); padding: 0.75rem;">
            <h5 style="color: var(--success); margin-bottom: 0.5rem; text-transform: uppercase; font-size: 0.75rem;">
              Autonomous Rebalanced Schedule
            </h5>
            <div style="font-size: 0.8rem; color: var(--text-primary);">
              ${(replanData.new_plan.days || []).slice(0, 2).map(d => `
                <div style="margin-bottom: 0.4rem;">
                  <strong>${d.formatted_date}:</strong>
                  ${d.sessions.slice(0, 2).map(s => `
                    <div style="color: #a5b4fc; padding-left: 0.5rem;">↳ ${s.start_time} - ${s.title}</div>
                  `).join('')}
                </div>
              `).join('')}
            </div>
          </div>
        </div>

        <div style="background: rgba(245, 158, 11, 0.1); border: 1px solid var(--warning); border-radius: var(--radius-md); padding: 0.75rem; font-size: 0.82rem;">
          <strong>Human-in-the-Loop Decision:</strong> Approve applying this recalculated schedule to restore project feasibility.
        </div>
      </div>
    `;

    modal.classList.add('active');
  },

  closeModal(modalId) {
    const m = document.getElementById(modalId);
    if (m) m.classList.remove('active');
  },

  async applyReplanApproval() {
    if (!this.activeApprovalId) return;
    this.closeModal('replanModal');
    await this.approvePlan(this.activeApprovalId);
  },

  async completeTask(taskId) {
    try {
      const resp = await fetch(`/api/tasks/${taskId}/complete`, { method: 'POST' });
      const res = await resp.json();
      this.showToast("Task marked completed!", "success");
      this.loadDashboardData();
    } catch (err) {
      this.showToast("Failed to complete task", "error");
    }
  },

  async loadDashboardData() {
    try {
      // 1. Fetch Analytics
      const anResp = await fetch('/api/analytics');
      if (anResp.ok) {
        const data = await anResp.json();
        this.updateAnalyticsUI(data);
      }

      // 2. Fetch Tasks
      const tResp = await fetch('/api/tasks');
      if (tResp.ok) {
        const tasks = await tResp.json();
        this.updateTasksUI(tasks);
      }

      // 3. Fetch Schedule
      const sResp = await fetch('/api/schedule');
      if (sResp.ok) {
        const schedules = await sResp.json();
        this.updateScheduleUI(schedules);
      }

      // 4. Fetch Runs for Activity Feed
      const rResp = await fetch('/api/agent/runs');
      if (rResp.ok) {
        const runs = await rResp.json();
        this.updateAgentFeedUI(runs);
      }
    } catch (e) {
      console.warn("Auto-refresh data error:", e);
    }
  },

  updateAnalyticsUI(data) {
    const p = data.progress || {};
    const setElem = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.innerText = val;
    };
    setElem('statCompleted', p.completed_tasks || 0);
    setElem('statInProgress', p.in_progress_tasks || 0);
    setElem('statPending', p.pending_tasks || 0);
    setElem('statOverdue', p.overdue_tasks || 0);
    setElem('statRate', `${p.completion_rate || 0}%`);
    setElem('statHours', `${p.completed_hours || 0} / ${p.total_hours || 0} hrs`);
  },

  updateTasksUI(tasks) {
    const list = document.getElementById('todayTasksList');
    if (!list) return;

    if (!tasks || tasks.length === 0) {
      list.innerHTML = `
        <div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.9rem;">
          No active tasks yet. Enter a goal above or run the autonomous demo!
        </div>
      `;
      return;
    }

    list.innerHTML = tasks.slice(0, 6).map(t => `
      <div class="task-item">
        <div class="task-item-header">
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <input type="checkbox" ${t.status === 'COMPLETED' ? 'checked disabled' : ''} 
                   onchange="TaskPilot.completeTask(${t.id})" style="cursor: pointer; width: 16px; height: 16px;" />
            <span class="task-title" style="${t.status === 'COMPLETED' ? 'text-decoration: line-through; opacity: 0.6;' : ''}">
              ${t.title}
            </span>
          </div>
          <span class="badge badge-${(t.priority || 'medium').toLowerCase()}">${t.priority}</span>
        </div>
        <div class="task-meta">
          <span>📅 Due: ${t.deadline || 'Flexible'}</span>
          <span>⏱️ ${t.duration_hours}h</span>
          <span>📊 ${t.subtasks ? t.subtasks.length : 0} subtasks</span>
          <span class="badge badge-pending">${t.status}</span>
        </div>
      </div>
    `).join('');
  },

  updateScheduleUI(schedules) {
    const timeline = document.getElementById('todayScheduleList');
    if (!timeline) return;

    if (!schedules || schedules.length === 0) {
      timeline.innerHTML = `
        <div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.9rem;">
          No scheduled study sessions. Enter a goal to let TaskPilot generate your calendar!
        </div>
      `;
      return;
    }

    timeline.innerHTML = schedules.slice(0, 8).map(s => `
      <div class="session-slot">
        <span class="session-time">⏰ ${s.start_time} - ${s.end_time}</span>
        <div style="display: flex; flex-direction: column;">
          <span style="font-weight: 600;">${s.title}</span>
          <span style="font-size: 0.72rem; color: var(--text-secondary);">${s.date_str}</span>
        </div>
        <span class="badge badge-${s.status === 'COMPLETED' ? 'success' : s.status === 'MISSED' ? 'high' : 'low'}">
          ${s.status}
        </span>
      </div>
    `).join('');
  },

  updateAgentFeedUI(runs) {
    const feed = document.getElementById('agentActivityFeed');
    if (!feed) return;

    if (!runs || runs.length === 0) {
      feed.innerHTML = `
        <div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.85rem;">
          Agent idle. Ready for instruction.
        </div>
      `;
      return;
    }

    feed.innerHTML = runs.slice(0, 6).map(r => `
      <div class="feed-item ${r.status === 'COMPLETED' ? 'success' : r.status === 'WAITING_APPROVAL' ? 'warning' : ''}">
        <div>
          <div style="font-weight: 600;">${r.status === 'COMPLETED' ? '✓' : r.status === 'WAITING_APPROVAL' ? '⏳' : '🧠'} ${r.goal.slice(0, 50)}...</div>
          <div style="color: var(--text-secondary); margin-top: 0.2rem;">
            Intent: <strong>${r.intent}</strong> | Status: <strong>${r.status}</strong>
          </div>
          <div class="feed-time">${new Date(r.created_at).toLocaleTimeString()}</div>
        </div>
      </div>
    `).join('');
  }
};

document.addEventListener('DOMContentLoaded', () => TaskPilot.init());
