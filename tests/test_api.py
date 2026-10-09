
def test_health_check(client):
    res = client.get('/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert data["service"] == "TaskPilot AI"

def test_api_task_crud(client):
    # 1. Create task
    res = client.post('/api/tasks', json={
        "title": "OS Project",
        "description": "Kernel threads",
        "priority": "HIGH",
        "deadline": "2026-10-15",
        "duration_hours": 3.0
    })
    assert res.status_code == 201
    task = res.get_json()
    task_id = task["id"]

    # 2. Get task
    get_res = client.get(f'/api/tasks/{task_id}')
    assert get_res.status_code == 200
    assert get_res.get_json()["title"] == "OS Project"

    # 3. Update task
    up_res = client.put(f'/api/tasks/{task_id}', json={"priority": "CRITICAL"})
    assert up_res.status_code == 200
    assert up_res.get_json()["priority"] == "CRITICAL"

    # 4. Complete task
    comp_res = client.post(f'/api/tasks/{task_id}/complete')
    assert comp_res.status_code == 200
    assert comp_res.get_json()["status"] == "COMPLETED"

    # 5. Delete task
    del_res = client.delete(f'/api/tasks/{task_id}')
    assert del_res.status_code == 200

def test_api_agent_lifecycle_and_approval(client):
    # Run Agent
    res = client.post('/api/agent/run', json={
        "goal": "I have a Java exam on Monday, DBMS assignment due tomorrow, and project presentation on Wednesday. I have 3 hours available every evening. Create a study plan."
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "WAITING_APPROVAL"
    approval_id = data["approval"]["approval_id"]

    # Approve
    appr_res = client.post('/api/agent/approve', json={"approval_id": approval_id})
    assert appr_res.status_code == 200
    appr_data = appr_res.get_json()
    assert appr_data["status"] == "COMPLETED"

    # List runs
    runs_res = client.get('/api/agent/runs')
    assert runs_res.status_code == 200
    assert len(runs_res.get_json()) > 0

    # Get single run details
    run_id = data["run_id"]
    run_detail = client.get(f'/api/agent/runs/{run_id}')
    assert run_detail.status_code == 200
    assert len(run_detail.get_json()["tool_calls"]) > 0

def test_api_simulate_delay(client):
    # Seed demo first
    seed_res = client.post('/api/demo/seed')
    assert seed_res.status_code == 200
    approval_id = seed_res.get_json()["result"]["approval"]["approval_id"]
    client.post('/api/agent/approve', json={"approval_id": approval_id})

    # Simulate missed session
    delay_res = client.post('/api/planner/simulate-delay', json={"reason": "I couldn't study today"})
    assert delay_res.status_code == 200
    d_data = delay_res.get_json()
    assert d_data["conflict_detected"] is True
    assert "no longer feasible" in d_data["conflict_description"].lower()

def test_api_research(client):
    res = client.post('/api/research', json={"topic": "AI agents in education"})
    assert res.status_code == 200
    data = res.get_json()
    assert "summary" in data
    assert len(data["findings"]) > 0
    assert len(data["action_items"]) > 0

def test_api_analytics(client):
    res = client.get('/api/analytics')
    assert res.status_code == 200
    data = res.get_json()
    assert "progress" in data
    assert "conflicts" in data

def test_api_error_handling(client):
    # Empty goal error
    res = client.post('/api/agent/run', json={"goal": "  "})
    assert res.status_code == 400

    # Invalid task ID
    res = client.get('/api/tasks/99999')
    assert res.status_code == 404

    # Missing approval ID
    res = client.post('/api/agent/approve', json={})
    assert res.status_code == 400
