import hashlib

import pytest

from backend import create_app


SESSION_ID = "cc9fa8ec-69a8-45a4-b32c-aeead18fe58d"
ROLE_ONE_ID = "ef6beabb-03ab-455a-8f1c-77e63d8fcb12"
ROLE_TWO_ID = "511da378-0b5c-4578-9f40-dbc024a5328f"


class FakeResult:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class FakeQuery:
    def __init__(self, database, table_name, action, values=None, count=None):
        self.database = database
        self.table_name = table_name
        self.action = action
        self.values = values
        self.count_requested = count
        self.filters = {}
        self.limit_value = None

    def eq(self, field, value):
        self.filters[field] = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def order(self, _field):
        return self

    def execute(self):
        if self.database.fail:
            raise RuntimeError("Falha simulada")

        if self.action == "insert":
            participant = {
                **self.values,
                "id": "f5168159-a39a-4c93-aa57-4e65fbf61224",
            }
            self.database.inserted_participant = participant
            return FakeResult([participant])

        rows = [
            row
            for row in self.database.rows[self.table_name]
            if all(row.get(field) == value for field, value in self.filters.items())
        ]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        count = len(rows) if self.count_requested == "exact" else None
        return FakeResult(rows, count=count)


class FakeTable:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name

    def select(self, _columns, count=None):
        return FakeQuery(
            self.database, self.table_name, "select", count=count
        )

    def insert(self, values):
        return FakeQuery(self.database, self.table_name, "insert", values=values)


class FakeDatabase:
    def __init__(self, status="waiting", include_session=True, participant_count=0):
        self.fail = False
        self.inserted_participant = None
        self.rows = {
            "sessions": (
                [
                    {
                        "id": SESSION_ID,
                        "code": "K7P2X",
                        "status": status,
                        "group_size": 4,
                    }
                ]
                if include_session
                else []
            ),
            "roles": [
                {
                    "id": ROLE_ONE_ID,
                    "session_id": SESSION_ID,
                    "name": "pesquisador",
                    "type": "digital",
                    "description": "Localiza informações.",
                    "created_at": "2026-09-11T18:30:00+00:00",
                },
                {
                    "id": ROLE_TWO_ID,
                    "session_id": SESSION_ID,
                    "name": "relator",
                    "type": "presential",
                    "description": "Organiza a síntese.",
                    "created_at": "2026-09-11T18:30:01+00:00",
                },
            ],
            "participants": [
                {"id": f"participant-{index}", "session_id": SESSION_ID}
                for index in range(participant_count)
            ],
        }

    def table(self, table_name):
        return FakeTable(self, table_name)


def install_fake_database(monkeypatch, database):
    monkeypatch.setattr(
        "backend.services.sessions.get_supabase", lambda: database
    )


def test_join_normalizes_code_assigns_group_and_stores_only_token_hash(monkeypatch):
    database = FakeDatabase(participant_count=4)
    install_fake_database(monkeypatch, database)
    app = create_app()

    response = app.test_client().post(
        "/api/sessions/k7p2x/join", json={"name": "  Ana Souza  "}
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["ok"] is True
    assert body["error"] is None
    assert body["data"]["participant"] == {
        "id": "f5168159-a39a-4c93-aa57-4e65fbf61224",
        "name": "Ana Souza",
        "group_number": 2,
        "role": {
            "id": ROLE_ONE_ID,
            "name": "pesquisador",
            "type": "digital",
            "description": "Localiza informações.",
        },
    }
    assert body["data"]["session_status"] == "waiting"

    raw_token = body["data"]["participant_token"]
    stored = database.inserted_participant
    assert raw_token not in str(stored)
    assert stored["participant_token_hash"] == hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()


def test_join_returns_not_found_for_unknown_session(monkeypatch):
    database = FakeDatabase(include_session=False)
    install_fake_database(monkeypatch, database)
    app = create_app()

    response = app.test_client().post(
        "/api/sessions/K7P2X/join", json={"name": "Ana"}
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_join_rejects_session_that_already_started(monkeypatch):
    database = FakeDatabase(status="active")
    install_fake_database(monkeypatch, database)
    app = create_app()

    response = app.test_client().post(
        "/api/sessions/K7P2X/join", json={"name": "Ana"}
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "SESSION_ALREADY_STARTED"


@pytest.mark.parametrize(
    ("code", "payload"),
    [
        ("O01I", {"name": "Ana"}),
        ("K7P2X", {"name": ""}),
        ("K7P2X", None),
    ],
)
def test_join_rejects_invalid_input(code, payload):
    app = create_app()

    response = app.test_client().post(
        f"/api/sessions/{code}/join", json=payload
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_join_returns_internal_error_without_exposing_database_details(monkeypatch):
    database = FakeDatabase()
    database.fail = True
    install_fake_database(monkeypatch, database)
    app = create_app()

    response = app.test_client().post(
        "/api/sessions/K7P2X/join", json={"name": "Ana"}
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "ok": False,
        "data": None,
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "Não foi possível concluir a operação. Tente novamente.",
        },
    }
