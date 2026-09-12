from copy import deepcopy

import pytest

from tests.session_database import (
    PARTICIPANT_ID, SESSION_ID, STAGE_ID, TEACHER_TOKEN, environment,
)


def results(client, token=TEACHER_TOKEN, code="K7P2X"):
    return client.get(f"/api/sessions/{code}/results",
                      headers={} if token is None else {"X-Teacher-Token": token})


@pytest.fixture
def results_environment(environment):
    client, state = environment
    participant = state["rows"]["participants"][0]
    state["rows"]["participants"] += [
        {**participant, "id": "second", "name": "Bruno", "group_number": 2},
        {**participant, "id": "peer", "name": "Carla"},
        {**participant, "id": "foreign", "session_id": "other-session"},
    ]
    state["rows"]["role_completions"] = [
        {"id": "c1", "participant_id": PARTICIPANT_ID, "stage_id": STAGE_ID},
        {"id": "c2", "participant_id": PARTICIPANT_ID, "stage_id": "second-stage"},
        {"id": "c3", "participant_id": "peer", "stage_id": STAGE_ID},
        {"id": "c4", "participant_id": "foreign", "stage_id": STAGE_ID},
    ]
    state["rows"]["submissions"] = [{
        "id": "s1", "session_id": SESSION_ID, "group_number": 1,
        "content": "Conclusão", "submitted_by": PARTICIPANT_ID,
        "updated_at": "2026-09-12T12:00:00Z",
    }, {
        "id": "foreign-submission", "session_id": "other-session", "group_number": 2,
        "content": "Privado", "submitted_by": "foreign",
        "updated_at": "2026-09-12T12:00:00Z",
    }]
    return client, state


@pytest.mark.parametrize("status", ["waiting", "active", "finished"])
def test_results_return_contract_in_every_session_status(results_environment, status):
    client, state = results_environment
    state["rows"]["sessions"][0]["status"] = status
    before = deepcopy(state["rows"])
    response = results(client, code="k7p2x")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True, "error": None,
        "data": {
            "session": {"id": SESSION_ID, "code": "K7P2X",
                        "activity_title": "Uso consciente da água", "status": status},
            "groups": [{
                "number": 1,
                "members": [
                    {"id": PARTICIPANT_ID, "name": "Ana Souza", "role_name": "pesquisador",
                     "completed_stage_count": 2},
                    {"id": "peer", "name": "Carla", "role_name": "pesquisador",
                     "completed_stage_count": 1},
                ],
                "submission": {"id": "s1", "content": "Conclusão",
                               "submitted_by": PARTICIPANT_ID,
                               "updated_at": "2026-09-12T12:00:00Z"},
            }, {
                "number": 2,
                "members": [{"id": "second", "name": "Bruno", "role_name": "pesquisador",
                             "completed_stage_count": 0}],
                "submission": None,
            }],
        },
    }
    assert state["rows"] == before
    assert all(req.method == "GET" for req in state["requests"])


def test_results_without_participants(environment):
    client, state = environment
    state["rows"]["participants"] = []
    response = results(client)
    assert response.status_code == 200
    assert response.get_json()["data"]["groups"] == []


def test_results_follow_small_server_pages_without_losing_records(results_environment):
    client, state = results_environment
    expected = results(client).get_json()
    state["page_cap"] = 1
    assert results(client).get_json() == expected


def test_results_query_completions_in_bounded_batches(environment):
    client, state = environment
    prototype = state["rows"]["participants"][0]
    state["rows"]["participants"] = [
        {**prototype, "id": f"student-{number:03d}"} for number in range(101)
    ]
    state["rows"]["role_completions"] = [
        {"id": "completion", "participant_id": "student-100", "stage_id": STAGE_ID}
    ]
    response = results(client)
    assert response.status_code == 200
    members = response.get_json()["data"]["groups"][0]["members"]
    assert len(members) == 101
    assert members[-1]["completed_stage_count"] == 1
    completion_requests = [req for req in state["requests"]
                           if req.url.path.endswith("/role_completions")]
    assert len(completion_requests) == 3  # empty batch + populated batch + end page


@pytest.mark.parametrize("token,error", [
    (None, "TEACHER_TOKEN_REQUIRED"), (" ", "TEACHER_TOKEN_REQUIRED"),
    ("invalid", "INVALID_TEACHER_TOKEN"),
])
def test_results_require_teacher_token(environment, token, error):
    client, state = environment
    response = results(client, token=token)
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == error
    assert len(state["requests"]) <= 1


@pytest.mark.parametrize("code", ["ZZZZZ", "invalid"])
def test_results_reject_unknown_or_invalid_session(environment, code):
    client, _ = environment
    response = results(client, code=code)
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.parametrize("table", ["sessions", "participants", "role_completions", "submissions"])
def test_results_hide_database_errors(environment, table):
    client, state = environment
    state["fail_at"] = ("GET", table)
    response = results(client)
    assert response.status_code == 500
    assert response.get_json()["error"]["code"] == "INTERNAL_ERROR"
