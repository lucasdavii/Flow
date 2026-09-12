"""Fluxo integrado dos oito endpoints com transporte PostgREST simulado."""

from backend import create_app
from tests.session_database import environment
from tests.test_create_session import VALID_PAYLOAD


def test_full_session_lifecycle(environment):
    client, state = environment
    state["rows"] = {table: [] for table in state["rows"]}
    created = client.post("/api/sessions", json=VALID_PAYLOAD)
    assert created.status_code == 201
    data = created.get_json()["data"]
    code = data["session"]["code"]
    teacher = {"X-Teacher-Token": data["teacher_token"]}
    session_id = data["session"]["id"]
    students = []
    for name in ("Ana", "Bruno", "Carla", "Daniel", "Eva"):
        response = client.post(f"/api/sessions/{code}/join", json={"name": name})
        assert response.status_code == 201
        student = response.get_json()["data"]
        students.append((student["participant"], {
            "X-Participant-Token": student["participant_token"],
        }))
    assert [student[0]["group_number"] for student in students] == [1, 1, 1, 1, 2]
    participant, token = students[0]
    poll_url = f"/api/sessions/{code}/state"
    waiting = client.get(poll_url, headers=token).get_json()["data"]
    assert waiting["session"]["status"] == "waiting"
    assert waiting["session"]["current_stage"] is None
    assert len(waiting["group"]["members"]) == 4
    started = client.post(f"/api/sessions/{code}/start", headers=teacher)
    assert started.status_code == 200
    first_stage = started.get_json()["data"]["session"]["current_stage"]
    assert client.post(f"/api/sessions/{code}/join", json={"name": "Atrasado"}).status_code == 409
    assert client.get(poll_url, headers=token).get_json()["data"]["session"]["current_stage"] == first_stage
    completion_url = f"/api/sessions/{code}/complete-role"
    completed = client.post(completion_url, headers=token, json={"stage_id": first_stage["id"]})
    assert completed.status_code == 200
    assert client.post(completion_url, headers=token, json={"stage_id": first_stage["id"]}).get_json() == completed.get_json()
    assert client.get(poll_url, headers=token).get_json()["data"]["participant"]["current_stage_completed"] is True
    next_url = f"/api/sessions/{code}/next"
    assert client.post(next_url, headers=teacher).status_code == 200
    second = client.get(poll_url, headers=token).get_json()["data"]
    assert second["session"]["current_stage"]["position"] == 2
    assert second["participant"]["current_stage_completed"] is False
    assert client.post(completion_url, headers=token, json={"stage_id": first_stage["id"]}).status_code == 409
    submission_url = f"/api/sessions/{code}/submissions"
    assert client.post(submission_url, headers=token, json={"content": "Muito cedo"}).status_code == 409
    conclusion = client.post(next_url, headers=teacher).get_json()["data"]["session"]
    assert conclusion["current_stage"]["type"] == "conclusion"
    sent = client.post(submission_url, headers=token, json={"content": "Primeira versão"})
    assert sent.status_code == 200
    revised = client.post(submission_url, headers=students[1][1], json={"content": "Conclusão revisada"})
    assert revised.status_code == 200
    assert revised.get_json()["data"]["submission"]["id"] == sent.get_json()["data"]["submission"]["id"]
    final = client.post(next_url, headers=teacher)
    assert final.status_code == 200
    assert final.get_json()["data"]["session"]["status"] == "finished"
    poll = client.get(poll_url, headers=token).get_json()["data"]
    assert poll["session"]["current_stage"] is None
    assert poll["session"]["status"] == "finished"
    assert poll["participant"]["current_stage_completed"] is False
    assert client.post(submission_url, headers=token, json={"content": "Tarde"}).status_code == 409
    report = client.get(f"/api/sessions/{code}/results", headers=teacher)
    assert report.status_code == 200
    results = report.get_json()["data"]
    assert results["session"]["id"] == session_id
    assert results["session"]["status"] == "finished"
    assert len(results["groups"]) == 2
    assert results["groups"][0]["submission"]["content"] == "Conclusão revisada"
    assert results["groups"][0]["submission"]["submitted_by"] == students[1][0]["id"]
    assert results["groups"][1]["submission"] is None
    counts = {member["id"]: member["completed_stage_count"]
              for group in results["groups"] for member in group["members"]}
    assert counts[participant["id"]] == 1
    assert sum(counts.values()) == 1
    assert "token" not in report.get_data(as_text=True)
