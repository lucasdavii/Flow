"""Rotas HTTP relacionadas a sessões."""

from flask import Blueprint, current_app, jsonify, request

from backend.services.sessions import (
    JoinSessionError,
    SessionAlreadyStartedError,
    SessionCodeGenerationError,
    SessionCreationError,
    SessionNotFoundError,
    ValidationError,
    create_session,
    join_session,
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


def internal_error_response():
    """Oculta detalhes técnicos e oferece ao frontend um erro previsível."""
    # O motivo real fica apenas no log do servidor para não revelar banco,
    # credenciais ou estrutura interna nas respostas enviadas ao navegador.
    return error_response(
        "INTERNAL_ERROR",
        "Não foi possível concluir a operação. Tente novamente.",
        500,
    )


@sessions_blueprint.post("/sessions")
def post_session():
    """Cria uma sessão, suas etapas e funções."""
    payload = request.get_json(silent=True)

    try:
        data = create_session(payload)
    except ValidationError as error:
        return error_response("VALIDATION_ERROR", str(error), 400)
    except SessionCodeGenerationError:
        current_app.logger.exception("Não foi possível gerar um código único.")
        return error_response(
            "SESSION_CODE_GENERATION_FAILED",
            "Não foi possível criar a sessão. Tente novamente.",
            500,
        )
    except SessionCreationError:
        current_app.logger.exception("Não foi possível criar a sessão.")
        return internal_error_response()

    return jsonify({"ok": True, "data": data, "error": None}), 201


@sessions_blueprint.post("/sessions/<string:code>/join")
def post_session_join(code: str):
    """Insere um aluno e devolve sua atribuição e token individual."""
    payload = request.get_json(silent=True)

    try:
        data = join_session(code, payload)
    except ValidationError as error:
        return error_response("VALIDATION_ERROR", str(error), 400)
    except SessionNotFoundError:
        return error_response(
            "SESSION_NOT_FOUND", "Sessão não encontrada.", 404
        )
    except SessionAlreadyStartedError:
        return error_response(
            "SESSION_ALREADY_STARTED",
            "Esta sessão já foi iniciada e não aceita novos participantes.",
            409,
        )
    except JoinSessionError:
        current_app.logger.exception("Não foi possível inserir o participante.")
        return internal_error_response()

    return jsonify({"ok": True, "data": data, "error": None}), 201
