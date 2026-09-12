"""Regras de negócio para criação e gerenciamento de sessões."""

import hashlib
import logging
import re
import secrets
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from backend.db import get_supabase

SESSION_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
SESSION_CODE_LENGTH = 5
MAX_CODE_ATTEMPTS = 10
VALID_STAGE_TYPES = {"digital", "presential", "conclusion"}
VALID_ROLE_TYPES = {"digital", "presential"}
SESSION_CODE_PATTERN = re.compile(
    rf"^[{SESSION_CODE_ALPHABET}]{{{SESSION_CODE_LENGTH}}}$"
)


class ValidationError(ValueError):
    """Indica que o corpo enviado não segue o contrato."""


class SessionCreationError(RuntimeError):
    """Indica que não foi possível persistir uma sessão completa."""


class SessionCodeGenerationError(SessionCreationError):
    """Indica que todas as tentativas de gerar código único falharam."""


class JoinSessionError(RuntimeError):
    """Indica uma falha inesperada ao inserir um participante."""


class SessionNotFoundError(LookupError):
    """Indica que o código informado não pertence a uma sessão."""


class SessionAlreadyStartedError(RuntimeError):
    """Indica que a entrada ocorreu depois do estado waiting."""


class SessionStateError(RuntimeError):
    """Indica uma falha inesperada ao consultar o estado da sessão."""


class ParticipantTokenRequiredError(PermissionError):
    """Indica que a consulta não recebeu a credencial do participante."""


class InvalidParticipantTokenError(PermissionError):
    """Indica que a credencial não pertence a um aluno da sessão."""


class TeacherTokenRequiredError(PermissionError):
    """Indica que a operação não recebeu a credencial do professor."""


class InvalidTeacherTokenError(PermissionError):
    """Indica que a credencial não pertence ao professor da sessão."""


class SessionHasNoParticipantsError(RuntimeError):
    """Indica que a sessão ainda não tem alunos para iniciar."""


class SessionStartError(RuntimeError):
    """Indica uma falha inesperada ao iniciar a sessão."""


class SessionNotActiveError(RuntimeError):
    """Indica que a operação exige uma sessão ativa."""


class SessionAdvanceError(RuntimeError):
    """Indica uma falha inesperada ao avançar a sessão."""


class StageNotCurrentError(RuntimeError):
    """Indica uma conclusão referente a outra etapa."""


class RoleCompletionError(RuntimeError):
    """Indica uma falha inesperada ao registrar a conclusão da função."""


class SubmissionNotAllowedError(RuntimeError):
    """Indica um envio fora da etapa de conclusão."""


class SubmissionError(RuntimeError):
    """Indica uma falha inesperada ao gravar a conclusão do grupo."""


class SessionResultsError(RuntimeError):
    """Indica uma falha inesperada ao consultar os resultados."""


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"O campo {field_name} é obrigatório.")
    # PostgreSQL não aceita NUL e o transporte JSON exige UTF-8 válido.
    if "\x00" in value:
        raise ValidationError(f"O campo {field_name} contém caracteres inválidos.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValidationError(
            f"O campo {field_name} contém caracteres inválidos."
        ) from None
    return value.strip()


def _get_database(database: Any, error_type: type[RuntimeError]) -> Any:
    try:
        return database or get_supabase()
    except Exception as error:
        raise error_type from error


def _normalize_session_code(code: Any) -> str:
    if not isinstance(code, str):
        raise ValidationError("Informe um código de sessão válido.")

    # O código é case-insensitive para reduzir erros de digitação no celular.
    normalized_code = code.strip().upper()
    if not SESSION_CODE_PATTERN.fullmatch(normalized_code):
        raise ValidationError("Informe um código de sessão válido.")
    return normalized_code


