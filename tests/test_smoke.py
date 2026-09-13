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
