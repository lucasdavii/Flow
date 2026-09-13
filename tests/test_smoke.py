from backend import create_app


def test_frontend_index_is_served_by_flask():
    app = create_app()
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    # Confirma que o Flask entrega a tela atual do Flow, sem acoplar o teste
    # a textos do layout anterior.
    assert b"FLOW \xe2\x80\x94 Aprender no ritmo certo" in response.data
    assert b'id="flowApp"' in response.data


def test_frontend_serves_mvp_api_modules():
    """Evita publicar a tela principal sem os scripts que chamam o Flask."""
    client = create_app().test_client()

    index = client.get("/")
    assert b'assets/js/api.js' in index.data
    assert b'assets/js/mvp.js' in index.data

    assert client.get("/assets/js/api.js").status_code == 200
    mvp = client.get("/assets/js/mvp.js")
    assert mvp.status_code == 200
    assert b"FlowAPI.createSession" in mvp.data
    assert b"FlowAPI.joinSession" in mvp.data
    assert b"renderGroupMembers" in mvp.data
    assert b"renderTeacherActivity" in mvp.data
    assert b"stopStudentUpdates" in mvp.data
