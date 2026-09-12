from backend import create_app


def test_frontend_index_is_served_by_flask():
    app = create_app()
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"HACKTUDO 2026" in response.data
