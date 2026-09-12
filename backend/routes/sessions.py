"""Rotas HTTP relacionadas a sessões."""

from flask import Blueprint, current_app, jsonify, request

from backend.services.sessions import (
    InvalidParticipantTokenError,
    InvalidTeacherTokenError,
    JoinSessionError,
    ParticipantTokenRequiredError,
    SessionAlreadyStartedError,
    SessionCodeGenerationError,
    SessionCreationError,
    SessionHasNoParticipantsError,
    SessionNotFoundError,
    SessionStateError,
    SessionStartError,
    TeacherTokenRequiredError,
    ValidationError,
    create_session,
    get_session_state,
    join_session,
    start_session,
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


@sessions_blueprint.get("/sessions/<string:code>/state")
def get_session_state_route(code: str):
    """Entrega ao aluno somente o estado associado ao seu token."""
    # O token fica no cabeçalho para não aparecer em URL, histórico ou logs.
    participant_token = request.headers.get("X-Participant-Token")

    try:
        data = get_session_state(code, participant_token)
    except ParticipantTokenRequiredError:
        return error_response(
            "PARTICIPANT_TOKEN_REQUIRED",
            "Informe o token do participante.",
            401,
        )
    except InvalidParticipantTokenError:
        return error_response(
            "INVALID_PARTICIPANT_TOKEN",
            "Token do participante inválido.",
            401,
        )
    except (SessionNotFoundError, ValidationError):
        # Para esta consulta, um código malformado também não identifica uma
        # sessão e segue o único erro 404 previsto no contrato.
        return error_response(
            "SESSION_NOT_FOUND", "Sessão não encontrada.", 404
        )
    except SessionStateError:
        current_app.logger.exception("Não foi possível consultar a sessão.")
        return internal_error_response()

    return jsonify({"ok": True, "data": data, "error": None}), 200


@sessions_blueprint.post("/sessions/<string:code>/start")
def post_session_start(code: str):
    """Inicia a primeira etapa mediante autorização do professor."""
    try:
        data = start_session(code, request.headers.get("X-Teacher-Token"))
    except TeacherTokenRequiredError:
        return error_response(
            "TEACHER_TOKEN_REQUIRED", "Informe o token do professor.", 401
        )
    except InvalidTeacherTokenError:
        return error_response(
            "INVALID_TEACHER_TOKEN", "Token do professor inválido.", 401
        )
    except (SessionNotFoundError, ValidationError):
        return error_response("SESSION_NOT_FOUND", "Sessão não encontrada.", 404)
    except SessionAlreadyStartedError:
        return error_response(
            "SESSION_ALREADY_STARTED", "Esta sessão já foi iniciada.", 409
        )
    except SessionHasNoParticipantsError:
        return error_response(
            "SESSION_HAS_NO_PARTICIPANTS",
            "Aguarde a entrada de pelo menos um participante para iniciar.",
            409,
        )
    except SessionStartError:
        current_app.logger.exception("Não foi possível iniciar a sessão.")
        return internal_error_response()

    return jsonify({"ok": True, "data": data, "error": None}), 200
