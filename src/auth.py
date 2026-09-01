import streamlit as st

from src.supabase_client import clear_client_cache, get_client


def is_auth_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "jwt expired" in msg or "invalid claim" in msg or "pgrst303" in msg:
        return True
    try:
        from postgrest.exceptions import APIError

        if isinstance(exc, APIError):
            err = exc.args[0] if exc.args else {}
            if isinstance(err, dict):
                code = str(err.get("code", "")).upper()
                message = str(err.get("message", "")).lower()
                if code == "PGRST303" or "jwt" in message:
                    return True
    except ImportError:
        pass
    return False


def try_refresh_session() -> bool:
    refresh = st.session_state.get("refresh_token")
    if not refresh:
        return False
    try:
        clear_client_cache()
        client = get_client(access_token=None)
        res = client.auth.refresh_session(refresh)
        session = res.session
        if not session:
            return False
        st.session_state.access_token = session.access_token
        st.session_state.refresh_token = session.refresh_token
        clear_client_cache()
        return True
    except Exception:
        return False


def session_expired() -> None:
    for key in (
        "authenticated",
        "access_token",
        "refresh_token",
        "user_id",
        "user_email",
        "user_rol",
        "user_nombre",
    ):
        st.session_state.pop(key, None)
    st.session_state.authenticated = False
    clear_client_cache()
    from src.data_cache import invalidate_data_cache

    invalidate_data_cache()
    st.session_state._login_msg = "Tu sesión expiró. Volvé a iniciar sesión."


def handle_auth_error(exc: BaseException) -> str | None:
    """None = no es error de auth; 'refresh' = token renovado; 'expired' = ir al login."""
    if not is_auth_error(exc):
        return None
    if try_refresh_session():
        return "refresh"
    session_expired()
    return "expired"


def init_session() -> None:
    defaults = {
        "authenticated": False,
        "access_token": None,
        "refresh_token": None,
        "user_id": None,
        "user_email": None,
        "user_rol": None,
        "user_nombre": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def login(email: str, password: str) -> tuple[bool, str]:
    try:
        client = get_client(access_token=None)
        response = client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        session = response.session
        user = response.user
        if not session or not user:
            return False, "Credenciales inválidas"

        clear_client_cache()
        authed = get_client(access_token=session.access_token)

        profile = (
            authed.table("profiles")
            .select("rol, nombre, email")
            .eq("id", user.id)
            .single()
            .execute()
        )
        data = profile.data
        if not data:
            return False, "Usuario sin perfil asignado. Contacte al administrador."

        st.session_state.authenticated = True
        st.session_state.access_token = session.access_token
        st.session_state.refresh_token = session.refresh_token
        st.session_state.user_id = user.id
        st.session_state.user_email = data.get("email") or user.email
        st.session_state.user_rol = data["rol"]
        st.session_state.user_nombre = data.get("nombre") or ""
        if data["rol"] == "asistente":
            st.session_state.asistente_page = "Listado"
        from src.data_cache import invalidate_data_cache

        invalidate_data_cache()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def logout() -> None:
    from src.data_cache import invalidate_data_cache

    invalidate_data_cache()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    clear_client_cache()


def require_auth() -> bool:
    init_session()
    return bool(st.session_state.get("authenticated"))


def is_asistente() -> bool:
    return st.session_state.get("user_rol") == "asistente"


def is_ejecutivo() -> bool:
    return st.session_state.get("user_rol") == "ejecutivo"
