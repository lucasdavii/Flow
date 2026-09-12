"""Regressões de concorrência reproduzidas sem acessar banco real.

O transporte simulado exerce a RPC de entrada atômica e mantém os cenários
de operações sobrepostas ainda fora do escopo desta correção como xfail.
"""

from collections import Counter

import pytest

from tests.session_database import (
    PARTICIPANT_TOKEN, STAGE_ID, TEACHER_TOKEN, environment,
)


def test_concurrent_joins_respect_group_size(environment):
    client, state = environment
    state["rows"]["sessions"][0]["group_size"] = 2
    concurrent_responses = []

    def join_before_insert(request, state):
        if request.method == "POST" and request.url.path.endswith(
            "/rpc/join_session_atomic"
        ):
            state["before_request"] = None
            concurrent_responses.append(client.post(
                "/api/sessions/K7P2X/join", json={"name": "Aluno B"}
            ))

    state["before_request"] = join_before_insert
    response = client.post(
        "/api/sessions/K7P2X/join", json={"name": "Aluno A"}
    )

    assert response.status_code == concurrent_responses[0].status_code == 201
    group_counts = Counter(
        participant["group_number"] for participant in state["rows"]["participants"]
    )
    assert group_counts == {1: 2, 2: 1}


@pytest.mark.xfail(
    strict=True,
    reason="A entrada e o início precisam serializar o estado na mesma transação.",
)
def test_join_rejects_insert_after_concurrent_start(environment):
    client, state = environment

    def start_before_insert(request, state):
        if request.method == "POST" and request.url.path.endswith("/participants"):
            state["before_request"] = None
            response = client.post(
                "/api/sessions/K7P2X/start",
                headers={"X-Teacher-Token": TEACHER_TOKEN},
            )
            assert response.status_code == 200

    state["before_request"] = start_before_insert
    response = client.post(
        "/api/sessions/K7P2X/join", json={"name": "Aluno atrasado"}
    )

    assert state["rows"]["sessions"][0]["status"] == "active"
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "SESSION_ALREADY_STARTED"
    assert len(state["rows"]["participants"]) == 1


@pytest.mark.xfail(
    strict=True,
    reason="A validação da etapa e a conclusão precisam compartilhar transação.",
)
def test_completion_rejects_insert_after_concurrent_advance(environment):
    client, state = environment
    state["rows"]["sessions"][0].update(
        status="active", current_stage_id=STAGE_ID
    )

    def advance_before_insert(request, state):
        if request.method == "POST" and request.url.path.endswith("/role_completions"):
            state["before_request"] = None
            response = client.post(
                "/api/sessions/K7P2X/next",
                headers={"X-Teacher-Token": TEACHER_TOKEN},
            )
            assert response.status_code == 200

    state["before_request"] = advance_before_insert
    response = client.post(
        "/api/sessions/K7P2X/complete-role",
        json={"stage_id": STAGE_ID},
        headers={"X-Participant-Token": PARTICIPANT_TOKEN},
    )

    assert state["rows"]["sessions"][0]["current_stage_id"] == "second-stage"
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "STAGE_NOT_CURRENT"
    assert state["rows"]["role_completions"] == []


@pytest.mark.xfail(
    strict=True,
    reason="A validação do estado e a submissão precisam compartilhar transação.",
)
def test_submission_rejects_insert_after_concurrent_finish(environment):
    client, state = environment
    state["rows"]["sessions"][0].update(
        status="active", current_stage_id=STAGE_ID
    )
    state["rows"]["stages"] = [
        stage for stage in state["rows"]["stages"] if stage["id"] == STAGE_ID
    ]
    state["rows"]["stages"][0]["type"] = "conclusion"

    def finish_before_insert(request, state):
        if request.method == "POST" and request.url.path.endswith("/submissions"):
            state["before_request"] = None
            response = client.post(
                "/api/sessions/K7P2X/next",
                headers={"X-Teacher-Token": TEACHER_TOKEN},
            )
            assert response.status_code == 200

    state["before_request"] = finish_before_insert
    response = client.post(
        "/api/sessions/K7P2X/submissions",
        json={"content": "Conclusão tardia"},
        headers={"X-Participant-Token": PARTICIPANT_TOKEN},
    )

    assert state["rows"]["sessions"][0]["status"] == "finished"
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "SESSION_NOT_ACTIVE"
    assert state["rows"]["submissions"] == []
