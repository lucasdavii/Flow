"""Rotas HTTP relacionadas a sessões."""

from flask import Blueprint, current_app, jsonify, request

from backend.services.sessions import (
    SessionCreationError,
    ValidationError,
    create_session,
)

sessions_blueprint = Blueprint("sessions", __name__)


def error_response(code: str, message: str, status_code: int):
    """Cria o envelope de erro definido no contrato da API."""
    return (
        jsonify(
            {
                "ok": False,
                "data": None,
                "error": {"code": code, "message": message},
            }
        ),
        status_code,
    )


@sessions_blueprint.post("/sessions")
def post_session():
    """Cria uma sessão, suas etapas e funções."""
    payload = request.get_json(silent=True)

    try:
        data = create_session(payload)
    except ValidationError as error:
        return error_response("VALIDATION_ERROR", str(error), 400)
    except SessionCreationError:
        current_app.logger.exception("Não foi possível criar a sessão.")
        return error_response(
            "SESSION_CODE_GENERATION_FAILED",
            "Não foi possível criar a sessão. Tente novamente.",
            500,
        )

    return jsonify({"ok": True, "data": data, "error": None}), 201
