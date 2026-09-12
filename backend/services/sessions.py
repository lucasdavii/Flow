"""Regras de negócio para criação e gerenciamento de sessões."""

import hashlib
import logging
import secrets
from typing import Any

from backend.db import get_supabase

SESSION_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
SESSION_CODE_LENGTH = 5
MAX_CODE_ATTEMPTS = 10
VALID_STAGE_TYPES = {"digital", "presential", "conclusion"}
VALID_ROLE_TYPES = {"digital", "presential"}


class ValidationError(ValueError):
    """Indica que o corpo enviado não segue o contrato."""


class SessionCreationError(RuntimeError):
    """Indica que não foi possível persistir uma sessão completa."""


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"O campo {field_name} é obrigatório.")
    return value.strip()


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

    raise SessionCreationError


def _remove_incomplete_session(database: Any, session_id: str) -> None:
    try:
        database.table("sessions").delete().eq("id", session_id).execute()
    except Exception:
        logging.exception("Falha ao remover sessão incompleta %s.", session_id)


def create_session(payload: Any, database: Any = None) -> dict[str, Any]:
    """Valida e persiste uma sessão completa conforme docs/api.md."""
    values = _validate_payload(payload)
    teacher_token = secrets.token_urlsafe(32)
    try:
        client = database or get_supabase()
    except Exception as error:
        raise SessionCreationError from error

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
