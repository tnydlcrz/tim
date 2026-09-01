import streamlit as st
from supabase import Client

from src.services import compromisos
from src.ui import render_compromiso_row_compact, rerun_app, row_text

ASIST_LIST_SCROLL_HEIGHT = 520


def _render_confirmacion_borrado(client: Client) -> None:
    pending_id = st.session_state.get("pending_delete_id")
    if not pending_id:
        return
    titulo = st.session_state.get("pending_delete_titulo", "")
    st.warning(f"¿Eliminar «{titulo}»? Esta acción no se puede deshacer.")
    c1, c2, _ = st.columns([1, 1, 4])
    with c1:
        if st.button("Sí, eliminar", type="primary", key="confirm_delete_yes", use_container_width=True):
            compromisos.delete_compromiso(client, pending_id)
            st.session_state.pop("pending_delete_id", None)
            st.session_state.pop("pending_delete_titulo", None)
            st.session_state._flash_msg = "Compromiso eliminado."
            st.rerun()
    with c2:
        if st.button("Cancelar", key="confirm_delete_no", use_container_width=True):
            st.session_state.pop("pending_delete_id", None)
            st.session_state.pop("pending_delete_titulo", None)
            st.rerun()


def _render_lista_filas(df) -> None:
    for i, (_, row) in enumerate(df.iterrows()):
        c1, c2, c3 = st.columns([10, 1, 1])
        with c1:
            estado = row.get("estado_display")
            if estado is None or (isinstance(estado, float) and estado != estado):
                estado = ""
            render_compromiso_row_compact(
                titulo=row_text(row.get("titulo")),
                ubicacion=row_text(row.get("ubicacion_display")),
                categoria=row_text(row.get("categoria")),
                subcategoria=row_text(row.get("subcategoria")),
                prioridad=row_text(row.get("prioridad")),
                avance_pct=int(row.get("avance_pct") or 0),
                estado=row_text(estado),
                activo=bool(row.get("activo", True)),
                fecha_inicio=row.get("fecha_inicio"),
            )
        with c2:
            if st.button("Editar", key=f"edit_{row['id']}_{i}", use_container_width=True):
                st.session_state.edit_compromiso_id = row["id"]
                st.session_state.form_return_to = "Listado"
                st.session_state._nav_formulario = True
                rerun_app()
        with c3:
            if st.button("Eliminar", key=f"del_{row['id']}_{i}", use_container_width=True):
                st.session_state.pending_delete_id = row["id"]
                st.session_state.pending_delete_titulo = row.get("titulo", "")
                rerun_app()


def _render_lista_scroll(df) -> None:
    with st.container(height=ASIST_LIST_SCROLL_HEIGHT, border=True):
        if df.empty:
            st.info("No hay compromisos que coincidan con los criterios.")
            return
        _render_lista_filas(df)


@st.fragment
def _listado_lista_fragment(df) -> None:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown('<span class="exec-toolbar-label">Buscar</span>', unsafe_allow_html=True)
        q = st.text_input(
            "Buscar compromisos",
            placeholder="Ej: Vidal, obras, urgente, agenda…",
            key="asist_search",
            label_visibility="collapsed",
        )
    with c2:
        st.markdown('<span class="exec-toolbar-label">Ordenar por</span>', unsafe_allow_html=True)
        sort = st.selectbox(
            "Ordenar compromisos",
            list(compromisos.SORT_OPTIONS.keys()),
            index=0,
            key="asist_sort",
            label_visibility="collapsed",
        )

    lista = compromisos.filter_search(df, q)
    lista = compromisos.sort_panel(lista, sort)

    st.markdown(
        f'<p class="exec-list-count">{len(lista)} compromiso(s)</p>',
        unsafe_allow_html=True,
    )
    _render_lista_scroll(lista)


def render_listado(client: Client) -> None:
    if msg := st.session_state.pop("_flash_msg", None):
        st.success(msg)
    st.subheader("Listado de compromisos")
    df = compromisos.fetch_panel(client, incluir_inactivos=True)
    if df.empty:
        st.info("No hay compromisos cargados.")
        return

    _render_confirmacion_borrado(client)
    _listado_lista_fragment(df)
