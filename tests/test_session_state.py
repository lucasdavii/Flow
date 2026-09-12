import hashlib

from backend import create_app


SESSION_ID = "cc9fa8ec-69a8-45a4-b32c-aeead18fe58d"
STAGE_ID = "d75df973-6948-44f2-91c6-53f30448eb1b"
PARTICIPANT_ID = "f5168159-a39a-4c93-aa57-4e65fbf61224"
ROLE_ID = "ef6beabb-03ab-455a-8f1c-77e63d8fcb12"
PARTICIPANT_TOKEN = "token-do-participante"


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
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

        rows = [
            row
            for row in self.database.rows[self.table_name]
            if all(row.get(field) == value for field, value in self.filters.items())
        ]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return FakeResult(rows)


class FakeTable:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name

    def select(self, _columns):
        return FakeQuery(self.database, self.table_name)


class FakeDatabase:
    def __init__(self, *, current_stage=True, completed=True):
        self.fail = False
        stage = (
            {
                "id": STAGE_ID,
                "position": 1,
                "title": "Pesquisa orientada",
                "type": "digital",
                "instructions": "Encontre duas fontes confiáveis.",
            }
            if current_stage
            else None
        )
        role = {
            "id": ROLE_ID,
            "name": "pesquisador",
            "type": "digital",
            "description": "Localiza informações.",
        }
        self.rows = {
            "sessions": [
                {
                    "id": SESSION_ID,
                    "code": "K7P2X",
                    "activity_title": "Uso consciente da água",
                    "status": "active" if current_stage else "waiting",
                    "current_stage": stage,
                }
            ],
            "participants": [
                {
                    "id": PARTICIPANT_ID,
                    "session_id": SESSION_ID,
                    "name": "Ana Souza",
                    "group_number": 1,
                    "participant_token_hash": hashlib.sha256(
                        PARTICIPANT_TOKEN.encode("utf-8")
                    ).hexdigest(),
                    "role": role,
                },
                {
                    "id": "0c75bad6-47c5-4a00-bd40-6f6f993bb74d",
                    "session_id": SESSION_ID,
                    "name": "Bruno Lima",
                    "group_number": 1,
                    "participant_token_hash": "outro-hash",
                    "role": {**role, "name": "relator"},
                },
            ],
            "role_completions": (
                [
                    {
                        "id": "a193f6e2-da9c-4843-8193-08ff2f7861d2",
                        "participant_id": PARTICIPANT_ID,
                        "stage_id": STAGE_ID,
                    }
                ]
                if completed and current_stage
                else []
            ),
        }

    def table(self, table_name):
        return FakeTable(self, table_name)


def install_fake_database(monkeypatch, database):
    monkeypatch.setattr(
        "backend.services.sessions.get_supabase", lambda: database
    )


def test_state_returns_current_session_participant_and_group(monkeypatch):
    database = FakeDatabase()
    install_fake_database(monkeypatch, database)
    response = create_app().test_client().get(
        "/api/sessions/k7p2x/state",
        headers={"X-Participant-Token": PARTICIPANT_TOKEN},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["error"] is None
    assert body["data"]["session"]["current_stage"]["id"] == STAGE_ID
    assert body["data"]["participant"] == {
        "id": PARTICIPANT_ID,
        "name": "Ana Souza",
        "group_number": 1,
        "role": {
            "id": ROLE_ID,
            "name": "pesquisador",
            "type": "digital",
            "description": "Localiza informações.",
        },
        "current_stage_completed": True,
    }
    assert body["data"]["group"] == {
        "number": 1,
        "members": [
            {
                "id": PARTICIPANT_ID,
                "name": "Ana Souza",
                "role_name": "pesquisador",
            },
            {
                "id": "0c75bad6-47c5-4a00-bd40-6f6f993bb74d",
                "name": "Bruno Lima",
                "role_name": "relator",
            },
        ],
    }


def test_state_without_current_stage_returns_null_and_not_completed(monkeypatch):
    database = FakeDatabase(current_stage=False)
    install_fake_database(monkeypatch, database)
    response = create_app().test_client().get(
        "/api/sessions/K7P2X/state",
        headers={"X-Participant-Token": PARTICIPANT_TOKEN},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["session"]["current_stage"] is None
    assert response.get_json()["data"]["participant"][
        "current_stage_completed"
    ] is False


def test_state_requires_participant_token():
    response = create_app().test_client().get("/api/sessions/K7P2X/state")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "PARTICIPANT_TOKEN_REQUIRED"


def test_state_rejects_invalid_participant_token(monkeypatch):
    database = FakeDatabase()
    install_fake_database(monkeypatch, database)
    response = create_app().test_client().get(
        "/api/sessions/K7P2X/state",
        headers={"X-Participant-Token": "token-incorreto"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "INVALID_PARTICIPANT_TOKEN"


def test_state_returns_not_found_for_unknown_session(monkeypatch):
    database = FakeDatabase()
    database.rows["sessions"] = []
    install_fake_database(monkeypatch, database)
    response = create_app().test_client().get(
        "/api/sessions/K7P2X/state",
        headers={"X-Participant-Token": PARTICIPANT_TOKEN},
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_state_returns_internal_error_without_database_details(monkeypatch):
    database = FakeDatabase()
    database.fail = True
    install_fake_database(monkeypatch, database)
    response = create_app().test_client().get(
        "/api/sessions/K7P2X/state",
        headers={"X-Participant-Token": PARTICIPANT_TOKEN},
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
