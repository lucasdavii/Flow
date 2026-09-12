"""Regressões de entrada inválida e envelopes descobertas na revisão."""

from copy import deepcopy

import pytest

from backend import create_app
from tests.test_create_session import VALID_PAYLOAD
from tests.session_database import environment


@pytest.fixture
def client_without_database(monkeypatch):
    def unexpected_database_access():
        pytest.fail("Entrada inválida não deve acessar o banco")
    monkeypatch.setattr("backend.services.sessions.get_supabase", unexpected_database_access)
    return create_app().test_client()


@pytest.mark.parametrize("path", [
    "/api/sessions", "/api/sessions/K7P2X/join",
    "/api/sessions/K7P2X/complete-role", "/api/sessions/K7P2X/submissions",
])
def test_deep_json_returns_validation_error(client_without_database, path):
    response = client_without_database.post(
        path, data="[" * 10000 + "0" + "]" * 10000,
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("invalid_text", ["texto\x00", "texto\ud800"])
@pytest.mark.parametrize("field", ["activity_title", "stage_title", "role_description", "name", "content"])
def test_invalid_utf8_or_nul_is_rejected_before_database(client_without_database, field, invalid_text):
    payload = deepcopy(VALID_PAYLOAD)
    path = "/api/sessions"
    if field == "activity_title":
        payload[field] = invalid_text
    elif field == "stage_title":
        payload["stages"][0]["title"] = invalid_text
    elif field == "role_description":
        payload["roles"][0]["description"] = invalid_text
    else:
        path += "/K7P2X/" + ("join" if field == "name" else "submissions")
        payload = {field: invalid_text}
    response = client_without_database.post(path, json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("method,path,service", [
    ("POST", "/api/sessions", "create_session"),
    ("POST", "/api/sessions/K7P2X/join", "join_session"),
    ("GET", "/api/sessions/K7P2X/state", "get_session_state"),
    ("POST", "/api/sessions/K7P2X/start", "start_session"),
    ("POST", "/api/sessions/K7P2X/next", "advance_session"),
    ("POST", "/api/sessions/K7P2X/complete-role", "complete_role"),
    ("POST", "/api/sessions/K7P2X/submissions", "submit_conclusion"),
    ("GET", "/api/sessions/K7P2X/results", "get_session_results"),
])
def test_unexpected_service_failure_has_stable_json_envelope(monkeypatch, method, path, service):
    def unavailable(*args, **kwargs):
        raise RuntimeError("Detalhes internos de infraestrutura")
    monkeypatch.setattr("backend.routes.sessions." + service, unavailable)
    app = create_app()
    app.config.update(TESTING=True, DEBUG=True)
    response = app.test_client().open(path, method=method, json={})
    assert response.status_code == 500
    assert response.get_json() == {
        "ok": False, "data": None,
        "error": {"code": "INTERNAL_ERROR",
                  "message": "Não foi possível concluir a operação. Tente novamente."},
    }


@pytest.mark.parametrize("path,header,code", [
    ("state", "X-Participant-Token", "INVALID_PARTICIPANT_TOKEN"),
    ("results", "X-Teacher-Token", "INVALID_TEACHER_TOKEN"),
])
def test_invalid_unicode_token_returns_unauthorized(environment, path, header, code):
    client, _ = environment
    response = client.get(f"/api/sessions/K7P2X/{path}", headers={header: "\ud800"})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == code
