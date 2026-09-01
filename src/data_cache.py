"""Cache de lecturas Supabase para reducir parpadeo en reruns de Streamlit."""

from __future__ import annotations

import streamlit as st

PANEL_TTL = 60
CATALOGOS_TTL = 300
SUBCATEGORIAS_TTL = 300


def user_cache_key() -> str:
    return str(st.session_state.get("user_id") or "anon")


def invalidate_data_cache() -> None:
    fetch_panel_cached.clear()
    load_catalogos_cached.clear()
    fetch_subcategorias_cached.clear()


@st.cache_data(ttl=PANEL_TTL, show_spinner=False)
def fetch_panel_cached(incluir_inactivos: bool, user_key: str):
    from src.services.compromisos import _fetch_panel_impl
    from src.supabase_client import get_client

    return _fetch_panel_impl(get_client(), incluir_inactivos)


@st.cache_data(ttl=CATALOGOS_TTL, show_spinner=False)
def load_catalogos_cached(user_key: str) -> dict[str, list[dict]]:
    from src.services.catalogos import _load_catalogos_impl
    from src.supabase_client import get_client

    return _load_catalogos_impl(get_client())


@st.cache_data(ttl=SUBCATEGORIAS_TTL, show_spinner=False)
def fetch_subcategorias_cached(categoria_id: str | None, user_key: str) -> list[dict]:
    from src.services.catalogos import _fetch_subcategorias_impl
    from src.supabase_client import get_client

    return _fetch_subcategorias_impl(get_client(), categoria_id)
