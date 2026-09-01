from functools import lru_cache

import streamlit as st
from supabase import Client, create_client


def normalize_supabase_url(url: str) -> str:
    """Quita /rest/v1 si el usuario lo pegó por error desde la doc de API."""
    url = url.strip().rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    return url.rstrip("/")


def get_supabase_config() -> tuple[str, str]:
    try:
        url = normalize_supabase_url(st.secrets["SUPABASE_URL"])
        key = st.secrets["SUPABASE_ANON_KEY"]
    except (KeyError, FileNotFoundError):
        url = st.session_state.get("_supabase_url", "")
        key = st.session_state.get("_supabase_key", "")
    if not url or not key:
        raise RuntimeError(
            "Configurá SUPABASE_URL y SUPABASE_ANON_KEY en .streamlit/secrets.toml"
        )
    return url, key


@lru_cache(maxsize=4)
def _cached_client(url: str, key: str, access_token: str | None) -> Client:
    client = create_client(url, key)
    if access_token:
        client.postgrest.auth(access_token)
    return client


def get_client(access_token: str | None = None) -> Client:
    url, key = get_supabase_config()
    token = access_token or st.session_state.get("access_token")
    return _cached_client(url, key, token or "")


def clear_client_cache() -> None:
    _cached_client.cache_clear()