def _validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("Envie um objeto JSON válido.")

    activity_title = _required_text(payload.get("activity_title"), "activity_title")
    group_size = payload.get("group_size")
    stages = payload.get("stages")
    roles = payload.get("roles")

    if isinstance(group_size, bool) or not isinstance(group_size, int):
        raise ValidationError("O campo group_size deve ser um número inteiro.")
    if not 2 <= group_size <= 8:
        raise ValidationError("O campo group_size deve estar entre 2 e 8.")
    if not isinstance(stages, list) or not stages:
        raise ValidationError("Informe pelo menos uma etapa em stages.")
    if not isinstance(roles, list) or not roles:
        raise ValidationError("Informe pelo menos uma função em roles.")

    normalized_stages = []
    positions = []
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            raise ValidationError(f"A etapa {index + 1} deve ser um objeto JSON.")

        position = stage.get("position")
        if isinstance(position, bool) or not isinstance(position, int):
            raise ValidationError("Toda etapa deve ter position inteiro.")

        stage_type = stage.get("type")
        if not isinstance(stage_type, str) or stage_type not in VALID_STAGE_TYPES:
            raise ValidationError(
                "O tipo da etapa deve ser digital, presential ou conclusion."
            )

        positions.append(position)
        normalized_stages.append(
            {
                "position": position,
                "title": _required_text(stage.get("title"), "stages[].title"),
                "type": stage_type,
                "instructions": _required_text(
                    stage.get("instructions"), "stages[].instructions"
                ),
            }
        )

    if sorted(positions) != list(range(1, len(stages) + 1)):
        raise ValidationError("As posições das etapas devem começar em 1 e não ter lacunas.")

    normalized_roles = []
    role_names = set()
    for index, role in enumerate(roles):
        if not isinstance(role, dict):
            raise ValidationError(f"A função {index + 1} deve ser um objeto JSON.")

        role_type = role.get("type")
        if not isinstance(role_type, str) or role_type not in VALID_ROLE_TYPES:
            raise ValidationError("O tipo da função deve ser digital ou presential.")

        name = _required_text(role.get("name"), "roles[].name")
        normalized_name = name.casefold()
        if normalized_name in role_names:
            raise ValidationError("Os nomes das funções não podem se repetir.")
        role_names.add(normalized_name)

        normalized_roles.append(
            {
                "name": name,
                "type": role_type,
                "description": _required_text(
                    role.get("description"), "roles[].description"
                ),
            }
        )

    return {
        "activity_title": activity_title,
        "group_size": group_size,
        "stages": normalized_stages,
        "roles": normalized_roles,
    }


def _generate_session_code() -> str:
    return "".join(
        secrets.choice(SESSION_CODE_ALPHABET) for _ in range(SESSION_CODE_LENGTH)
    )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _is_session_code_conflict(error: Exception) -> bool:
    error_code = str(getattr(error, "code", ""))
    error_text = str(error).lower()
    return error_code == "23505" and (
        "sessions_code_key" in error_text or "key (code)=" in error_text
    )


def _insert_session(database: Any, session_values: dict[str, Any]) -> dict[str, Any]:
    for _ in range(MAX_CODE_ATTEMPTS):
        values = {**session_values, "code": _generate_session_code()}
        try:
            response = database.table("sessions").insert(values).execute()
        except Exception as error:
            if _is_session_code_conflict(error):
                continue
            raise SessionCreationError from error

        if response.data:
            return response.data[0]
        raise SessionCreationError

    raise SessionCodeGenerationError


def _remove_incomplete_session(database: Any, session_id: str) -> None:
    try:
        database.table("sessions").delete().eq("id", session_id).execute()
    except Exception:
        logging.exception("Falha ao remover sessão incompleta %s.", session_id)


def create_session(payload: Any, database: Any = None) -> dict[str, Any]:
    """Valida e persiste uma sessão completa conforme docs/api.md."""
    values = _validate_payload(payload)
    teacher_token = secrets.token_urlsafe(32)
    client = _get_database(database, SessionCreationError)

    session = _insert_session(
        client,
        {
            "activity_title": values["activity_title"],
            "group_size": values["group_size"],
            "status": "waiting",
            "teacher_token_hash": _hash_token(teacher_token),
        },
    )

    session_id = session["id"]
    stages = [
        {**stage, "session_id": session_id} for stage in values["stages"]
    ]
    roles = [{**role, "session_id": session_id} for role in values["roles"]]

    try:
        client.table("stages").insert(stages).execute()
        client.table("roles").insert(roles).execute()
    except Exception as error:
        _remove_incomplete_session(client, session_id)
        raise SessionCreationError from error

    return {
        "session": {
            "id": session["id"],
            "code": session["code"],
            "activity_title": session["activity_title"],
            "status": session["status"],
            "current_stage": None,
            "participant_count": 0,
            "created_at": session["created_at"],
        },
        "teacher_token": teacher_token,
    }


