"""Criação tardia do cliente Supabase usado apenas pelo backend."""

from flask import current_app
from supabase import Client, create_client


def get_supabase() -> Client:
    """Retorna um cliente usando credenciais do ambiente do servidor."""
    url = current_app.config.get("SUPABASE_URL")
    key = current_app.config.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise RuntimeError(
            "Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no arquivo .env."
        )

    return create_client(url, key)
