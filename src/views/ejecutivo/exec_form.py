"""Navegación del formulario en vista ejecutiva."""

from __future__ import annotations

import streamlit as st

TAB_LISTA = "Compromisos"
TAB_AGENDA = "Agenda"


def exec_form_active() -> bool:
    return bool(st.session_state.get("exec_form_mode"))


def get_exec_edit_id() -> str | None:
    if st.session_state.get("exec_form_mode") == "edit":
        return st.session_state.get("exec_form_edit_id")
    return None


def open_exec_form_new(*, return_to: str, solo_agenda: bool = False) -> None:
    st.session_state.exec_form_mode = "new"
    st.session_state.exec_form_edit_id = None
    st.session_state.exec_form_return = return_to
    st.session_state.exec_form_return_id = None
    st.session_state.exec_selected_id = None
    st.session_state.pop("exec_pending_delete_id", None)
    st.session_state.pop("exec_pending_delete_titulo", None)
    if solo_agenda:
        st.session_state.form_solo_agenda = True
    else:
        st.session_state.pop("form_solo_agenda", None)


def open_exec_form_edit(compromiso_id: str, *, return_to: str = "detalle") -> None:
    st.session_state.exec_form_mode = "edit"
    st.session_state.exec_form_edit_id = compromiso_id
    st.session_state.exec_form_return = return_to
    st.session_state.exec_form_return_id = compromiso_id if return_to == "detalle" else None
    st.session_state.exec_selected_id = None
    st.session_state.pop("exec_pending_delete_id", None)
    st.session_state.pop("exec_pending_delete_titulo", None)


def open_exec_detalle(compromiso_id: str, *, origen: str = "lista") -> None:
    st.session_state.exec_selected_id = compromiso_id
    st.session_state.exec_detail_from = origen
    st.session_state.pop("exec_form_mode", None)
    st.session_state.pop("exec_pending_delete_id", None)
    st.session_state.pop("exec_pending_delete_titulo", None)
