"""Ponto de entrada local da aplicação."""

from backend import create_app

app = create_app()


if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False))
