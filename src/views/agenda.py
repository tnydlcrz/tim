from __future__ import annotations

from datetime import date, timedelta

import streamlit as st
from supabase import Client

from src.services import compromisos
from src.ui import format_fecha, render_agenda_event_row, rerun_app, row_text
from src.views.ejecutivo import exec_form

AGENDA_LIST_SCROLL_HEIGHT = 520


def _init_agenda_state() -> None:
    if "agenda_fecha" not in st.session_state:
        st.session_state.agenda_fecha = compromisos.hoy_ar()
    if "agenda_ver_todos" not in st.session_state:
        st.session_state.agenda_ver_todos = False


def _agenda_ver_dia() -> None:
    st.session_state.agenda_ver_todos = False


def _agenda_shift(delta: int) -> None:
    _agenda_ver_dia()
    base = st.session_state.get("agenda_fecha")
    if not isinstance(base, date):
        base = compromisos.hoy_ar()
    st.session_state.agenda_fecha = base + timedelta(days=delta)


def _agenda_ir_hoy() -> None:
    _agenda_ver_dia()
    st.session_state.agenda_fecha = compromisos.hoy_ar()


def _agenda_ver_todos() -> None:
    st.session_state.agenda_ver_todos = True


def _render_evento(row, i: int, modo: str, *, mostrar_fecha: bool = False) -> None:
    cols = st.columns([11, 1] if modo == "ejecutivo" else [10, 1])
    with cols[0]:
        render_agenda_event_row(
            titulo=row_text(row.get("titulo")),
            hora=row.get("hora_inicio"),
            ubicacion=row_text(row.get("ubicacion_display")),
            subcategoria=row_text(row.get("subcategoria")),
            prioridad=row_text(row.get("prioridad")),
            activo=bool(row.get("activo", True)),
            persona=row_text(row.get("persona_solicitante")),
            fecha=row.get("fecha_inicio") if mostrar_fecha else None,
        )
    with cols[1]:
        if modo == "ejecutivo":
            if st.button("Ver", key=f"agenda_ver_{row['id']}_{i}", use_container_width=True):
                exec_form.open_exec_detalle(row["id"], origen="agenda")
                rerun_app()
        else:
            if st.button("Editar", key=f"agenda_edit_{row['id']}_{i}", use_container_width=True):
                st.session_state.edit_compromiso_id = row["id"]
                st.session_state.form_solo_agenda = True
                st.session_state.form_return_to = "Agenda"
                st.session_state._nav_formulario = True
                rerun_app()


def _render_lista_filas(df, modo: str, *, mostrar_fecha: bool = False) -> None:
    for i, (_, row) in enumerate(df.iterrows()):
        _render_evento(row, i, modo, mostrar_fecha=mostrar_fecha)


def _render_lista_dia_scroll(
    eventos,
    sin_fecha,
    modo: str,
) -> None:
    with st.container(height=AGENDA_LIST_SCROLL_HEIGHT, border=True):
        if eventos.empty and sin_fecha.empty:
            st.info("No hay eventos programados para este día.")
            return

        if not eventos.empty:
            st.markdown(f"**Eventos del día ({len(eventos)})**")
            _render_lista_filas(eventos, modo)

        if not sin_fecha.empty:
            if not eventos.empty:
                st.markdown("---")
            st.markdown(f"**Sin fecha asignada ({len(sin_fecha)})**")
            st.caption("Estos eventos no aparecen en un día concreto hasta que se les asigne fecha.")
            _render_lista_filas(sin_fecha, modo, mostrar_fecha=True)


def _render_lista_todos_scroll(eventos, modo: str) -> None:
    with st.container(height=AGENDA_LIST_SCROLL_HEIGHT, border=True):
        if eventos.empty:
            st.info("No hay eventos de agenda registrados.")
            return
        _render_lista_filas(eventos, modo, mostrar_fecha=True)


@st.fragment
def _agenda_listas_fragment(
    ver_todos: bool,
    modo: str,
    eventos_todos,
    eventos_dia,
    sin_fecha,
) -> None:
    if ver_todos:
        _render_lista_todos_scroll(eventos_todos, modo)
    else:
        _render_lista_dia_scroll(eventos_dia, sin_fecha, modo)


def render_agenda(client: Client, modo: str = "asistente") -> None:
    _init_agenda_state()
    if modo == "asistente" and (msg := st.session_state.pop("_flash_msg", None)):
        st.success(msg)
    ver_todos = bool(st.session_state.agenda_ver_todos)
    dia: date = st.session_state.agenda_fecha
    incluir_cancelados = st.checkbox("Mostrar eventos cancelados", key="agenda_inactivos")

    if ver_todos:
        eventos_todos = compromisos.fetch_agenda_todos(client, incluir_inactivos=incluir_cancelados)
        eventos_dia = sin_fecha = None
        total = len(eventos_todos)
    else:
        eventos_todos = None
        eventos_dia = compromisos.fetch_agenda_dia(client, dia, incluir_inactivos=incluir_cancelados)
        sin_fecha = compromisos.fetch_agenda_sin_fecha(client, incluir_inactivos=incluir_cancelados)
        total = len(eventos_dia) + len(sin_fecha)

    st.subheader("Agenda — todos los eventos" if ver_todos else "Agenda del día")
    st.caption(
        "Eventos de la categoría Agenda. Desmarcá «Evento programado» al editar para cancelar. "
        "Zona horaria: Argentina."
    )

    c_prev, c_fecha, c_next, c_hoy, c_todos = st.columns([1, 2.5, 1, 1.25, 1.25])
    with c_prev:
        st.button(
            "◀ Día anterior",
            key="agenda_prev",
            use_container_width=True,
            on_click=_agenda_shift,
            kwargs={"delta": -1},
        )
    with c_fecha:
        st.date_input(
            "Fecha",
            format="DD/MM/YYYY",
            key="agenda_fecha",
            label_visibility="collapsed",
            on_change=_agenda_ver_dia,
            disabled=ver_todos,
        )
    with c_next:
        st.button(
            "Día siguiente ▶",
            key="agenda_next",
            use_container_width=True,
            on_click=_agenda_shift,
            kwargs={"delta": 1},
        )
    with c_hoy:
        st.button(
            "Hoy",
            key="agenda_hoy",
            use_container_width=True,
            on_click=_agenda_ir_hoy,
        )
    with c_todos:
        st.button(
            "Todos",
            key="agenda_todos",
            type="primary" if ver_todos else "secondary",
            use_container_width=True,
            on_click=_agenda_ver_todos,
        )

    count_label = "Todos los eventos · Argentina" if ver_todos else f"{format_fecha(dia)} · Argentina"

    tc1, tc2 = st.columns([4, 1])
    with tc1:
        if modo == "ejecutivo":
            st.caption("Usá **Ver** en un evento para editarlo o eliminarlo.")
    with tc2:
        if modo == "asistente":
            if st.button("+ Nuevo evento", type="primary", key="agenda_nuevo", use_container_width=True):
                st.session_state.edit_compromiso_id = None
                st.session_state.form_solo_agenda = True
                st.session_state.form_return_to = "Agenda"
                st.session_state._nav_formulario = True
                st.rerun()
        else:
            if st.button("+ Nuevo evento", type="primary", key="agenda_nuevo_exec", use_container_width=True):
                exec_form.open_exec_form_new(return_to="agenda", solo_agenda=True)
                st.rerun()

    st.markdown(
        f'<p class="exec-list-count">{count_label} · {total} evento(s)</p>',
        unsafe_allow_html=True,
    )

    _agenda_listas_fragment(ver_todos, modo, eventos_todos, eventos_dia, sin_fecha)
