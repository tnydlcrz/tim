from html import escape
from datetime import date, time
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def rerun_app() -> None:
    """Rerun completo de la app (necesario al navegar desde un @st.fragment)."""
    st.rerun(scope="app")


def load_css() -> None:
    css_path = ASSETS / "styles.css"
    if css_path.exists():
        mtime = css_path.stat().st_mtime
        st.markdown(f"<style>{_css_text(mtime)}</style>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _css_text(_mtime: float) -> str:
    css_path = ASSETS / "styles.css"
    return css_path.read_text(encoding="utf-8") if css_path.exists() else ""


def render_header(subtitle: str = "") -> None:
    sub = f'<p class="header-sub">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f"""
        <div class="exec-header">
            <h1>Tablero de Seguimiento de Compromisos</h1>
            <p class="header-org">Ministerio de Salud — Provincia de Corrientes</p>
            {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "default") -> str:
    return f'<span class="badge badge-{kind}">{escape(str(text or ""))}</span>'


def _cell(text: str) -> str:
    return escape(str(text or ""))


def _is_null_value(value: object) -> bool:
    if value is None or value == "":
        return True
    if type(value).__name__ in ("NaTType", "NAType"):
        return True
    try:
        import pandas as pd

        if pd.isna(value):
            return True
    except (TypeError, ValueError, ImportError):
        pass
    try:
        if value != value:
            return True
    except TypeError:
        pass
    s = str(value).strip().lower()
    return s in ("none", "nat", "nan")


def format_fecha(value: object | None) -> str:
    if _is_null_value(value):
        return "—"
    if isinstance(value, date):
        try:
            return value.strftime("%d/%m/%Y")
        except (ValueError, OSError):
            return "—"
    s = str(value).strip()
    if not s:
        return "—"
    try:
        return date.fromisoformat(s[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return "—"


def format_hora(value: object | None) -> str:
    if _is_null_value(value):
        return "—"
    if isinstance(value, time):
        return value.strftime("%H:%M")
    s = str(value).strip()
    if not s:
        return "—"
    parts = s.split(":")
    if len(parts) >= 2:
        try:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        except ValueError:
            pass
    return "—"


def format_categoria_line(categoria: object | None, subcategoria: object | None = None) -> str:
    def _txt(value: object | None) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and value != value:
            return ""
        s = str(value).strip()
        return "" if s.lower() in ("none", "nan", "nat") else s

    cat = _txt(categoria)
    sub = _txt(subcategoria)
    if cat and sub:
        return f"{cat} · {sub}"
    return cat or sub or "—"


def row_text(value: object | None, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, float) and value != value:
        return default
    s = str(value).strip()
    return default if s.lower() in ("none", "nan", "nat") else s


def prioridad_kind(nombre: str) -> str:
    n = (nombre or "").lower()
    if "urgent" in n:
        return "urgente"
    if "alta" in n:
        return "alta"
    if "media" in n:
        return "media"
    if "baja" in n:
        return "baja"
    return "default"


def estado_kind(nombre: str) -> str:
    n = (nombre or "").lower().strip()
    if "sin iniciar" in n:
        return "sin-iniciar"
    if "complet" in n:
        return "completado"
    if "demorad" in n:
        return "demorado"
    if "en curso" in n:
        return "en-curso"
    if "iniciad" in n:
        return "iniciado"
    return "default"


def section_title(text: str) -> None:
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


def progress_bar(pct: int, height: int = 8) -> str:
    pct = max(0, min(100, int(pct or 0)))
    return (
        f'<span class="progress-wrap" style="height:{height}px">'
        f'<span class="progress-fill" style="width:{pct}%"></span>'
        f"</span>"
        f'<span class="progress-label">{pct}%</span>'
    )


def progress_bar_block(pct: int, height: int = 12) -> str:
    """Barra de avance para detalle (HTML en una sola línea, compatible con Streamlit)."""
    return f'<div class="card-progress">{progress_bar(pct, height)}</div>'


def compromiso_card(
    titulo: str,
    ubicacion: str,
    categoria: str,
    prioridad: str,
    avance_pct: int,
    total_lineas: int,
) -> str:
    pk = prioridad_kind(prioridad)
    cat = (categoria or "").strip()
    cat_badge = badge(cat, "ambito") if cat else ""
    return f"""
    <div class="compromiso-card">
        <div class="card-top">
            <span class="card-ubicacion">{ubicacion}</span>
            {badge(prioridad, pk)}
            {cat_badge}
        </div>
        <h3 class="card-titulo">{titulo}</h3>
        <div class="card-progress">{progress_bar(avance_pct)}</div>
        <span class="card-meta">{total_lineas} línea(s)</span>
    </div>
    """


def compromiso_row_compact(
    titulo: str,
    ubicacion: str,
    categoria: str,
    prioridad: str,
    avance_pct: int,
    estado: str = "",
    activo: bool = True,
    fecha_inicio: object | None = None,
    subcategoria: str = "",
) -> str:
    pk = prioridad_kind(prioridad)
    cat = (categoria or "").strip()
    cat_badge = badge(cat, "ambito") if cat and cat != "—" else ""
    pct = max(0, min(100, int(avance_pct or 0)))
    if activo:
        ek = estado_kind(estado) if estado else "default"
        est = badge(estado, ek) if estado else ""
        avance_html = (
            f"{est}"
            f'<span class="exec-row-bar"><span class="exec-row-bar-fill" style="width:{pct}%"></span></span>'
            f'<span class="exec-row-pct">{pct}%</span>'
        )
        row_class = "exec-row"
    else:
        avance_html = badge("Inactivo", "inactivo")
        row_class = "exec-row exec-row-inactivo"
    meta_parts: list[str] = []
    sub = (subcategoria or "").strip()
    if sub and sub != "—":
        meta_parts.append(_cell(sub))
    meta_parts.append(_cell(ubicacion))
    meta_parts.append(f"Inicio: {_cell(format_fecha(fecha_inicio))}")
    meta = " · ".join(meta_parts)
    return (
        f'<div class="{row_class}">'
        f'<span class="exec-row-badges">{badge(prioridad, pk)}{cat_badge}</span>'
        f'<span class="exec-row-body">'
        f'<span class="exec-row-title-row">'
        f'<span class="exec-row-title">{_cell(titulo)}</span>'
        f'<span class="exec-row-avance">'
        f"{avance_html}"
        f"</span>"
        f"</span>"
        f'<span class="exec-row-meta">{meta}</span>'
        f"</span>"
        f"</div>"
    )


def render_compromiso_row_compact(
    titulo: str,
    ubicacion: str,
    categoria: str,
    prioridad: str,
    avance_pct: int,
    estado: str = "",
    activo: bool = True,
    fecha_inicio: object | None = None,
    subcategoria: str = "",
) -> None:
    st.markdown(
        compromiso_row_compact(
            titulo=titulo,
            ubicacion=ubicacion,
            categoria=categoria,
            prioridad=prioridad,
            avance_pct=avance_pct,
            estado=estado,
            activo=activo,
            fecha_inicio=fecha_inicio,
            subcategoria=subcategoria,
        ),
        unsafe_allow_html=True,
    )


def agenda_event_row_html(
    titulo: str,
    hora: object | None,
    ubicacion: str,
    subcategoria: str,
    prioridad: str,
    activo: bool = True,
    persona: str = "",
    fecha: object | None = None,
) -> str:
    pk = prioridad_kind(prioridad)
    hora_txt = format_hora(hora)
    hora_cls = "agenda-hora-vacia" if hora_txt == "—" else "agenda-hora"
    hora_label = "Sin horario" if hora_txt == "—" else hora_txt
    meta_parts = []
    if fecha is not None:
        meta_parts.append(_cell(format_fecha(fecha)))
    meta_parts.append(_cell(ubicacion))
    if subcategoria:
        meta_parts.append(_cell(subcategoria))
    if persona:
        meta_parts.append(_cell(persona))
    meta = " · ".join(p for p in meta_parts if p)
    cancel = badge("Cancelado", "inactivo") if not activo else ""
    row_cls = "agenda-event" if activo else "agenda-event agenda-event-cancelado"
    return (
        f'<div class="{row_cls}">'
        f'<span class="{hora_cls}">{_cell(hora_label)}</span>'
        f'<span class="agenda-event-body">'
        f'<span class="agenda-event-title-row">'
        f'<span class="agenda-event-title">{_cell(titulo)}</span>'
        f'<span class="agenda-event-badges">{badge(prioridad, pk)}{cancel}</span>'
        f"</span>"
        f'<span class="agenda-event-meta">{meta or "—"}</span>'
        f"</span>"
        f"</div>"
    )


def render_agenda_event_row(**kwargs) -> None:
    st.markdown(agenda_event_row_html(**kwargs), unsafe_allow_html=True)


def breadcrumb(parts: list[str]) -> None:
    if not parts:
        return
    html = " › ".join(f"<span>{p}</span>" for p in parts)
    st.markdown(f'<div class="breadcrumb">{html}</div>', unsafe_allow_html=True)
