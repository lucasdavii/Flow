"""Contrato HTTP de start usando o cliente PostgREST com transporte simulado."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime

import httpx
import pytest
from postgrest import SyncPostgrestClient

from backend import create_app


SESSION_ID = "cc9fa8ec-69a8-45a4-b32c-aeead18fe58d"
STAGE_ID = "d75df973-6948-44f2-91c6-53f30448eb1b"
TEACHER_TOKEN = "token-do-professor"
STAGE = {
    "id": STAGE_ID,
    "position": 1,
    "title": "Pesquisa orientada",
    "type": "digital",
    "instructions": "Encontre duas fontes confiáveis.",
}


@pytest.fixture
def environment(monkeypatch):
    state = {
        "rows": {
            "sessions": [{
                "id": SESSION_ID,
                "code": "K7P2X",
                "status": "waiting",
                "teacher_token_hash": hashlib.sha256(
                    TEACHER_TOKEN.encode()
                ).hexdigest(),
                "current_stage_id": None,
            }],
            # A etapa 2 aparece antes para detectar seleção sem position=1.
            "stages": [
                {**STAGE, "id": "second-stage", "position": 2,
                 "session_id": SESSION_ID},
                {**STAGE, "session_id": SESSION_ID},
            ],
            "participants": [{"id": "student", "session_id": SESSION_ID}],
        },
        "requests": [],
        "fail_at": None,
        "concurrent_start": False,
    }

    def handle(request):
        table = request.url.path.rsplit("/", 1)[-1]
        state["requests"].append(request)
        if state["fail_at"] == (request.method, table):
            return httpx.Response(500, json={
                "code": "XX000", "message": "Detalhes internos do banco",
            })
        if request.method == "PATCH" and state["concurrent_start"]:
            state["rows"]["sessions"][0].update(
                status="active", current_stage_id="later-stage"
            )
        rows = state["rows"][table]
        for field, value in request.url.params.items():
            if value.startswith("eq."):
                rows = [row for row in rows if str(row.get(field)) == value[3:]]
        if request.method == "PATCH":
            assert request.url.params.get("id") == f"eq.{SESSION_ID}"
            assert request.url.params.get("status") == "eq.waiting"
            assert "return=representation" in request.headers["prefer"]
            for row in rows:
                row.update(json.loads(request.content))
        if "limit" in request.url.params:
            rows = rows[:int(request.url.params["limit"])]
        # Simula a projeção de colunas feita pelo PostgREST.
        columns = request.url.params.get("select", "*")
        if columns != "*":
            rows = [{key: row[key] for key in columns.split(",")} for row in rows]
        return httpx.Response(200, json=deepcopy(rows))

    with httpx.Client(transport=httpx.MockTransport(handle)) as http_client:
        database = SyncPostgrestClient(
            "https://database.invalid/rest/v1", http_client=http_client
        )
        monkeypatch.setattr("backend.services.sessions.get_supabase", lambda: database)
        yield create_app().test_client(), state


def post_start(client, token=TEACHER_TOKEN, code="K7P2X"):
    headers = {} if token is None else {"X-Teacher-Token": token}
    return client.post(f"/api/sessions/{code}/start", headers=headers)


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.get_json()
    assert body["ok"] is False
    assert body["data"] is None
    assert body["error"]["code"] == code


def test_start_selects_first_stage_and_persists_active_state(environment):
    client, state = environment
    response = post_start(client, code="k7p2x")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "data": {"session": {
            "id": SESSION_ID, "code": "K7P2X", "status": "active",
            "current_stage": STAGE,
        }},
        "error": None,
    }
    session = state["rows"]["sessions"][0]
    assert session["status"] == "active"
    assert session["current_stage_id"] == STAGE_ID
    assert datetime.fromisoformat(session["updated_at"]).utcoffset().total_seconds() == 0
    assert TEACHER_TOKEN not in response.get_data(as_text=True)
    assert all(TEACHER_TOKEN not in str(req.url) for req in state["requests"])
    assert_error(post_start(client), 409, "SESSION_ALREADY_STARTED")


@pytest.mark.parametrize("token", [None, "", "   "])
def test_start_requires_teacher_token_without_database_access(environment, token):
    client, state = environment
    assert_error(post_start(client, token), 401, "TEACHER_TOKEN_REQUIRED")
    assert state["requests"] == []


@pytest.mark.parametrize("status", ["waiting", "active", "finished"])
def test_start_rejects_other_tokens_before_checking_state(environment, status):
    client, state = environment
    state["rows"]["sessions"][0]["status"] = status
    assert_error(post_start(client, "outro-token"), 401, "INVALID_TEACHER_TOKEN")
    assert len(state["requests"]) == 1


@pytest.mark.parametrize("code", ["ZZZZZ", "invalid"])
def test_start_unknown_or_malformed_session(environment, code):
    client, state = environment
    assert_error(post_start(client, code=code), 404, "SESSION_NOT_FOUND")
    assert not any(req.method == "PATCH" for req in state["requests"])


@pytest.mark.parametrize("status", ["active", "finished"])
def test_start_rejects_already_started_session(environment, status):
    client, state = environment
    state["rows"]["sessions"][0]["status"] = status
    assert_error(post_start(client), 409, "SESSION_ALREADY_STARTED")
    assert len(state["requests"]) == 1


def test_start_requires_participant_from_same_session(environment):
    client, state = environment
    state["rows"]["participants"][0]["session_id"] = "another-session"
    assert_error(post_start(client), 409, "SESSION_HAS_NO_PARTICIPANTS")
    assert state["rows"]["sessions"][0]["status"] == "waiting"


def test_start_requires_first_stage_from_same_session(environment):
    client, state = environment
    state["rows"]["stages"][1]["session_id"] = "another-session"
    assert_error(post_start(client), 500, "INTERNAL_ERROR")
    assert state["rows"]["sessions"][0]["status"] == "waiting"


def test_concurrent_start_cannot_overwrite_progress(environment):
    client, state = environment
    state["concurrent_start"] = True
    assert_error(post_start(client), 409, "SESSION_ALREADY_STARTED")
    assert state["rows"]["sessions"][0]["current_stage_id"] == "later-stage"


@pytest.mark.parametrize("operation", [
    ("GET", "sessions"), ("GET", "participants"),
    ("GET", "stages"), ("PATCH", "sessions"),
])
def test_start_hides_database_errors(environment, operation):
    client, state = environment
    state["fail_at"] = operation
    response = post_start(client)
    assert_error(response, 500, "INTERNAL_ERROR")
    assert response.get_json()["error"]["message"] == (
        "Não foi possível concluir a operação. Tente novamente."
    )
    assert state["rows"]["sessions"][0]["status"] == "waiting"


def test_start_handles_database_initialization_failure(monkeypatch):
    def unavailable():
        raise RuntimeError("Configuração interna indisponível")

    monkeypatch.setattr("backend.services.sessions.get_supabase", unavailable)
    assert_error(post_start(create_app().test_client()), 500, "INTERNAL_ERROR")
