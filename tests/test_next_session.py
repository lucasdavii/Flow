"""Avanço de etapas, encerramento e conflitos usando HTTP simulado."""

from copy import deepcopy
from datetime import datetime

import pytest

from backend import create_app
from tests.session_database import (
    SESSION_ID, STAGE_ID, TEACHER_TOKEN, STAGE, environment,
)


@pytest.fixture
def active_environment(environment):
    client, state = environment
    state["rows"]["sessions"][0].update(
        status="active", current_stage_id=STAGE_ID
    )
    return client, state


def post_next(client, token=TEACHER_TOKEN, code="K7P2X"):
    headers = {} if token is None else {"X-Teacher-Token": token}
    return client.post(f"/api/sessions/{code}/next", headers=headers)


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.get_json()
    assert body["ok"] is False
    assert body["data"] is None
    assert body["error"]["code"] == code


def test_start_advance_and_finish(environment):
    client, state = environment
    response = client.post(
        "/api/sessions/K7P2X/start", headers={"X-Teacher-Token": TEACHER_TOKEN}
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["session"]["current_stage"] == STAGE

    response = post_next(client, code="k7p2x")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True, "error": None,
        "data": {"session": {
            "id": SESSION_ID, "code": "K7P2X", "status": "active",
            "current_stage": {**STAGE, "id": "second-stage", "position": 2},
        }},
    }
    session = state["rows"]["sessions"][0]
    assert session["current_stage_id"] == "second-stage"
    assert session["status"] == "active"
    assert datetime.fromisoformat(session["updated_at"]).utcoffset().total_seconds() == 0

    response = post_next(client)
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True, "error": None,
        "data": {"session": {
            "id": SESSION_ID, "code": "K7P2X", "status": "finished",
            "current_stage": None,
        }},
    }
    assert session["current_stage_id"] is None
    assert session["status"] == "finished"
    assert_error(post_next(client), 409, "SESSION_NOT_ACTIVE")


@pytest.mark.parametrize("token", [None, "", "   "])
def test_next_requires_token_without_database_access(active_environment, token):
    client, state = active_environment
    assert_error(post_next(client, token), 401, "TEACHER_TOKEN_REQUIRED")
    assert state["requests"] == []


@pytest.mark.parametrize("status", ["waiting", "active", "finished"])
def test_next_checks_token_before_session_status(active_environment, status):
    client, state = active_environment
    state["rows"]["sessions"][0]["status"] = status
    assert_error(post_next(client, "token-de-outro-professor"), 401, "INVALID_TEACHER_TOKEN")
    assert len(state["requests"]) == 1


@pytest.mark.parametrize("status", ["waiting", "finished"])
def test_next_rejects_inactive_sessions(active_environment, status):
    client, state = active_environment
    state["rows"]["sessions"][0]["status"] = status
    before = deepcopy(state["rows"])
    assert_error(post_next(client), 409, "SESSION_NOT_ACTIVE")
    assert state["rows"] == before


@pytest.mark.parametrize("code", ["ZZZZZ", "invalid"])
def test_next_rejects_unknown_or_malformed_code(active_environment, code):
    client, state = active_environment
    assert_error(post_next(client, code=code), 404, "SESSION_NOT_FOUND")
    assert not any(req.method == "PATCH" for req in state["requests"])


@pytest.mark.parametrize("stage_id", [None, "unknown-stage"])
def test_next_does_not_finish_session_with_invalid_current_stage(active_environment, stage_id):
    client, state = active_environment
    state["rows"]["sessions"][0]["current_stage_id"] = stage_id
    before = deepcopy(state["rows"])
    assert_error(post_next(client), 500, "INTERNAL_ERROR")
    assert state["rows"] == before


def test_next_cannot_use_current_stage_of_another_session(active_environment):
    client, state = active_environment
    state["rows"]["stages"][1]["session_id"] = "another-session"
    assert_error(post_next(client), 500, "INTERNAL_ERROR")
    assert state["rows"]["sessions"][0]["current_stage_id"] == STAGE_ID


def test_single_stage_session_finishes_ignoring_other_sessions(active_environment):
    client, state = active_environment
    state["rows"]["stages"][0]["session_id"] = "another-session"
    other_session = {
        "id": "another-session", "status": "active",
        "current_stage_id": "other-stage", "code": "ZZZZZ",
    }
    state["rows"]["sessions"].append(deepcopy(other_session))
    response = post_next(client)
    assert response.status_code == 200
    assert response.get_json()["data"]["session"]["status"] == "finished"
    assert response.get_json()["data"]["session"]["current_stage"] is None
    assert state["rows"]["sessions"][1] == other_session


@pytest.mark.parametrize("finished", [False, True])
def test_competing_advance_returns_persisted_state_without_skipping(active_environment, finished):
    client, state = active_environment

    def competing_advance(request, state):
        if request.method == "PATCH":
            state["rows"]["sessions"][0].update(
                status="finished" if finished else "active",
                current_stage_id=None if finished else "second-stage",
                updated_at="2026-09-12T12:00:00Z",
            )

    state["before_request"] = competing_advance
    response = post_next(client)
    assert response.status_code == 200
    session = response.get_json()["data"]["session"]
    assert session["status"] == ("finished" if finished else "active")
    assert session["current_stage"] == (
        None if finished else {**STAGE, "id": "second-stage", "position": 2}
    )
    assert state["rows"]["sessions"][0]["updated_at"] == "2026-09-12T12:00:00Z"
    writes = [req for req in state["requests"] if req.method == "PATCH"]
    assert len(writes) == 1
    assert writes[0].url.params["current_stage_id"] == f"eq.{STAGE_ID}"


@pytest.mark.parametrize("request_number", [1, 2, 3, 4])
def test_next_hides_errors_at_each_database_operation(active_environment, request_number):
    client, state = active_environment
    before = deepcopy(state["rows"])

    def fail_request(request, state):
        if len(state["requests"]) == request_number:
            state["fail_at"] = (request.method, request.url.path.rsplit("/", 1)[-1])

    state["before_request"] = fail_request
    response = post_next(client)
    assert_error(response, 500, "INTERNAL_ERROR")
    assert response.get_json()["error"]["message"] == (
        "Não foi possível concluir a operação. Tente novamente."
    )
    assert state["rows"] == before


def test_next_handles_database_initialization_failure(monkeypatch):
    def unavailable():
        raise RuntimeError("Configuração interna indisponível")

    monkeypatch.setattr("backend.services.sessions.get_supabase", unavailable)
    assert_error(post_next(create_app().test_client()), 500, "INTERNAL_ERROR")