def _find_waiting_session(database: Any, code: str) -> dict[str, Any]:
    try:
        response = (
            database.table("sessions")
            .select("id,status,group_size")
            .eq("code", code)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise JoinSessionError from error

    if not response.data:
        raise SessionNotFoundError

    session = response.data[0]
    if session["status"] != "waiting":
        raise SessionAlreadyStartedError
    return session


def _load_roles(database: Any, session_id: str) -> list[dict[str, Any]]:
    try:
        response = (
            database.table("roles")
            .select("id,name,type,description")
            .eq("session_id", session_id)
            .order("created_at")
            .order("id")
            .execute()
        )
    except Exception as error:
        raise JoinSessionError from error

    if not response.data:
        raise JoinSessionError
    return response.data


def _count_participants(database: Any, session_id: str) -> int:
    try:
        response = (
            database.table("participants")
            .select("id", count="exact")
            .eq("session_id", session_id)
            .execute()
        )
    except Exception as error:
        raise JoinSessionError from error

    return response.count if response.count is not None else len(response.data)


def _join_database_error_code(error: Exception) -> str | None:
    """Traduz somente os erros de negócio emitidos pela função transacional."""
    error_text = f"{getattr(error, 'message', '')} {error}".upper()
    for code in ("SESSION_NOT_FOUND", "SESSION_ALREADY_STARTED"):
        if code in error_text:
            return code
    return None


def join_session(code: Any, payload: Any, database: Any = None) -> dict[str, Any]:
    """Insere um aluno em uma sessão waiting conforme docs/api.md."""
    normalized_code = _normalize_session_code(code)
    if not isinstance(payload, dict):
        raise ValidationError("Envie um objeto JSON válido.")
    name = _required_text(payload.get("name"), "name")

    client = _get_database(database, JoinSessionError)
    participant_token = secrets.token_urlsafe(32)
    try:
        response = (
            # A função mantém leitura, distribuição de grupo e inserção na
            # mesma transação para impedir vagas duplicadas sob concorrência.
            client.rpc(
                "join_session_atomic",
                {
                    "p_session_code": normalized_code,
                    "p_name": name,
                    # O token bruto volta ao aluno uma vez; um vazamento do
                    # banco não deve permitir reutilizar a credencial original.
                    "p_token_hash": _hash_token(participant_token),
                },
            )
            .execute()
        )
    except Exception as error:
        error_code = _join_database_error_code(error)
        if error_code == "SESSION_NOT_FOUND":
            raise SessionNotFoundError from error
        if error_code == "SESSION_ALREADY_STARTED":
            raise SessionAlreadyStartedError from error
        raise JoinSessionError from error

    if not response.data:
        raise JoinSessionError
    result = response.data[0]

    return {
        "participant": {
            "id": result["participant_id"],
            "name": result["participant_name"],
            "group_number": result["group_number"],
            "role": {
                "id": result["role_id"],
                "name": result["role_name"],
                "type": result["role_type"],
                "description": result["role_description"],
            },
        },
        "participant_token": participant_token,
        "session_status": result["session_status"],
    }


def _load_session_state(database: Any, code: str) -> dict[str, Any]:
    try:
        response = (
            database.table("sessions")
            .select(
                "id,code,activity_title,status,"
                "current_stage:stages!sessions_current_stage_fk("
                "id,position,title,type,instructions)"
            )
            .eq("code", code)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise SessionStateError from error

    if not response.data:
        raise SessionNotFoundError
    return response.data[0]


def _load_authenticated_participant(
    database: Any, session_id: str, participant_token: str
) -> dict[str, Any]:
    try:
        token_hash = _hash_token(participant_token)
    except UnicodeEncodeError:
        raise InvalidParticipantTokenError from None
    try:
        response = (
            database.table("participants")
            .select(
                "id,name,group_number,"
                "role:roles!participants_role_id_fkey("
                "id,name,type,description)"
            )
            .eq("session_id", session_id)
            # A comparação acontece com o hash para que o token bruto nunca
            # seja armazenado nem usado como filtro visível no banco.
            .eq("participant_token_hash", token_hash)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise SessionStateError from error

    if not response.data:
        raise InvalidParticipantTokenError
    return response.data[0]


def _load_group_members(
    database: Any, session_id: str, group_number: int
) -> list[dict[str, Any]]:
    try:
        response = (
            database.table("participants")
            .select("id,name,role:roles!participants_role_id_fkey(name)")
            .eq("session_id", session_id)
            .eq("group_number", group_number)
            # A ordem estável evita que a lista fique mudando a cada polling.
            .order("created_at")
            .order("id")
            .execute()
        )
    except Exception as error:
        raise SessionStateError from error

    try:
        return [
            {
                "id": member["id"],
                "name": member["name"],
                "role_name": member["role"]["name"],
            }
            for member in response.data
        ]
    except (KeyError, TypeError) as error:
        raise SessionStateError from error


def _has_completed_stage(
    database: Any, participant_id: str, stage_id: str | None
) -> bool:
    if stage_id is None:
        return False

    try:
        response = (
            database.table("role_completions")
            .select("id")
            .eq("participant_id", participant_id)
            .eq("stage_id", stage_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise SessionStateError from error
    return bool(response.data)


def get_session_state(
    code: Any, participant_token: Any, database: Any = None
) -> dict[str, Any]:
    """Retorna a visão atual da sessão autorizada para um participante."""
    normalized_code = _normalize_session_code(code)
    if not isinstance(participant_token, str) or not participant_token.strip():
        raise ParticipantTokenRequiredError

    client = _get_database(database, SessionStateError)
    session = _load_session_state(client, normalized_code)
    participant = _load_authenticated_participant(
        client, session["id"], participant_token.strip()
    )

    current_stage = session.get("current_stage")
    role = participant.get("role")
    if role is None:
        raise SessionStateError

    members = _load_group_members(
        client, session["id"], participant["group_number"]
    )
    completed = _has_completed_stage(
        client,
        participant["id"],
        current_stage["id"] if current_stage else None,
    )

    return {
        "session": {
            "id": session["id"],
            "code": session["code"],
            "activity_title": session["activity_title"],
            "status": session["status"],
            "current_stage": current_stage,
        },
        "participant": {
            "id": participant["id"],
            "name": participant["name"],
            "group_number": participant["group_number"],
            "role": role,
            "current_stage_completed": completed,
        },
        "group": {
            "number": participant["group_number"],
            "members": members,
        },
    }


def start_session(
    code: Any, teacher_token: Any, database: Any = None
) -> dict[str, Any]:
    """Autoriza o professor e inicia uma sessão waiting com alunos."""
    normalized_code = _normalize_session_code(code)
    if not isinstance(teacher_token, str) or not teacher_token.strip():
        raise TeacherTokenRequiredError

    client = _get_database(database, SessionStartError)
    try:
        session = _load_teacher_session(client, normalized_code, teacher_token.strip())
        if session["status"] != "waiting":
            raise SessionAlreadyStartedError

        participants = (
            client.table("participants")
            .select("id")
            .eq("session_id", session["id"])
            .limit(1)
            .execute()
        )
        if not participants.data:
            raise SessionHasNoParticipantsError

        stages = (
            client.table("stages")
            .select("id,position,title,type,instructions")
            .eq("session_id", session["id"])
            .eq("position", 1)
            .limit(1)
            .execute()
        )
        if not stages.data:
            raise SessionStartError
        stage = stages.data[0]

        # Somente uma chamada pode iniciar; as demais não devem reiniciar
        # uma sessão que já esteja em andamento.
        updated = (
            client.table("sessions")
            .update({
                "status": "active",
                "current_stage_id": stage["id"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", session["id"])
            .eq("status", "waiting")
            .execute()
        )
        if not updated.data:
            raise SessionAlreadyStartedError
    except (
        SessionNotFoundError,
        InvalidTeacherTokenError,
        SessionAlreadyStartedError,
        SessionHasNoParticipantsError,
        SessionStartError,
    ):
        raise
    except Exception as error:
        raise SessionStartError from error

    return {
        "session": {
            "id": session["id"],
            "code": session["code"],
            "status": "active",
            "current_stage": {
                field: stage[field]
                for field in ("id", "position", "title", "type", "instructions")
            },
        }
    }


def _load_teacher_session(
    database: Any, code: str, teacher_token: str
) -> dict[str, Any]:
    try:
        token_hash = _hash_token(teacher_token)
    except UnicodeEncodeError:
        raise InvalidTeacherTokenError from None
    response = (
        database.table("sessions")
        .select("id,code,activity_title,status,current_stage_id,teacher_token_hash")
        .eq("code", code)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise SessionNotFoundError
    session = response.data[0]
    if not secrets.compare_digest(
        session["teacher_token_hash"], token_hash
    ):
        raise InvalidTeacherTokenError
    return session


def _load_stage(database: Any, session_id: str, stage_id: str) -> dict[str, Any]:
    response = (
        database.table("stages")
        .select("id,position,title,type,instructions")
        .eq("session_id", session_id)
        .eq("id", stage_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise SessionAdvanceError
    return response.data[0]


def advance_session(
    code: Any, teacher_token: Any, database: Any = None
) -> dict[str, Any]:
    """Avança uma etapa ativa ou finaliza a sessão depois da última."""
    normalized_code = _normalize_session_code(code)
    if not isinstance(teacher_token, str) or not teacher_token.strip():
        raise TeacherTokenRequiredError

    client = _get_database(database, SessionAdvanceError)
    try:
        session = _load_teacher_session(client, normalized_code, teacher_token.strip())
        if session["status"] != "active":
            raise SessionNotActiveError
        if session["current_stage_id"] is None:
            raise SessionAdvanceError
        current_stage = _load_stage(client, session["id"], session["current_stage_id"])
        stages = (
            client.table("stages")
            .select("id,position,title,type,instructions")
            .eq("session_id", session["id"])
            .eq("position", current_stage["position"] + 1)
            .limit(1)
            .execute()
        )
        next_stage = stages.data[0] if stages.data else None
        status = "active" if next_stage else "finished"
        updated = (
            client.table("sessions")
            .update({
                "status": status,
                "current_stage_id": next_stage["id"] if next_stage else None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", session["id"])
            .eq("status", "active")
            .eq("current_stage_id", current_stage["id"])
            .execute()
        )
        if not updated.data:
            # Outra chamada já avançou esta etapa. Devolve o estado persistido
            # sem repetir a escrita, que poderia pular uma etapa.
            session = _load_teacher_session(
                client, normalized_code, teacher_token.strip()
            )
            status = session["status"]
            if status == "active" and session["current_stage_id"] is not None:
                next_stage = _load_stage(
                    client, session["id"], session["current_stage_id"]
                )
            elif status == "finished":
                next_stage = None
            else:
                raise SessionAdvanceError

        return {
            "session": {
                "id": session["id"],
                "code": session["code"],
                "status": status,
                "current_stage": next_stage,
            }
        }
    except (
        SessionNotFoundError,
        InvalidTeacherTokenError,
        SessionNotActiveError,
        SessionAdvanceError,
    ):
        raise
    except Exception as error:
        raise SessionAdvanceError from error


def _active_participant(
    database: Any, code: str, participant_token: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    session = _load_session_state(database, code)
    participant = _load_authenticated_participant(
        database, session["id"], participant_token
    )
    if session["status"] != "active":
        raise SessionNotActiveError
    if session["current_stage"] is None:
        raise SessionStateError
    return session, participant


def _completion_database_error_code(error: Exception) -> str | None:
    """Reconhece apenas conflitos previstos pelo contrato de complete-role."""
    error_text = f"{getattr(error, 'message', '')} {error}".upper()
    expected_codes = (
        "SESSION_NOT_FOUND",
        "INVALID_PARTICIPANT_TOKEN",
        "SESSION_NOT_ACTIVE",
        "STAGE_NOT_CURRENT",
    )
    return next((code for code in expected_codes if code in error_text), None)


def complete_role(
    code: Any, participant_token: Any, payload: Any, database: Any = None
) -> dict[str, Any]:
    """Registra uma única conclusão por aluno e etapa ativa."""
    normalized_code = _normalize_session_code(code)
    if not isinstance(payload, dict):
        raise ValidationError("Envie um objeto JSON válido.")
    stage_value = _required_text(payload.get("stage_id"), "stage_id")
    try:
        stage_id = str(UUID(stage_value))
    except ValueError as error:
        raise ValidationError("O campo stage_id deve ser um UUID válido.") from error
    if not isinstance(participant_token, str) or not participant_token.strip():
        raise ParticipantTokenRequiredError

    try:
        token_hash = _hash_token(participant_token.strip())
    except UnicodeEncodeError:
        raise InvalidParticipantTokenError from None

    client = _get_database(database, RoleCompletionError)
    try:
        response = (
            # A função bloqueia a sessão até validar e gravar, impedindo que
            # uma troca de etapa aconteça entre essas duas ações.
            client.rpc(
                "complete_role_atomic",
                {
                    "p_session_code": normalized_code,
                    "p_participant_token_hash": token_hash,
                    "p_stage_id": stage_id,
                },
            )
            .execute()
        )
        if not response.data:
            raise RoleCompletionError
        completion = response.data[0]
        return {"completion": {
            field: completion[field]
            for field in ("participant_id", "stage_id", "completed_at")
        }}
    except Exception as error:
        if isinstance(error, RoleCompletionError):
            raise
        error_code = _completion_database_error_code(error)
        if error_code == "SESSION_NOT_FOUND":
            raise SessionNotFoundError from error
        if error_code == "INVALID_PARTICIPANT_TOKEN":
            raise InvalidParticipantTokenError from error
        if error_code == "SESSION_NOT_ACTIVE":
            raise SessionNotActiveError from error
        if error_code == "STAGE_NOT_CURRENT":
            raise StageNotCurrentError from error
        raise RoleCompletionError from error


def submit_conclusion(
    code: Any, participant_token: Any, payload: Any, database: Any = None
) -> dict[str, Any]:
    """Envia ou atualiza a conclusão do grupo identificado pelo token."""
    normalized_code = _normalize_session_code(code)
    if not isinstance(payload, dict):
        raise ValidationError("Envie um objeto JSON válido.")
    content = _required_text(payload.get("content"), "content")
    if not isinstance(participant_token, str) or not participant_token.strip():
        raise ParticipantTokenRequiredError

    client = _get_database(database, SubmissionError)
    try:
        session, participant = _active_participant(
            client, normalized_code, participant_token.strip()
        )
        if session["current_stage"]["type"] != "conclusion":
            raise SubmissionNotAllowedError
        response = (
            client.table("submissions")
            .upsert(
                {
                    "session_id": session["id"],
                    "group_number": participant["group_number"],
                    "submitted_by": participant["id"],
                    "content": content,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="session_id,group_number",
            )
            .execute()
        )
        if not response.data:
            raise SubmissionError
        submission = response.data[0]
        return {"submission": {
            field: submission[field]
            for field in (
                "id", "group_number", "content", "submitted_by",
                "created_at", "updated_at",
            )
        }}
    except (
        SessionNotFoundError, InvalidParticipantTokenError,
        SessionNotActiveError, SubmissionNotAllowedError, SubmissionError,
    ):
        raise
    except Exception as error:
        raise SubmissionError from error


def _fetch_all(query_factory: Any) -> list[dict[str, Any]]:
    """Percorre páginas ordenadas, inclusive com limites menores no servidor."""
    rows = []
    while True:
        page = query_factory().range(len(rows), len(rows) + 499).execute().data
        if not page:
            return rows
        rows.extend(page)


def get_session_results(
    code: Any, teacher_token: Any, database: Any = None
) -> dict[str, Any]:
    """Agrupa alunos, progresso e conclusões para o professor da sessão."""
    normalized_code = _normalize_session_code(code)
    if not isinstance(teacher_token, str) or not teacher_token.strip():
        raise TeacherTokenRequiredError
    client = _get_database(database, SessionResultsError)
    try:
        session = _load_teacher_session(client, normalized_code, teacher_token.strip())
        participants = _fetch_all(lambda: (
            client.table("participants")
            .select("id,name,group_number,role:roles!participants_role_id_fkey(name)")
            .eq("session_id", session["id"])
            .order("group_number").order("created_at").order("id")
        ))
        completed_counts = Counter()
        # Lotes limitam o tamanho da URL e evitam uma consulta por aluno.
        participant_ids = [participant["id"] for participant in participants]
        for offset in range(0, len(participant_ids), 100):
            batch = participant_ids[offset:offset + 100]
            completions = _fetch_all(lambda: (
                client.table("role_completions")
                .select("participant_id,stage_id")
                .in_("participant_id", batch)
                .order("id")
            ))
            completed_counts.update(row["participant_id"] for row in completions)
        submissions = _fetch_all(lambda: (
            client.table("submissions")
            .select("id,group_number,content,submitted_by,updated_at")
            .eq("session_id", session["id"])
            .order("group_number")
        ))
        submissions_by_group = {
            row["group_number"]: {
                field: row[field]
                for field in ("id", "content", "submitted_by", "updated_at")
            }
            for row in submissions
        }
        groups = {}
        for participant in participants:
            number = participant["group_number"]
            group = groups.setdefault(number, {
                "number": number, "members": [],
                "submission": submissions_by_group.get(number),
            })
            group["members"].append({
                "id": participant["id"],
                "name": participant["name"],
                "role_name": participant["role"]["name"],
                "completed_stage_count": completed_counts[participant["id"]],
            })
        return {
            "session": {
                field: session[field]
                for field in ("id", "code", "activity_title", "status")
            },
            "groups": [groups[number] for number in sorted(groups)],
        }
    except (SessionNotFoundError, InvalidTeacherTokenError, SessionResultsError):
        raise
    except Exception as error:
        raise SessionResultsError from error
