import hashlib
import re

import pytest

from backend import create_app
from backend.services.sessions import SessionCreationError, create_session


VALID_PAYLOAD = {
    "activity_title": "Uso consciente da água",
    "group_size": 4,
    "stages": [
        {
            "position": 1,
            "title": "Pesquisa orientada",
            "type": "digital",
            "instructions": "Encontre duas fontes confiáveis.",
        },
        {
            "position": 2,
            "title": "Discussão do grupo",
            "type": "presential",
            "instructions": "Guardem os aparelhos e discutam.",
        },
        {
            "position": 3,
            "title": "Conclusão",
            "type": "conclusion",
            "instructions": "Registrem a conclusão do grupo.",
        },
    ],
    "roles": [
        {
            "name": "pesquisador",
            "type": "digital",
            "description": "Localiza informações.",
        },
        {
            "name": "relator",
            "type": "presential",
            "description": "Organiza a síntese.",
        },
    ],
}


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeOperation:
    def __init__(self, database, table_name, action, values=None):
        self.database = database
        self.table_name = table_name
        self.action = action
        self.values = values
        self.filters = {}

    def eq(self, field, value):
        self.filters[field] = value
        return self

    def execute(self):
        if self.action == "delete":
            self.database.deleted.append((self.table_name, self.filters))
            return FakeResult([])

        if self.database.fail_on_insert == self.table_name:
            raise RuntimeError("Falha simulada")

        self.database.inserted[self.table_name] = self.values
        if self.table_name == "sessions":
            return FakeResult(
                [
                    {
                        **self.values,
                        "id": "cc9fa8ec-69a8-45a4-b32c-aeead18fe58d",
                        "created_at": "2026-09-11T18:30:00+00:00",
                    }
                ]
            )
        return FakeResult(self.values)


class FakeTable:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name

    def insert(self, values):
        return FakeOperation(self.database, self.table_name, "insert", values)

    def delete(self):
        return FakeOperation(self.database, self.table_name, "delete")


class FakeDatabase:
    def __init__(self, fail_on_insert=None):
        self.inserted = {}
        self.deleted = []
        self.fail_on_insert = fail_on_insert

    def table(self, table_name):
        return FakeTable(self, table_name)


@pytest.fixture
def fake_database(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setattr(
        "backend.services.sessions.get_supabase", lambda: database
    )
    return database


def test_create_session_returns_contract_and_stores_only_token_hash(fake_database):
    app = create_app()
    response = app.test_client().post("/api/sessions", json=VALID_PAYLOAD)

    assert response.status_code == 201
    body = response.get_json()
    assert body["ok"] is True
    assert body["error"] is None
    assert body["data"]["session"]["status"] == "waiting"
    assert body["data"]["session"]["current_stage"] is None
    assert body["data"]["session"]["participant_count"] == 0
    assert re.fullmatch(
        r"[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{5}",
        body["data"]["session"]["code"],
    )

    raw_token = body["data"]["teacher_token"]
    stored_session = fake_database.inserted["sessions"]
    assert raw_token not in str(stored_session)
    assert stored_session["teacher_token_hash"] == hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()
    assert len(fake_database.inserted["stages"]) == 3
    assert len(fake_database.inserted["roles"]) == 2


@pytest.mark.parametrize(
    ("change", "expected_message"),
    [
        ({"activity_title": ""}, "activity_title"),
        ({"group_size": 1}, "group_size"),
        ({"stages": []}, "stages"),
        ({"roles": []}, "roles"),
    ],
)
def test_create_session_rejects_invalid_payload(change, expected_message):
    app = create_app()
    payload = {**VALID_PAYLOAD, **change}

    response = app.test_client().post("/api/sessions", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "data": None,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": response.get_json()["error"]["message"],
        },
    }
    assert expected_message in response.get_json()["error"]["message"]


def test_create_session_rejects_non_json_body():
    app = create_app()

    response = app.test_client().post("/api/sessions", data="not json")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_session_removes_partial_data_after_related_insert_failure():
    database = FakeDatabase(fail_on_insert="roles")

    with pytest.raises(SessionCreationError):
        create_session(VALID_PAYLOAD, database=database)

    assert database.deleted == [
        (
            "sessions",
            {"id": "cc9fa8ec-69a8-45a4-b32c-aeead18fe58d"},
        )
    ]


def test_create_session_returns_json_error_when_database_is_unavailable(monkeypatch):
    def unavailable_database():
        raise RuntimeError("Banco indisponível")

    monkeypatch.setattr(
        "backend.services.sessions.get_supabase", unavailable_database
    )
    app = create_app()

    response = app.test_client().post("/api/sessions", json=VALID_PAYLOAD)

    assert response.status_code == 500
    assert response.get_json() == {
        "ok": False,
        "data": None,
        "error": {
            "code": "SESSION_CODE_GENERATION_FAILED",
            "message": "Não foi possível criar a sessão. Tente novamente.",
        },
    }
