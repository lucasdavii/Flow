import pytest

from backend import create_app
from tests.session_database import (
    PARTICIPANT_ID, PARTICIPANT_TOKEN, SESSION_ID, STAGE_ID, environment,
)


@pytest.fixture
def active_environment(environment):
    client, state = environment
    state["rows"]["sessions"][0].update(status="active", current_stage_id=STAGE_ID)
    return client, state


def complete(client, payload=None, token=PARTICIPANT_TOKEN, code="K7P2X"):
    return client.post(
        f"/api/sessions/{code}/complete-role",
        json={"stage_id": STAGE_ID} if payload is None else payload,
        headers={} if token is None else {"X-Participant-Token": token},
    )


def test_completion_is_idempotent_and_visible_in_polling(active_environment):
    client, state = active_environment
    response = complete(client, code="k7p2x")
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True and body["error"] is None
    assert body["data"]["completion"] == {
        "participant_id": PARTICIPANT_ID, "stage_id": STAGE_ID,
        "completed_at": state["rows"]["role_completions"][0]["completed_at"],
    }
    assert complete(client).get_json() == body
    assert len(state["rows"]["role_completions"]) == 1
    poll = client.get("/api/sessions/K7P2X/state",
                      headers={"X-Participant-Token": PARTICIPANT_TOKEN})
    assert poll.status_code == 200
    assert poll.get_json()["data"]["participant"]["current_stage_completed"] is True


@pytest.mark.parametrize("payload", [[], {}, {"stage_id": None}, {"stage_id": []},
                                     {"stage_id": 42}, {"stage_id": "invalid"}])
def test_completion_rejects_invalid_payload_without_database(active_environment, payload):
    client, state = active_environment
    response = complete(client, payload)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"
    assert state["requests"] == []


@pytest.mark.parametrize("token,error", [
    (None, "PARTICIPANT_TOKEN_REQUIRED"), (" ", "PARTICIPANT_TOKEN_REQUIRED"),
    ("invalid", "INVALID_PARTICIPANT_TOKEN"),
])
def test_completion_requires_participant_token(active_environment, token, error):
    client, state = active_environment
    response = complete(client, token=token)
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == error
    assert state["rows"]["role_completions"] == []


@pytest.mark.parametrize("status", ["waiting", "finished"])
def test_completion_requires_active_session(active_environment, status):
    client, state = active_environment
    state["rows"]["sessions"][0]["status"] = status
    response = complete(client)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "SESSION_NOT_ACTIVE"
    assert state["rows"]["role_completions"] == []


def test_completion_rejects_stale_stage_and_spoofed_participant(active_environment):
    client, state = active_environment
    response = complete(client, {"stage_id": "3b70e93d-4f83-47cf-8424-8087f262fb75"})
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "STAGE_NOT_CURRENT"
    assert state["rows"]["role_completions"] == []
    response = complete(client, {"stage_id": STAGE_ID.upper(), "participant_id": "other"})
    assert response.status_code == 200
    assert response.get_json()["data"]["completion"]["participant_id"] == PARTICIPANT_ID


def test_completion_does_not_accept_token_from_another_session(active_environment):
    client, state = active_environment
    state["rows"]["participants"][0]["session_id"] = "other-session"
    assert complete(client).status_code == 401
    assert state["rows"]["role_completions"] == []


def test_completion_unknown_session(active_environment):
    client, state = active_environment
    response = complete(client, code="ZZZZZ")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.parametrize("operation", [
    ("POST", "complete_role_atomic"),
])
def test_completion_hides_database_errors(active_environment, operation):
    client, state = active_environment
    if operation == ("GET", "role_completions"):
        assert complete(client).status_code == 200
    state["fail_at"] = operation
    response = complete(client)
    assert response.status_code == 500
    assert response.get_json()["error"] == {
        "code": "INTERNAL_ERROR",
        "message": "Não foi possível concluir a operação. Tente novamente.",
    }
