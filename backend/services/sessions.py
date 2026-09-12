"""Regras de negócio para criação e gerenciamento de sessões."""

import hashlib
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any

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


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"O campo {field_name} é obrigatório.")
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
        if stage_type not in VALID_STAGE_TYPES:
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
        if role_type not in VALID_ROLE_TYPES:
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


def join_session(code: Any, payload: Any, database: Any = None) -> dict[str, Any]:
    """Insere um aluno em uma sessão waiting conforme docs/api.md."""
    normalized_code = _normalize_session_code(code)
    if not isinstance(payload, dict):
        raise ValidationError("Envie um objeto JSON válido.")
    name = _required_text(payload.get("name"), "name")

    client = _get_database(database, JoinSessionError)
    session = _find_waiting_session(client, normalized_code)
    roles = _load_roles(client, session["id"])
    participant_count = _count_participants(client, session["id"])

    # Grupos são preenchidos sequencialmente. A posição dentro do grupo escolhe
    # uma função complementar de forma previsível, sem criar tabela de groups.
    group_number = participant_count // session["group_size"] + 1
    position_in_group = participant_count % session["group_size"]
    role = roles[position_in_group % len(roles)]

    participant_token = secrets.token_urlsafe(32)
    try:
        response = (
            client.table("participants")
            .insert(
                {
                    "session_id": session["id"],
                    "role_id": role["id"],
                    "name": name,
                    "group_number": group_number,
                    # O token bruto volta ao aluno uma vez; um vazamento do
                    # banco não deve permitir reutilizar a credencial original.
                    "participant_token_hash": _hash_token(participant_token),
                }
            )
            .execute()
        )
    except Exception as error:
        raise JoinSessionError from error

    if not response.data:
        raise JoinSessionError
    participant = response.data[0]

    return {
        "participant": {
            "id": participant["id"],
            "name": participant["name"],
            "group_number": participant["group_number"],
            "role": {
                "id": role["id"],
                "name": role["name"],
                "type": role["type"],
                "description": role["description"],
            },
        },
        "participant_token": participant_token,
        "session_status": session["status"],
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
            .eq("participant_token_hash", _hash_token(participant_token))
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
        response = (
            client.table("sessions")
            .select("id,code,status,teacher_token_hash")
            .eq("code", normalized_code)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise SessionNotFoundError
        session = response.data[0]
        if not secrets.compare_digest(
            session["teacher_token_hash"], _hash_token(teacher_token.strip())
        ):
            raise InvalidTeacherTokenError
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
