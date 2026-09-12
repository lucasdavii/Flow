"""Banco simulado para testar transições com o cliente PostgREST instalado."""

import hashlib
import json
from copy import deepcopy

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
        "before_request": None,
    }

    def handle(request):
        table = request.url.path.rsplit("/", 1)[-1]
        state["requests"].append(request)
        if state["before_request"]:
            state["before_request"](request, state)
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
            assert request.url.params.get("status") in {"eq.waiting", "eq.active"}
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
