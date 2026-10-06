"""Vista de detalle de un compromiso (cuerpo compartido asistente / ejecutivo)."""

from __future__ import annotations

from html import escape

import streamlit as st
from supabase import Client

from src.services import compromisos
from src.ui import badge, estado_kind, format_fecha, format_hora, prioridad_kind, progress_bar_block, row_text


def render_compromiso_info(
    client: Client,
    compromiso_id: str,
    *,
    row: dict | None = None,
    lineas: list[dict] | None = None,
) -> bool:
    """Cabecera, metadatos e ítems. Devuelve False si el compromiso no existe."""
    row = row or compromisos.fetch_compromiso(client, compromiso_id)
    if not row:
        st.warning("Compromiso no encontrado.")
        return False

    lineas = lineas if lineas is not None else compromisos.fetch_lineas(client, compromiso_id)
    es_agenda = row.get("categoria") == compromisos.AGENDA_CATEGORIA

    pk = prioridad_kind(row.get("prioridad", ""))
    cat = row_text(row.get("categoria"))
    cat_badge = badge(cat, "ambito") if cat else ""
    sub = row_text(row.get("subcategoria"))
    titulo = row.get("titulo") or ""
    ubicacion = compromisos.format_ubicacion_compromiso(row)
    st.markdown(
        f'<div class="detalle-header">'
        f'{badge(row.get("prioridad", ""), pk)}{cat_badge}'
        f'<span class="detalle-ubicacion">{escape(ubicacion)}</span>'
        f"</div>"
        f'<p class="detalle-titulo">{escape(titulo)}</p>'
        + (f'<p class="card-categoria">{escape(sub)}</p>' if sub else ""),
        unsafe_allow_html=True,
    )
    if not es_agenda:
        st.markdown(
            progress_bar_block(int(row.get("avance_pct") or 0), 12),
            unsafe_allow_html=True,
        )

    if es_agenda and not row.get("activo", True):
        st.info("Evento cancelado.")
    elif es_agenda:
        st.caption("Para cancelar el evento, usá **Editar** y desmarcá «Evento programado».")

    c1, c2, c3 = st.columns(3)
    c1.write(f"**Fecha:** {format_fecha(row.get('fecha_inicio'))}")
    if es_agenda:
        c2.write(f"**Hora:** {format_hora(row.get('hora_inicio'))}")
        c3.write(f"**Estado:** {'Programado' if row.get('activo', True) else 'Cancelado'}")
    else:
        c2.write(f"**Fin:** {format_fecha(row.get('fecha_fin'))}")
        c3.write(f"**Líneas:** {row.get('total_lineas', 0)}")

    if not es_agenda:
        c4, c5 = st.columns(2)
        c4.write(f"**Servicio:** {row.get('servicio') or '—'}")
        c5.write(f"**Área / Sector:** {row.get('area') or '—'}")

        c6, c7 = st.columns(2)
        c6.write(f"**Número de expediente:** {row.get('numero_expte') or '—'}")
        c7.write(f"**Empresa:** {row.get('empresa') or '—'}")

    if row.get("persona_solicitante"):
        st.write(f"**{'Contacto' if es_agenda else 'Solicitante'}:** {row['persona_solicitante']}")
    if row.get("telefono_solicitante"):
        st.write(f"**Tel:** [{row['telefono_solicitante']}](tel:{row['telefono_solicitante']})")

    if not es_agenda:
        st.markdown(
            '<p class="detalle-lineas-heading"><strong>Ítems del compromiso:</strong></p>',
            unsafe_allow_html=True,
        )
        for ln in lineas:
            edo = ln.get("estados") or {}
            ename = edo.get("nombre", "")
            ek = estado_kind(ename)
            desc = escape(ln.get("descripcion") or "")
            st.markdown(
                f"""
                <div class="linea-card">
                    <span class="linea-card-text">{desc}</span>
                    <div class="linea-card-meta">
                        <span class="linea-avance">{int(ln.get('avance_pct') or 0)}%</span>
                        {badge(ename, ek)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    return True
