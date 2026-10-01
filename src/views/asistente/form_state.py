"""Estado de sesión del formulario (módulo liviano, sin importar formulario.py)."""

from __future__ import annotations

import streamlit as st


def form_field_key(field: str, edit_id: str | None = None) -> str:
    return f"{field}_{edit_id or 'new'}"


def limpiar_ubicacion_formulario_nuevo() -> None:
    """Defaults Ministerio / Corrientes al abrir un formulario nuevo (no «mismo establecimiento»)."""
    st.session_state.pop("form_preset_ubicacion", None)
    st.session_state.pop("form_apply_ubicacion_preset", None)
    for field in ("rep", "loc", "est", "prev_loc", "est_na"):
        st.session_state.pop(form_field_key(field), None)
