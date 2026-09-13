import hashlib
from copy import deepcopy

import pytest

from tests.session_database import (
    PARTICIPANT_ID, PARTICIPANT_TOKEN, STAGE_ID, environment,
)


@pytest.fixture
def conclusion_environment(environment):
    client, state = environment
    state["rows"]["sessions"][0].update(status="active", current_stage_id=STAGE_ID)
    state["rows"]["stages"][1]["type"] = "conclusion"
    return client, state


def submit(client, payload=None, token=PARTICIPANT_TOKEN, code="K7P2X"):
    return client.post(
        f"/api/sessions/{code}/submissions",
        json={"content": "Conclusão do grupo."} if payload is None else payload,
        headers={} if token is None else {"X-Participant-Token": token},
    )


def test_submission_returns_contract_and_updates_same_group(conclusion_environment):
    client, state = conclusion_environment
    response = submit(client, {"content": "  Primeira conclusão.  "}, code="k7p2x")
    assert response.status_code == 200
    body = response.get_json()
    first = body["data"]["submission"]
    assert body["ok"] is True and body["error"] is None
    assert set(first) == {"id", "group_number", "content", "submitted_by",
                          "created_at", "updated_at"}
    assert first["content"] == "Primeira conclusão."
    assert first["submitted_by"] == PARTICIPANT_ID
    assert first["group_number"] == 1
    peer = {**state["rows"]["participants"][0], "id": "peer",
            "participant_token_hash": hashlib.sha256(b"peer-token").hexdigest()}
    state["rows"]["participants"].append(peer)
    response = submit(client, {"content": "Conclusão revisada."}, token="peer-token")
    assert response.status_code == 200
    revised = response.get_json()["data"]["submission"]
    assert revised["id"] == first["id"]
    assert revised["created_at"] == first["created_at"]
    assert revised["updated_at"] >= first["updated_at"]
    assert revised["submitted_by"] == "peer"
    assert revised["content"] == "Conclusão revisada."
    assert len(state["rows"]["submissions"]) == 1


def test_submission_cannot_spoof_group_author_or_session(conclusion_environment):
    client, state = conclusion_environment
    response = submit(client, {"content": "Texto", "group_number": 99,
                               "submitted_by": "other", "session_id": "other"})
    assert response.status_code == 200
    row = state["rows"]["submissions"][0]
    assert row["group_number"] == 1
    assert row["submitted_by"] == PARTICIPANT_ID
    assert row["session_id"] == state["rows"]["sessions"][0]["id"]


def test_submissions_of_other_groups_are_preserved(conclusion_environment):
    client, state = conclusion_environment
    assert submit(client).status_code == 200
    first = deepcopy(state["rows"]["submissions"][0])
    state["rows"]["participants"][0]["group_number"] = 2
    assert submit(client, {"content": "Segundo grupo"}).status_code == 200
    assert state["rows"]["submissions"][0] == first
    assert len(state["rows"]["submissions"]) == 2


@pytest.mark.parametrize("payload", [[], {}, {"content": " "}, {"content": None},
                                     {"content": 42}, {"content": []}])
def test_submission_rejects_invalid_content(conclusion_environment, payload):
    client, state = conclusion_environment
    response = submit(client, payload)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"
    assert state["requests"] == []


@pytest.mark.parametrize("token,error", [
    (None, "PARTICIPANT_TOKEN_REQUIRED"), (" ", "PARTICIPANT_TOKEN_REQUIRED"),
    ("invalid", "INVALID_PARTICIPANT_TOKEN"),
])
def test_submission_requires_token(conclusion_environment, token, error):
    client, state = conclusion_environment
    response = submit(client, token=token)
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == error
    assert state["rows"]["submissions"] == []


@pytest.mark.parametrize("status", ["waiting", "finished"])
def test_submission_requires_active_session(conclusion_environment, status):
    client, state = conclusion_environment
    state["rows"]["sessions"][0]["status"] = status
    response = submit(client)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "SESSION_NOT_ACTIVE"
    assert state["rows"]["submissions"] == []


@pytest.mark.parametrize("stage_type", ["digital", "presential"])
def test_submission_requires_conclusion_stage(conclusion_environment, stage_type):
    client, state = conclusion_environment
    state["rows"]["stages"][1]["type"] = stage_type
    response = submit(client)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "SUBMISSION_NOT_ALLOWED_IN_CURRENT_STAGE"
    assert state["rows"]["submissions"] == []


def test_submission_rejects_token_from_another_session(conclusion_environment):
    client, state = conclusion_environment
    state["rows"]["participants"][0]["session_id"] = "other-session"
    assert submit(client).status_code == 401
    assert state["rows"]["submissions"] == []


def test_submission_unknown_session(conclusion_environment):
    client, _ = conclusion_environment
    response = submit(client, code="ZZZZZ")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.parametrize("operation", [
    ("POST", "submit_conclusion_atomic"),
])
def test_submission_hides_database_errors(conclusion_environment, operation):
    client, state = conclusion_environment
    state["fail_at"] = operation
    response = submit(client)
    assert response.status_code == 500
    assert response.get_json()["error"]["code"] == "INTERNAL_ERROR"
    assert state["rows"]["submissions"] == []
