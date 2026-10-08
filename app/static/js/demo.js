// TaskPilot AI - Hackathon Live Judge Demonstration Controller

const DemoRunner = {
  async runFullWorkflow() {
    const input = document.getElementById('goalInput');
    const demoPrompt = "I have a Java exam on Monday, DBMS assignment due tomorrow, and project presentation on Wednesday. I have 3 hours available every evening. Create a study plan.";
    
    if (input) {
      input.value = "";
      // Animated typing effect for live presentation
      for (let i = 0; i < demoPrompt.length; i++) {
        input.value += demoPrompt[i];
        if (i % 5 === 0) await new Promise(r => setTimeout(r, 15));
      }
    }

    TaskPilot.showToast("🚀 Step 1: Submitting student goal to TaskPilot AI...", "info");
    await new Promise(r => setTimeout(r, 600));

    // Submit goal
    await TaskPilot.handleRunGoal();

    TaskPilot.showToast("🛡️ Step 2: Agent finished intent parsing & planning. Human approval requested!", "warning");
  },

  async resetAll() {
    if (!confirm("Reset all database records to clean state?")) return;
    try {
      const resp = await fetch('/api/demo/reset', { method: 'POST' });
      if (resp.ok) {
        TaskPilot.showToast("Database reset to pristine state.", "info");
        window.location.reload();
      }
    } catch (e) {
      TaskPilot.showToast("Failed to reset database", "error");
    }
  }
};

window.DemoRunner = DemoRunner;
