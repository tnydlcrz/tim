import streamlit as st

from src.auth import login
from src.ui import load_css, render_header, section_title


def show_login() -> None:
    load_css()
    render_header("Acceso al sistema")

    _, center, _ = st.columns([1, 1.1, 1])
    with center:
        section_title("Ingreso al sistema")
        if msg := st.session_state.pop("_login_msg", None):
            st.warning(msg)
        st.markdown(
            '<p class="section-hint">Ingresá con tu cuenta autorizada.</p>',
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Ingresar", use_container_width=True)
            if submitted:
                ok, err = login(email.strip(), password)
                if ok:
                    st.rerun()
                else:
                    st.error(f"No se pudo iniciar sesión: {err}")

        st.markdown(
            '<div class="info-box">Configurá Supabase en <code>.streamlit/secrets.toml</code>. '
            "Ver README para crear usuarios y perfiles.</div>",
            unsafe_allow_html=True,
        )