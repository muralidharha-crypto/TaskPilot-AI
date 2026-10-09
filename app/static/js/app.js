// TaskPilot AI - Autonomous Productivity Agent Core JS
// Improved accessibility, API error handling, modal behavior, and XSS protection.

'use strict';

const TaskPilot = {
  activeApprovalId: null,
  modalPreviousFocus: null,
  isRunning: false,
  completingTasks: new Set(),

  // ---------------------------------------------------------
  // INITIALIZATION
  // ---------------------------------------------------------

  init() {
    this.bindEvents();
    this.loadDashboardData();
  },

  bindEvents() {
    // Quick suggestion chips
    document.querySelectorAll('.suggestion-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        const input = document.getElementById('goalInput');
        if (!input) return;

        input.value =
          chip.getAttribute('data-goal') ||
          chip.textContent.trim();

        input.focus();
      });
    });

    // Run Agent Goal
    const runBtn = document.getElementById('btnRunGoal');

    if (runBtn) {
      runBtn.addEventListener('click', () => {
        this.handleRunGoal();
      });
    }

    // Ctrl+Enter / Cmd+Enter submits the goal
    const goalInput = document.getElementById('goalInput');

    if (goalInput) {
      goalInput.addEventListener('keydown', (event) => {
        if (
          event.key === 'Enter' &&
          (event.ctrlKey || event.metaKey)
        ) {
          event.preventDefault();
          this.handleRunGoal();
        }
      });
    }

    // Simulate missed study session
    const delayBtn = document.getElementById('btnSimulateDelay');

    if (delayBtn) {
      delayBtn.addEventListener('click', () => {
        this.handleSimulateDelay();
      });
    }

    // Event delegation for dynamically generated buttons
    document.addEventListener('click', (event) => {
      const approveButton = event.target.closest('[data-action="approve-plan"]');
      const rejectButton = event.target.closest('[data-action="reject-plan"]');
      const closeButton = event.target.closest('[data-action="close-modal"]');
      const applyButton = event.target.closest('[data-action="apply-replan"]');

      if (approveButton) {
        event.preventDefault();

        const approvalId = approveButton.dataset.approvalId;

        if (approvalId) {
          this.approvePlan(approvalId);
        }
      }

      if (rejectButton) {
        event.preventDefault();

        const approvalId = rejectButton.dataset.approvalId;

        if (approvalId) {
          this.rejectPlan(approvalId);
        }
      }

      if (closeButton) {
        event.preventDefault();
        this.closeModal(closeButton.dataset.modalId || 'replanModal');
      }

      if (applyButton) {
        event.preventDefault();
        this.applyReplanApproval();
      }
    });

    // Accessible task completion handling
    document.addEventListener('change', (event) => {
      const checkbox = event.target.closest('[data-action="complete-task"]');

      if (checkbox && checkbox.checked) {
        const taskId = checkbox.dataset.taskId;

        if (taskId) {
          this.completeTask(taskId, checkbox);
        }
      }
    });

    // Keyboard accessibility for the replan modal
    document.addEventListener('keydown', (event) => {
      const modal = document.getElementById('replanModal');

      if (!modal || !this.isModalOpen(modal)) return;

      if (event.key === 'Escape') {
        event.preventDefault();
        this.closeModal('replanModal');
        return;
      }

      if (event.key === 'Tab') {
        this.trapModalFocus(event, modal);
      }
    });

    // Clicking the modal backdrop closes the modal
    const modal = document.getElementById('replanModal');

    if (modal) {
      modal.addEventListener('click', (event) => {
        if (event.target === modal) {
          this.closeModal('replanModal');
        }
      });
    }
  },

  // ---------------------------------------------------------
  // SECURITY AND DOM HELPERS
  // ---------------------------------------------------------

  /**
   * Escapes dynamic values before placing them in HTML text or
   * quoted HTML attributes.
   *
   * Prefer textContent for plain text whenever possible.
   */
  escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (character) => {
      const entities = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      };

      return entities[character];
    });
  },

  /**
   * Converts an identifier into a safe positive integer string.
   * Invalid identifiers return an empty string.
   */
  safeId(value) {
    const id = Number(value);

    if (!Number.isSafeInteger(id) || id <= 0) {
      return '';
    }

    return String(id);
  },

  /**
   * Returns a safe CSS badge class suffix.
   */
  safeClass(value, fallback = 'medium') {
    const normalized = String(value ?? fallback)
      .toLowerCase()
      .replace(/[^a-z0-9_-]/g, '');

    return normalized || fallback;
  },

  /**
   * Parses JSON responses and throws a readable error if the
   * server returns invalid JSON or an unsuccessful HTTP status.
   */
  async readResponse(response, fallbackMessage = 'Request failed') {
    let data;

    try {
      data = await response.json();
    } catch {
      throw new Error(
        response.ok
          ? 'The server returned an invalid response.'
          : fallbackMessage
      );
    }

    if (!response.ok) {
      throw new Error(data.error || fallbackMessage);
    }

    return data;
  },

  /**
   * Creates an element containing plain text.
   */
  createTextElement(tagName, text, className = '') {
    const element = document.createElement(tagName);

    if (className) {
      element.className = className;
    }

    element.textContent = String(text ?? '');

    return element;
  },

  /**
   * Adds a polite screen-reader announcement to the page.
   * Creates the live region if the template does not contain one.
   */
  announce(message) {
    let region = document.getElementById('taskpilotAnnouncement');

    if (!region) {
      region = document.createElement('div');
      region.id = 'taskpilotAnnouncement';
      region.setAttribute('role', 'status');
      region.setAttribute('aria-live', 'polite');
      region.setAttribute('aria-atomic', 'true');

      Object.assign(region.style, {
        position: 'absolute',
        width: '1px',
        height: '1px',
        padding: '0',
        margin: '-1px',
        overflow: 'hidden',
        clip: 'rect(0, 0, 0, 0)',
        whiteSpace: 'nowrap',
        border: '0'
      });

      document.body.appendChild(region);
    }

    region.textContent = '';

    window.setTimeout(() => {
      region.textContent = String(message ?? '');
    }, 30);
  },

  /**
   * Converts a date to a readable local time.
   */
  formatTime(value) {
    if (!value) return 'Time unavailable';

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return 'Time unavailable';
    }

    return date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit'
    });
  },

  // ---------------------------------------------------------
  // TOAST NOTIFICATIONS
  // ---------------------------------------------------------

  showToast(message, type = 'info') {
    let container = document.getElementById('toastContainer');

    if (!container) {
      container = document.createElement('div');
      container.id = 'toastContainer';
      container.className = 'toast-container';
      container.setAttribute('aria-label', 'Notifications');
      document.body.appendChild(container);
    }

    const allowedTypes = ['info', 'success', 'error', 'warning'];

    if (!allowedTypes.includes(type)) {
      type = 'info';
    }

    const icons = {
      info: 'ℹ️',
      success: '✅',
      error: '❌',
      warning: '⚠️'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
    toast.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');

    const icon = document.createElement('span');
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = icons[type];

    const text = document.createElement('span');
    text.textContent = String(message ?? '');

    toast.append(icon, text);
    container.appendChild(toast);

    this.announce(message);

    const timeout = window.setTimeout(() => {
      toast.remove();
    }, 5000);

    toast.addEventListener('click', () => {
      window.clearTimeout(timeout);
      toast.remove();
    });
  },

  // ---------------------------------------------------------
  // GOAL SUBMISSION
  // ---------------------------------------------------------

  async handleRunGoal() {
    if (this.isRunning) return;

    const input = document.getElementById('goalInput');

    if (!input || !input.value.trim()) {
      this.showToast(
        'Please enter a goal or task request.',
        'warning'
      );

      if (input) input.focus();

      return;
    }

    const goal = input.value.trim();
    const runBtn = document.getElementById('btnRunGoal');

    this.isRunning = true;

    let originalButtonContent = '';

    if (runBtn) {
      originalButtonContent = runBtn.innerHTML;
      runBtn.disabled = true;
      runBtn.setAttribute('aria-busy', 'true');
      runBtn.textContent = 'Analyzing and planning...';
    }

    this.showToast(
      'TaskPilot is analyzing your request and creating an execution plan.',
      'info'
    );

    try {
      const response = await fetch('/api/agent/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ goal })
      });

      const result = await this.readResponse(
        response,
        'Failed to process your goal.'
      );

      if (result.type === 'RESEARCH') {
        this.showToast('Research synthesis complete!', 'success');
        window.location.href = '/research';
        return;
      }

      if (result.type === 'REPLAN') {
        this.renderReplanModal(result.replan);
        return;
      }

      this.renderPlanResults(result);

      this.showToast(
        'Execution plan created. Human approval is required before execution.',
        'success'
      );
    } catch (error) {
      this.showToast(
        error.message || 'Unable to process your request.',
        'error'
      );
    } finally {
      this.isRunning = false;

      if (runBtn) {
        runBtn.disabled = false;
        runBtn.removeAttribute('aria-busy');

        if (originalButtonContent) {
          runBtn.innerHTML = originalButtonContent;
        } else {
          runBtn.textContent = 'Plan & Execute';
        }
      }
    }
  },

  // ---------------------------------------------------------
  // RENDER EXECUTION PLAN
  // ---------------------------------------------------------

  renderPlanResults(data) {
    const section = document.getElementById('planResultsSection');

    if (!section) {
      this.showToast(
        'The plan results section could not be found.',
        'error'
      );
      return;
    }

    // Support both HTML hidden attributes and older display-based CSS.
    section.hidden = false;
    section.style.display = 'block';

    section.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'auto'
        : 'smooth',
      block: 'start'
    });

    // 1. Understanding breakdown
    const understandingBox = document.getElementById('understandingContent');

    if (understandingBox) {
      const analysis = data.analysis || {};
      const constraints = analysis.constraints || {};
      const detectedTasks = Array.isArray(analysis.detected_tasks)
        ? analysis.detected_tasks
        : [];

      understandingBox.innerHTML = `
        <div class="plan-understanding">
          <div>
            <strong>Intent:</strong>
            <span class="badge badge-medium">
              ${this.escapeHtml(
                String(analysis.intent || 'Unknown')
                  .replace(/_/g, ' ')
                  .toUpperCase()
              )}
            </span>
          </div>

          <div>
            <strong>Total Effort:</strong>
            <span class="badge badge-low">
              ${this.escapeHtml(analysis.total_estimated_hours ?? 0)} hours total
            </span>
          </div>

          <div>
            <strong>Daily Capacity:</strong>
            <span class="badge badge-low">
              ${this.escapeHtml(constraints.daily_hours ?? 'N/A')}h / day
              (${this.escapeHtml(constraints.schedule_timing ?? 'Not specified')})
            </span>
          </div>

          <div><strong>Detected Milestones:</strong></div>

          <ul class="detected-milestones">
            ${
              detectedTasks.length
                ? detectedTasks.map((task) => `
                    <li>
                      <strong>${this.escapeHtml(task.title)}</strong>
                      — Due:
                      ${this.escapeHtml(task.deadline || task.deadline_text || 'Not specified')}
                      (${this.escapeHtml(task.duration_hours ?? 0)}h,
                      ${this.escapeHtml(task.importance || 'Normal')} importance)
                    </li>
                  `).join('')
                : '<li>No milestones were detected.</li>'
            }
          </ul>
        </div>
      `;
    }

    // 2. Proposed actions and approval
    const approvalBox = document.getElementById('approvalContent');

    if (approvalBox) {
      const approval = data.approval || {};
      const approvalId = this.safeId(approval.approval_id);

      this.activeApprovalId = approvalId || null;

      const actions = Array.isArray(approval.proposed_actions)
        ? approval.proposed_actions
        : [];

      if (approvalId) {
        approvalBox.innerHTML = `
          <div class="approval-banner">
            <div>
              <h4>
                <span aria-hidden="true">🛡️</span>
                Human-in-the-Loop Sign-off Required
              </h4>

              <p>
                TaskPilot has formulated
                <strong>${actions.length}</strong> atomic actions.
                Review them before executing.
              </p>
            </div>

            <div class="table-responsive" role="region"
                 aria-label="Proposed actions" tabindex="0">
              <table class="action-audit-table">
                <thead>
                  <tr>
                    <th scope="col">Category</th>
                    <th scope="col">Tool</th>
                    <th scope="col">Proposed Action</th>
                  </tr>
                </thead>

                <tbody>
                  ${
                    actions.length
                      ? actions.map((action) => `
                          <tr>
                            <td>
                              <span class="badge badge-pending">
                                ${this.escapeHtml(
                                  String(action.category || 'General')
                                    .replace(/_/g, ' ')
                                )}
                              </span>
                            </td>

                            <td>
                              <code>
                                ${this.escapeHtml(action.tool_name || 'Unknown')}.${this.escapeHtml(action.function_name || 'Unknown')}
                              </code>
                            </td>

                            <td>${this.escapeHtml(action.description || 'No description provided')}</td>
                          </tr>
                        `).join('')
                      : '<tr><td colspan="3">No proposed actions.</td></tr>'
                  }
                </tbody>
              </table>
            </div>

            <div class="approval-actions">
              <button
                type="button"
                class="btn btn-secondary btn-sm"
                data-action="reject-plan"
                data-approval-id="${this.escapeHtml(approvalId)}">
                <span aria-hidden="true">✕</span>
                Reject
              </button>

              <button
                type="button"
                class="btn btn-success"
                data-action="approve-plan"
                data-approval-id="${this.escapeHtml(approvalId)}">
                <span aria-hidden="true">✓</span>
                Approve &amp; Execute (${actions.length} Actions)
              </button>
            </div>
          </div>
        `;
      } else {
        approvalBox.textContent =
          'No approval request is available for this plan.';
      }
    }

    // 3. Priority breakdown
    const priorityBox = document.getElementById('priorityContent');

    if (priorityBox) {
      const rankedTasks = Array.isArray(data.ranked_tasks)
        ? data.ranked_tasks
        : [];

      priorityBox.innerHTML = rankedTasks.length
        ? `
          <div class="priority-list">
            ${rankedTasks.map((task) => {
              const subtasks = Array.isArray(task.subtasks)
                ? task.subtasks
                : [];

              return `
                <div class="task-item">
                  <div class="task-item-header">
                    <span class="task-title">
                      ${this.escapeHtml(task.title || 'Untitled task')}
                    </span>

                    <span class="badge badge-${this.safeClass(task.priority)}">
                      ${this.escapeHtml(task.priority || 'Medium')}
                      (Score: ${this.escapeHtml(task.priority_score ?? 'N/A')})
                    </span>
                  </div>

                  <div class="priority-explanation">
                    ${this.escapeHtml(task.priority_explanation || 'No explanation provided.')}
                  </div>

                  <div class="subtask-tree">
                    ${
                      subtasks.length
                        ? subtasks.map((subtask) => `
                            <div>
                              <span aria-hidden="true">↳</span>
                              ${this.escapeHtml(subtask.title || 'Untitled subtask')}
                              (${this.escapeHtml(subtask.duration_hours ?? 0)}h)
                            </div>
                          `).join('')
                        : '<div>No subtasks listed.</div>'
                    }
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        `
        : '<p>No ranked tasks are available.</p>';
    }

    // 4. Generated schedule
    const scheduleBox = document.getElementById('generatedScheduleContent');

    if (scheduleBox) {
      const plan = data.plan || {};
      const days = Array.isArray(plan.days) ? plan.days : [];

      scheduleBox.innerHTML = days.length
        ? `
          <div class="timeline-list">
            ${days.map((day) => {
              const sessions = Array.isArray(day.sessions)
                ? day.sessions
                : [];

              return `
                <div class="day-block">
                  <div class="day-header">
                    <span>
                      <span aria-hidden="true">📅</span>
                      ${this.escapeHtml(day.day_name || 'Day')},
                      ${this.escapeHtml(day.formatted_date || '')}
                    </span>

                    <span class="badge badge-low">
                      ${this.escapeHtml(day.total_hours ?? 0)} hrs scheduled
                    </span>
                  </div>

                  <div>
                    ${
                      sessions.length
                        ? sessions.map((session) => `
                            <div class="session-slot">
                              <span class="session-time">
                                <span aria-hidden="true">⏰</span>
                                ${this.escapeHtml(session.start_time || '--:--')}
                                -
                                ${this.escapeHtml(session.end_time || '--:--')}
                              </span>

                              <span class="session-title">
                                ${this.escapeHtml(session.title || 'Untitled session')}
                              </span>

                              <span class="badge badge-${this.safeClass(session.priority)}">
                                ${this.escapeHtml(session.priority || 'Medium')}
                              </span>
                            </div>
                          `).join('')
                        : '<p>No sessions scheduled for this day.</p>'
                    }
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        `
        : '<p>No generated schedule is available.</p>';
    }

    this.announce('Execution plan displayed. Review the proposed actions before approving.');
  },

  // ---------------------------------------------------------
  // APPROVE PLAN
  // ---------------------------------------------------------

  async approvePlan(approvalId) {
    const id = this.safeId(approvalId);

    if (!id) {
      this.showToast('Invalid approval ID.', 'error');
      return;
    }

    const buttons = document.querySelectorAll(
      '[data-action="approve-plan"], [data-action="reject-plan"]'
    );

    buttons.forEach((button) => {
      button.disabled = true;
    });

    this.showToast(
      'Executing approved actions via internal tools...',
      'info'
    );

    try {
      const response = await fetch('/api/agent/approve', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ approval_id: id })
      });

      const result = await this.readResponse(
        response,
        'Failed to execute approved actions.'
      );

      const summary = result.summary || {};

      this.showToast(
        `Execution finished. ${summary.successful_actions ?? 0} actions executed successfully.`,
        'success'
      );

      const approvalBox = document.getElementById('approvalContent');

      if (approvalBox) {
        approvalBox.innerHTML = `
          <div class="card execution-confirmation">
            <div class="execution-confirmation-header">
              <h4>
                <span aria-hidden="true">✓</span>
                Execution Verified &amp; Recorded in Audit Trail
              </h4>

              <span class="badge badge-success">COMPLETED</span>
            </div>

            <div class="execution-timestamps">
              <div>
                <strong>User Approved:</strong>
                ${this.escapeHtml(
                  result.user_approved_at
                    ? this.formatTime(result.user_approved_at)
                    : 'Unavailable'
                )}
              </div>

              <div>
                <strong>Agent Executed:</strong>
                ${this.escapeHtml(
                  result.agent_executed_at
                    ? this.formatTime(result.agent_executed_at)
                    : 'Unavailable'
                )}
              </div>
            </div>

            <p>
              All tasks and schedule sessions are now active in the system.
            </p>
          </div>
        `;

        approvalBox.scrollIntoView({
          behavior: 'auto',
          block: 'nearest'
        });
      }

      this.activeApprovalId = null;
      await this.loadDashboardData();
    } catch (error) {
      this.showToast(
        error.message || 'Failed to execute approved actions.',
        'error'
      );
    } finally {
      buttons.forEach((button) => {
        button.disabled = false;
      });
    }
  },

  // ---------------------------------------------------------
  // REJECT PLAN
  // ---------------------------------------------------------

  async rejectPlan(approvalId) {
    const id = this.safeId(approvalId);

    if (!id) {
      this.showToast('Invalid approval ID.', 'error');
      return;
    }

    if (!window.confirm('Are you sure you want to reject this proposed action plan?')) {
      return;
    }

    try {
      const response = await fetch('/api/agent/reject', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          approval_id: id,
          comments: 'Rejected by user'
        })
      });

      await this.readResponse(response, 'Failed to reject the action plan.');

      this.showToast('Action plan rejected.', 'warning');

      const section = document.getElementById('planResultsSection');

      if (section) {
        section.hidden = true;
        section.style.display = 'none';
      }

      this.activeApprovalId = null;

      const goalInput = document.getElementById('goalInput');

      if (goalInput) {
        goalInput.focus();
      }
    } catch (error) {
      this.showToast(
        error.message || 'Failed to reject the action plan.',
        'error'
      );
    }
  },

  // ---------------------------------------------------------
  // SIMULATE DELAY
  // ---------------------------------------------------------

  async handleSimulateDelay() {
    this.showToast(
      "Simulating a missed study session: 'I couldn't study today'...",
      'warning'
    );

    try {
      const response = await fetch('/api/planner/simulate-delay', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          reason: "I couldn't study today"
        })
      });

      const result = await this.readResponse(
        response,
        'Schedule simulation failed.'
      );

      this.renderReplanModal(result);
    } catch (error) {
      this.showToast(
        error.message || 'Unable to simulate the schedule delay.',
        'error'
      );
    }
  },

  // ---------------------------------------------------------
  // REPLAN MODAL
  // ---------------------------------------------------------

  isModalOpen(modal) {
    return Boolean(
      modal &&
      !modal.hidden &&
      modal.getAttribute('aria-hidden') !== 'true' &&
      (
        modal.classList.contains('active') ||
        getComputedStyle(modal).display !== 'none'
      )
    );
  },

  renderReplanModal(replanData) {
    const modal = document.getElementById('replanModal');
    const content = document.getElementById('replanModalBody');

    if (!modal || !content) {
      this.showToast(
        'The rescheduling dialog could not be found.',
        'error'
      );
      return;
    }

    if (!replanData || typeof replanData !== 'object') {
      this.showToast('Invalid rescheduling data received.', 'error');
      return;
    }

    const approvalId = this.safeId(replanData.approval_id);

    if (!approvalId) {
      this.showToast(
        'The rescheduling response has no valid approval ID.',
        'error'
      );
      return;
    }

    this.activeApprovalId = approvalId;

    const oldSchedules = Array.isArray(replanData.old_plan?.all_schedules)
      ? replanData.old_plan.all_schedules
      : [];

    const newDays = Array.isArray(replanData.new_plan?.days)
      ? replanData.new_plan.days
      : [];

    content.innerHTML = `
      <div class="replan-content">
        <section class="replan-conflict">
          <h4>
            <span aria-hidden="true">⚠️</span>
            Scheduling Conflict Detected
          </h4>

          <p>
            ${this.escapeHtml(
              replanData.conflict_description || 'A scheduling conflict was detected.'
            )}
          </p>
        </section>

        <div class="replan-comparison">
          <section class="replan-old">
            <h5>Original Schedule (Obsolete)</h5>

            <div>
              ${
                oldSchedules.length
                  ? oldSchedules.slice(0, 4).map((schedule) => `
                      <div class="obsolete-schedule">
                        ${this.escapeHtml(schedule.date_str || '')}
                        (${this.escapeHtml(schedule.start_time || '')}):
                        ${this.escapeHtml(schedule.title || 'Untitled session')}
                      </div>
                    `).join('')
                  : '<p>No original schedule details available.</p>'
              }
            </div>
          </section>

          <section class="replan-new">
            <h5>Autonomous Rebalanced Schedule</h5>

            <div>
              ${
                newDays.length
                  ? newDays.slice(0, 2).map((day) => {
                      const sessions = Array.isArray(day.sessions)
                        ? day.sessions
                        : [];

                      return `
                        <div class="rebalanced-day">
                          <strong>
                            ${this.escapeHtml(day.formatted_date || 'Scheduled day')}
                          </strong>

                          ${
                            sessions.length
                              ? sessions.slice(0, 2).map((session) => `
                                  <div class="rebalanced-session">
                                    <span aria-hidden="true">↳</span>
                                    ${this.escapeHtml(session.start_time || '--:--')}
                                    -
                                    ${this.escapeHtml(session.title || 'Untitled session')}
                                  </div>
                                `).join('')
                              : '<p>No sessions available.</p>'
                          }
                        </div>
                      `;
                    }).join('')
                  : '<p>No updated schedule details available.</p>'
              }
            </div>
          </section>
        </div>

        <section class="replan-decision">
          <strong>Human-in-the-Loop Decision:</strong>
          Approve applying this recalculated schedule to restore project feasibility.
        </section>
      </div>
    `;

    // Keep the previous focus so it can be restored when the dialog closes.
    this.modalPreviousFocus = document.activeElement;

    // Support templates that use either hidden or .active.
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    modal.classList.add('active');

    // Make sure assistive technologies recognize the dialog.
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');

    if (!modal.hasAttribute('aria-labelledby')) {
      modal.setAttribute('aria-label', 'Review revised schedule');
    }

    const closeButton = modal.querySelector(
      '[data-action="close-modal"], .modal-close'
    );

    if (closeButton) {
      window.setTimeout(() => closeButton.focus(), 0);
    } else {
      modal.setAttribute('tabindex', '-1');
      modal.focus();
    }

    this.announce(
      'Schedule conflict detected. Review the proposed revised schedule.'
    );
  },

  trapModalFocus(event, modal) {
    const focusableElements = Array.from(
      modal.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), ' +
        'select:not([disabled]), textarea:not([disabled]), ' +
        '[tabindex]:not([tabindex="-1"])'
      )
    ).filter((element) => {
      return element.getClientRects().length > 0;
    });

    if (focusableElements.length === 0) {
      event.preventDefault();
      modal.focus();
      return;
    }

    const first = focusableElements[0];
    const last = focusableElements[focusableElements.length - 1];

    if (
      event.shiftKey &&
      (
        document.activeElement === first ||
        document.activeElement === modal
      )
    ) {
      event.preventDefault();
      last.focus();
    } else if (
      !event.shiftKey &&
      document.activeElement === last
    ) {
      event.preventDefault();
      first.focus();
    }
  },

  closeModal(modalId) {
    const modal = document.getElementById(modalId);

    if (!modal) return;

    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
    modal.hidden = true;

    // Restore focus to the element that opened the modal.
    if (
      this.modalPreviousFocus &&
      document.contains(this.modalPreviousFocus) &&
      typeof this.modalPreviousFocus.focus === 'function'
    ) {
      this.modalPreviousFocus.focus();
    }

    this.modalPreviousFocus = null;
  },

  async applyReplanApproval() {
    if (!this.activeApprovalId) {
      this.showToast(
        'No pending rescheduling approval was found.',
        'warning'
      );
      return;
    }

    const approvalId = this.activeApprovalId;

    this.closeModal('replanModal');

    await this.approvePlan(approvalId);
  },

  // ---------------------------------------------------------
  // TASK COMPLETION
  // ---------------------------------------------------------

  async completeTask(taskId, checkbox = null) {
    const id = this.safeId(taskId);

    if (!id) {
      this.showToast('Invalid task ID.', 'error');
      return;
    }

    if (this.completingTasks.has(id)) return;

    this.completingTasks.add(id);

    if (checkbox) {
      checkbox.disabled = true;
      checkbox.setAttribute('aria-busy', 'true');
    }

    try {
      const response = await fetch(`/api/tasks/${encodeURIComponent(id)}/complete`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json'
        }
      });

      await this.readResponse(response, 'Failed to complete the task.');

      this.showToast('Task marked as completed!', 'success');

      await this.loadDashboardData();
    } catch (error) {
      this.showToast(
        error.message || 'Failed to complete the task.',
        'error'
      );

      if (checkbox) {
        checkbox.checked = false;
      }
    } finally {
      this.completingTasks.delete(id);

      if (checkbox) {
        checkbox.disabled = false;
        checkbox.removeAttribute('aria-busy');
      }
    }
  },

  // ---------------------------------------------------------
  // DASHBOARD DATA
  // ---------------------------------------------------------

  async loadDashboardData() {
    const endpoints = [
      {
        url: '/api/analytics',
        update: (data) => this.updateAnalyticsUI(data)
      },
      {
        url: '/api/tasks',
        update: (data) => this.updateTasksUI(data)
      },
      {
        url: '/api/schedule',
        update: (data) => this.updateScheduleUI(data)
      },
      {
        url: '/api/agent/runs',
        update: (data) => this.updateAgentFeedUI(data)
      }
    ];

    const results = await Promise.allSettled(
      endpoints.map(async (endpoint) => {
        const response = await fetch(endpoint.url, {
          headers: {
            'Accept': 'application/json'
          }
        });

        const data = await this.readResponse(
          response,
          `Failed to load ${endpoint.url}.`
        );

        endpoint.update(data);
      })
    );

    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        console.warn(
          `TaskPilot dashboard request failed (${endpoints[index].url}):`,
          result.reason
        );
      }
    });
  },

  // ---------------------------------------------------------
  // ANALYTICS UI
  // ---------------------------------------------------------

  updateAnalyticsUI(data) {
    const progress = data?.progress || {};

    const setText = (id, value) => {
      const element = document.getElementById(id);

      if (element) {
        element.textContent = String(value);
      }
    };

    setText('statCompleted', progress.completed_tasks ?? 0);
    setText('statInProgress', progress.in_progress_tasks ?? 0);
    setText('statPending', progress.pending_tasks ?? 0);
    setText('statOverdue', progress.overdue_tasks ?? 0);
    setText('statRate', `${progress.completion_rate ?? 0}%`);
    setText(
      'statHours',
      `${progress.completed_hours ?? 0} / ${progress.total_hours ?? 0} hrs`
    );
  },

  // ---------------------------------------------------------
  // TASK LIST UI
  // ---------------------------------------------------------

  updateTasksUI(tasks) {
    const list = document.getElementById('todayTasksList');

    if (!list) return;

    if (!Array.isArray(tasks) || tasks.length === 0) {
      list.innerHTML = `
        <div class="empty-state">
          No active tasks yet. Enter a goal above or run the autonomous demo!
        </div>
      `;
      return;
    }

    list.innerHTML = tasks.slice(0, 6).map((task) => {
      const id = this.safeId(task.id);
      const isCompleted = task.status === 'COMPLETED';
      const priority = task.priority || 'Medium';

      return `
        <article class="task-item">
          <div class="task-item-header">
            <div class="task-heading">
              ${
                id
                  ? `
                    <input
                      type="checkbox"
                      id="complete-task-${this.escapeHtml(id)}"
                      data-action="complete-task"
                      data-task-id="${this.escapeHtml(id)}"
                      ${isCompleted ? 'checked disabled' : ''}
                      aria-label="Mark task ${this.escapeHtml(task.title || 'Untitled task')} as completed"
                    />
                  `
                  : ''
              }

              <label
                class="task-title ${isCompleted ? 'task-completed' : ''}"
                ${id ? `for="complete-task-${this.escapeHtml(id)}"` : ''}
              >
                ${this.escapeHtml(task.title || 'Untitled task')}
              </label>
            </div>

            <span class="badge badge-${this.safeClass(priority)}">
              ${this.escapeHtml(priority)}
            </span>
          </div>

          <div class="task-meta">
            <span>
              <span aria-hidden="true">📅</span>
              Due: ${this.escapeHtml(task.deadline || 'Flexible')}
            </span>

            <span>
              <span aria-hidden="true">⏱️</span>
              ${this.escapeHtml(task.duration_hours ?? 0)}h
            </span>

            <span>
              <span aria-hidden="true">📊</span>
              ${Array.isArray(task.subtasks) ? task.subtasks.length : 0} subtasks
            </span>

            <span class="badge badge-pending">
              ${this.escapeHtml(task.status || 'PENDING')}
            </span>
          </div>
        </article>
      `;
    }).join('');
  },

  // ---------------------------------------------------------
  // SCHEDULE UI
  // ---------------------------------------------------------

  updateScheduleUI(schedules) {
    const timeline = document.getElementById('todayScheduleList');

    if (!timeline) return;

    if (!Array.isArray(schedules) || schedules.length === 0) {
      timeline.innerHTML = `
        <div class="empty-state">
          No scheduled study sessions. Enter a goal to let TaskPilot generate your calendar!
        </div>
      `;
      return;
    }

    timeline.innerHTML = schedules.slice(0, 8).map((schedule) => {
      let statusClass = 'low';

      if (schedule.status === 'COMPLETED') {
        statusClass = 'success';
      } else if (schedule.status === 'MISSED') {
        statusClass = 'high';
      }

      return `
        <article class="session-slot">
          <span class="session-time">
            <span aria-hidden="true">⏰</span>
            ${this.escapeHtml(schedule.start_time || '--:--')}
            -
            ${this.escapeHtml(schedule.end_time || '--:--')}
          </span>

          <div class="session-details">
            <span class="session-title">
              ${this.escapeHtml(schedule.title || 'Untitled session')}
            </span>

            <span class="session-date">
              ${this.escapeHtml(schedule.date_str || '')}
            </span>
          </div>

          <span class="badge badge-${statusClass}">
            ${this.escapeHtml(schedule.status || 'PENDING')}
          </span>
        </article>
      `;
    }).join('');
  },

  // ---------------------------------------------------------
  // AGENT ACTIVITY FEED
  // ---------------------------------------------------------

  updateAgentFeedUI(runs) {
    const feed = document.getElementById('agentActivityFeed');

    if (!feed) return;

    if (!Array.isArray(runs) || runs.length === 0) {
      feed.innerHTML = `
        <div class="empty-state">
          Agent idle. Ready for instruction.
        </div>
      `;
      return;
    }

    feed.innerHTML = runs.slice(0, 6).map((run) => {
      const status = run.status || 'UNKNOWN';

      let feedClass = '';
      let icon = '🧠';

      if (status === 'COMPLETED') {
        feedClass = 'success';
        icon = '✓';
      } else if (status === 'WAITING_APPROVAL') {
        feedClass = 'warning';
        icon = '⏳';
      }

      const goal = String(run.goal || 'Untitled goal');
      const shortGoal = goal.length > 50
        ? `${goal.slice(0, 50)}...`
        : goal;

      return `
        <article class="feed-item ${feedClass}">
          <div>
            <div class="feed-goal">
              <span aria-hidden="true">${icon}</span>
              ${this.escapeHtml(shortGoal)}
            </div>

            <div class="feed-meta">
              Intent:
              <strong>${this.escapeHtml(run.intent || 'Unknown')}</strong>
              |
              Status:
              <strong>${this.escapeHtml(status)}</strong>
            </div>

            <time class="feed-time">
              ${this.escapeHtml(this.formatTime(run.created_at))}
            </time>
          </div>
        </article>
      `;
    }).join('');
  }
};

// ---------------------------------------------------------
// GLOBAL INITIALIZATION
// ---------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  TaskPilot.init();
});