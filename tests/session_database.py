"""Banco simulado para testar transições com o cliente PostgREST instalado."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from postgrest import SyncPostgrestClient

from backend import create_app


SESSION_ID = "cc9fa8ec-69a8-45a4-b32c-aeead18fe58d"
STAGE_ID = "d75df973-6948-44f2-91c6-53f30448eb1b"
TEACHER_TOKEN = "token-do-professor"
PARTICIPANT_TOKEN = "token-do-aluno"
PARTICIPANT_ID = "f5168159-a39a-4c93-aa57-4e65fbf61224"
ROLE_ID = "ef6beabb-03ab-455a-8f1c-77e63d8fcb12"
STAGE = {
    "id": STAGE_ID,
    "position": 1,
    "title": "Pesquisa orientada",
    "type": "digital",
    "instructions": "Encontre duas fontes confiáveis.",
}


def project(row, columns, tables):
    """Projeta colunas e os relacionamentos usados pela API nos testes."""
    if columns == "*":
        return dict(row)
    fields, start, depth = [], 0, 0
    for index, char in enumerate(columns):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            fields.append(columns[start:index])
            start = index + 1
    fields.append(columns[start:])
    result = {}
    for field in fields:
        if "(" not in field:
            result[field] = row[field]
            continue
        relationship, nested = field.split("(", 1)
        alias, target = relationship.split(":", 1)
        table = target.split("!", 1)[0]
        foreign_key = {"roles": "role_id", "stages": "current_stage_id",
                       "participants": "participant_id"}[table]
        related = next((item for item in tables[table]
                        if item["id"] == row.get(foreign_key)), None)
        result[alias] = project(related, nested[:-1], tables) if related else None
    return result


@pytest.fixture
def environment(monkeypatch):
    state = {
        "rows": {
            "sessions": [{
                "id": SESSION_ID,
                "code": "K7P2X",
                "status": "waiting",
                "activity_title": "Uso consciente da água",
                "group_size": 4,
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
            "participants": [{
                "id": PARTICIPANT_ID, "session_id": SESSION_ID,
                "name": "Ana Souza", "group_number": 1, "role_id": ROLE_ID,
                "created_at": "2026-09-12T12:00:00Z",
                "participant_token_hash": hashlib.sha256(
                    PARTICIPANT_TOKEN.encode()
                ).hexdigest(),
            }],
            "roles": [{
                "id": ROLE_ID, "session_id": SESSION_ID, "name": "pesquisador",
                "type": "digital", "description": "Localiza informações.",
                "created_at": "2026-09-12T12:00:00Z",
            }],
            "role_completions": [],
            "submissions": [],
        },
        "requests": [],
        "fail_at": None,
        "concurrent_start": False,
        "before_request": None,
        "page_cap": None,
    }

    def handle(request):
        endpoint = request.url.path.rsplit("/", 1)[-1]
        state["requests"].append(request)
        if state["before_request"]:
            state["before_request"](request, state)
        if endpoint == "submit_conclusion_atomic":
            values = json.loads(request.content)
            session = next((s for s in state["rows"]["sessions"]
                            if s["code"] == values["p_session_code"]), None)
            participant = next((p for p in state["rows"]["participants"]
                                if session and p["session_id"] == session["id"]
                                and p["participant_token_hash"] ==
                                values["p_participant_token_hash"]), None)
            stage = next((s for s in state["rows"]["stages"]
                          if session and s["id"] == session["current_stage_id"]), None)
            error = None
            if session is None:
                error = "SESSION_NOT_FOUND"
            elif participant is None:
                error = "INVALID_PARTICIPANT_TOKEN"
            elif session["status"] != "active":
                error = "SESSION_NOT_ACTIVE"
            elif stage is None or stage["type"] != "conclusion":
                error = "SUBMISSION_NOT_ALLOWED_IN_CURRENT_STAGE"
            if state["fail_at"] == ("POST", endpoint):
                error = "internal"
            if error:
                return httpx.Response(400, json={"code": "P0001", "message": error, "hint": None, "details": None})
            submission = next((s for s in state["rows"]["submissions"]
                               if s["session_id"] == session["id"]
                               and s["group_number"] == participant["group_number"]), None)
            now = datetime.now(timezone.utc).isoformat()
            if submission is None:
                submission = {
                    "id": str(uuid4()), "session_id": session["id"],
                    "group_number": participant["group_number"], "created_at": now,
                }
                state["rows"]["submissions"].append(submission)
            submission.update(content=values["p_content"],
                              submitted_by=participant["id"], updated_at=now)
            return httpx.Response(200, json=[deepcopy(submission)])
        if endpoint == "complete_role_atomic":
            values = json.loads(request.content)
            session = next((s for s in state["rows"]["sessions"]
                            if s["code"] == values["p_session_code"]), None)
            participant = next((p for p in state["rows"]["participants"]
                                if session and p["session_id"] == session["id"]
                                and p["participant_token_hash"] ==
                                values["p_participant_token_hash"]), None)
            error = None
            if session is None:
                error = "SESSION_NOT_FOUND"
            elif participant is None:
                error = "INVALID_PARTICIPANT_TOKEN"
            elif session["status"] != "active":
                error = "SESSION_NOT_ACTIVE"
            elif session["current_stage_id"] != values["p_stage_id"]:
                error = "STAGE_NOT_CURRENT"
            if state["fail_at"] == ("POST", endpoint):
                error = "internal"
            if error:
                return httpx.Response(400, json={"code": "P0001", "message": error, "hint": None, "details": None})
            completion = next((r for r in state["rows"]["role_completions"]
                               if r["participant_id"] == participant["id"]
                               and r["stage_id"] == values["p_stage_id"]), None)
            if completion is None:
                completion = {
                    "id": str(uuid4()), "participant_id": participant["id"],
                    "stage_id": values["p_stage_id"],
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
                state["rows"]["role_completions"].append(completion)
            return httpx.Response(200, json=[{
                key: completion[key]
                for key in ("participant_id", "stage_id", "completed_at")
            }])
        if endpoint == "join_session_atomic":
            values = json.loads(request.content)
            session = next(
                (
                    row for row in state["rows"]["sessions"]
                    if row["code"] == values["p_session_code"]
                ),
                None,
            )
            if session is None:
                return httpx.Response(404, json={
                    "code": "P0002", "message": "SESSION_NOT_FOUND",
                })
            if session["status"] != "waiting":
                return httpx.Response(400, json={
                    "code": "P0001", "message": "SESSION_ALREADY_STARTED",
                })

            roles = sorted(
                state["rows"]["roles"],
                key=lambda role: (role["created_at"], role["id"]),
            )
            participant_count = len([
                row for row in state["rows"]["participants"]
                if row["session_id"] == session["id"]
            ])
            role = roles[
                (participant_count % session["group_size"]) % len(roles)
            ]
            participant = {
                "id": str(uuid4()),
                "session_id": session["id"],
                "role_id": role["id"],
                "name": values["p_name"],
                "group_number": participant_count // session["group_size"] + 1,
                "participant_token_hash": values["p_token_hash"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            state["rows"]["participants"].append(participant)
            return httpx.Response(200, json=[{
                "participant_id": participant["id"],
                "participant_name": participant["name"],
                "group_number": participant["group_number"],
                "role_id": role["id"],
                "role_name": role["name"],
                "role_type": role["type"],
                "role_description": role["description"],
                "session_status": session["status"],
            }])

        table = endpoint
        if state["fail_at"] == (request.method, table):
            return httpx.Response(500, json={
                "code": "XX000", "message": "Detalhes internos do banco",
            })
        if request.method == "POST" and request.url.path.endswith(
            "/rpc/join_session_atomic"
        ):
            values = json.loads(request.content)
            code = values["p_code"]
            session = next(
                (row for row in state["rows"]["sessions"]
                 if row["code"] == code),
                None,
            )
            if session is None:
                return httpx.Response(
                    400, json={"code": "P0001", "message": "SESSION_NOT_FOUND"}
                )
            if session["status"] != "waiting":
                return httpx.Response(
                    400,
                    json={"code": "P0002", "message": "SESSION_ALREADY_STARTED"},
                )
            participants = [
                row for row in state["rows"]["participants"]
                if row["session_id"] == session["id"]
            ]
            roles = [
                row for row in state["rows"]["roles"]
                if row["session_id"] == session["id"]
            ]
            position = len(participants) % session["group_size"]
            role = sorted(
                roles, key=lambda row: (row.get("created_at", ""), row["id"])
            )[position % len(roles)]
            row = {
                "id": str(uuid4()),
                "session_id": session["id"],
                "role_id": role["id"],
                "name": values["p_name"],
                "group_number": len(participants) // session["group_size"] + 1,
                "participant_token_hash": values["p_token_hash"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            state["rows"]["participants"].append(row)
            return httpx.Response(200, json={
                "participant": {
                    "id": row["id"],
                    "name": row["name"],
                    "group_number": row["group_number"],
                    "role": {
                        "id": role["id"],
                        "name": role["name"],
                        "type": role["type"],
                        "description": role["description"],
                    },
                },
                "session_status": session["status"],
            })
        if request.method == "PATCH" and state["concurrent_start"]:
            state["rows"]["sessions"][0].update(
                status="active", current_stage_id="later-stage"
            )
        rows = state["rows"][table]
        for field, value in request.url.params.items():
            if value.startswith("eq."):
                rows = [row for row in rows if str(row.get(field)) == value[3:]]
            elif value.startswith("in.("):
                options = [item.strip('"') for item in value[4:-1].split(",")]
                rows = [row for row in rows if str(row.get(field)) in options]
        if request.method == "POST":
            values = json.loads(request.content)
            values = values if isinstance(values, list) else [values]
            changed = []
            conflict = request.url.params.get("on_conflict", "id").split(",")
            for value in values:
                existing = next((row for row in state["rows"][table]
                                 if all(key in value and row.get(key) == value[key]
                                        for key in conflict)), None)
                if existing is not None:
                    if "resolution=ignore-duplicates" in request.headers["prefer"]:
                        continue
                    existing.update(value)
                    changed.append(existing)
                else:
                    now = datetime.now(timezone.utc).isoformat()
                    row = {"id": str(uuid4()), "created_at": now,
                           "updated_at": now, **value}
                    if table == "role_completions":
                        row["completed_at"] = now
                    if table == "sessions":
                        row.setdefault("current_stage_id", None)
                    state["rows"][table].append(row)
                    changed.append(row)
            rows = changed
        if request.method == "PATCH":
            assert request.url.params.get("id", "").startswith("eq.")
            assert request.url.params.get("status") in {"eq.waiting", "eq.active"}
            assert "return=representation" in request.headers["prefer"]
            for row in rows:
                row.update(json.loads(request.content))
        for spec in reversed(request.url.params.get("order", "").split(",")):
            if spec:
                field, direction, *_ = spec.split(".")
                rows = sorted(rows, key=lambda row: row.get(field, ""),
                              reverse=direction == "desc")
        total = len(rows)
        offset = int(request.url.params.get("offset", 0))
        rows = rows[offset:]
        if "limit" in request.url.params:
            rows = rows[:int(request.url.params["limit"])]
        if state["page_cap"]:
            rows = rows[:state["page_cap"]]
        columns = request.url.params.get("select", "*")
        rows = [project(row, columns, state["rows"]) for row in rows]
        headers = {"content-range": f"0-{max(0, len(rows) - 1)}/{total}"}
        return httpx.Response(200, json=deepcopy(rows), headers=headers)

    with httpx.Client(transport=httpx.MockTransport(handle)) as http_client:
        database = SyncPostgrestClient(
            "https://database.invalid/rest/v1", http_client=http_client
        )
        monkeypatch.setattr("backend.services.sessions.get_supabase", lambda: database)
        yield create_app().test_client(), state
