import streamlit as st

from src.auth import handle_auth_error, init_session, is_asistente, is_ejecutivo, logout, require_auth
from src.supabase_client import get_client
from src.ui import load_css, render_header
from src.views.asistente.formulario import render_formulario
from src.views.asistente.listado import render_listado
from src.views.agenda import render_agenda
from src.views.ejecutivo.dashboard import render_dashboard
from src.views.login import show_login

st.set_page_config(
    page_title="Compromisos TIM-Salud",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _render_app(client) -> None:
    with st.sidebar:
        st.markdown(f"**{st.session_state.get('user_nombre') or st.session_state.user_email}**")
        st.caption(f"Rol: {st.session_state.user_rol}")
        if st.button("Cerrar sesión", use_container_width=True):
            logout()
            st.rerun()

    if is_ejecutivo():
        render_header("Vista ejecutiva")
        render_dashboard(client)
    elif is_asistente():
        render_header("Carga de compromisos")
        nav_from_edit = st.session_state.pop("_nav_formulario", False)
        if nav_from_edit:
            st.session_state["asistente_page"] = "Formulario"
        if nav_page := st.session_state.pop("_nav_asistente_page", None):
            st.session_state["asistente_page"] = nav_page
        if st.session_state.pop("_nav_listado", False):
            st.session_state["asistente_page"] = "Listado"
        prev_page = st.session_state.get("_asistente_prev_page")
        page = st.sidebar.radio(
            "Menú",
            ["Listado", "Agenda", "Formulario"],
            key="asistente_page",
        )
        if page == "Formulario" and prev_page != "Formulario" and not nav_from_edit:
            st.session_state.pop("edit_compromiso_id", None)
            st.session_state.pop("form_solo_agenda", None)
            st.session_state.pop("form_return_to", None)
        st.session_state._asistente_prev_page = page
        edit_id = st.session_state.get("edit_compromiso_id")
        if page == "Listado":
            render_listado(client)
        elif page == "Agenda":
            render_agenda(client, modo="asistente")
        else:
            render_formulario(client, edit_id)
    else:
        st.error("Rol no reconocido. Actualizá la tabla profiles en Supabase.")


def _preflight_auth(client) -> bool:
    """Valida el token antes de pintar la UI. False → sesión expirada (ya limpiada)."""
    user_id = st.session_state.get("user_id")
    if not user_id:
        return False
    try:
        client.table("profiles").select("id").eq("id", user_id).limit(1).execute()
        return True
    except Exception as exc:
        auth_action = handle_auth_error(exc)
        if auth_action == "refresh":
            return True
        if auth_action == "expired":
            return False
        raise


def main() -> None:
    init_session()
    load_css()

    if not require_auth():
        show_login()
        return

    try:
        client = get_client()
        if not _preflight_auth(client):
            st.rerun()
            return
        client = get_client()
        _render_app(client)
    except Exception as exc:
        auth_action = handle_auth_error(exc)
        if auth_action == "refresh":
            st.rerun()
        elif auth_action == "expired":
            st.rerun()
        else:
            raise


if __name__ == "__main__":
    main()
