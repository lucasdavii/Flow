"""Aplicação Flask do projeto HACKTUDO 2026."""

from flask import Flask

from backend.config import Config


def create_app(config: type[Config] = Config) -> Flask:
    """Cria a aplicação sem abrir conexão com serviços externos."""
    app = Flask(
        __name__,
        static_folder="../frontend",
        static_url_path="",
    )
    app.config.from_object(config)

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    return app
