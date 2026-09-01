from __future__ import annotations

from html import escape

import streamlit as st
import plotly.express as px
from supabase import Client

from src.services import compromisos
from src.ui import badge, estado_kind, format_fecha, format_hora, prioridad_kind, progress_bar_block, render_compromiso_row_compact, rerun_app, row_text
from src.views.agenda import render_agenda
from src.views.asistente.formulario import render_formulario
from src.views.ejecutivo import exec_form

LENSES = ["Categoría", "Ámbito", "Establecimiento", "Prioridad", "Avance", "Mes / Año"]
TAB_LISTA = exec_form.TAB_LISTA
TAB_GRAFICOS = "Gráficos"
TAB_AGENDA = exec_form.TAB_AGENDA
EXEC_LIST_SCROLL_HEIGHT = 520


def _init_state() -> None:
    defaults = {
        "exec_view": TAB_LISTA,
        "exec_lens": "Categoría",
        "exec_chart_filter": None,
        "exec_selected_id": None,
        "exec_detail_from": "lista",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _render_flash() -> None:
    if msg := st.session_state.pop("_exec_flash_msg", None):
        st.success(msg)


def _render_confirmacion_borrado(client: Client) -> bool:
    """Muestra confirmación. True si hay borrado pendiente (no renderizar acciones duplicadas)."""
    pending_id = st.session_state.get("exec_pending_delete_id")
    if not pending_id:
        return False
    titulo = st.session_state.get("exec_pending_delete_titulo", "")
    st.warning(f"¿Eliminar «{titulo}»? Esta acción no se puede deshacer.")
    c1, c2, _ = st.columns([1, 1, 4])
    with c1:
        if st.button("Sí, eliminar", type="primary", key="exec_confirm_delete_yes", use_container_width=True):
            compromisos.delete_compromiso(client, pending_id)
            st.session_state.pop("exec_pending_delete_id", None)
            st.session_state.pop("exec_pending_delete_titulo", None)
            st.session_state.exec_selected_id = None
            origen = st.session_state.get("exec_detail_from", "lista")
            if origen == "agenda":
                st.session_state.exec_view = TAB_AGENDA
            else:
                st.session_state.exec_view = TAB_LISTA
            st.session_state._exec_flash_msg = "Compromiso eliminado."
            st.rerun()
    with c2:
        if st.button("Cancelar", key="exec_confirm_delete_no", use_container_width=True):
            st.session_state.pop("exec_pending_delete_id", None)
            st.session_state.pop("exec_pending_delete_titulo", None)
            st.rerun()
    return True


def _sidebar_filters(df):
    st.sidebar.markdown("### Filtros")
    incluir_inactivos = st.sidebar.checkbox("Mostrar inactivos", value=False)

    categoria = st.sidebar.selectbox("Categoría", ["Todos"] + sorted(df["categoria"].dropna().unique().tolist()))

    ubicaciones = ["Todos"] + sorted(df["ubicacion_display"].dropna().unique().tolist())
    if any(df["establecimiento_id"].isna()):
        if "Ministerio de Salud (sin sede)" not in ubicaciones:
            ubicaciones.append("Ministerio de Salud (sin sede)")

    establecimiento = st.sidebar.selectbox("Establecimiento", ubicaciones)

    anios = ["Todos"]
    if "fecha_inicio" in df.columns and df["fecha_inicio"].notna().any():
        anios += sorted({int(y) for y in df["fecha_inicio"].dt.year.dropna().astype(int).unique()})
    anio_sel = st.sidebar.selectbox("Año", anios)
    meses = ["Todos"] + list(range(1, 13))
    mes_sel = st.sidebar.selectbox("Mes", meses)

    anio = None if anio_sel == "Todos" else int(anio_sel)
    mes = None if mes_sel == "Todos" else int(mes_sel)

    filtered = compromisos.apply_filters(
        df,
        establecimiento=establecimiento,
        categoria=categoria if categoria != "Todos" else None,
        anio=anio,
        mes=mes,
    )
    if "activo" in filtered.columns:
        activos = filtered[filtered["activo"] == True]  # noqa: E712
        lista = filtered if incluir_inactivos else activos
    else:
        activos = filtered
        lista = filtered
    return lista, activos


def _kpi_row(kpis: dict) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total visible", kpis["total"])
    c2.metric("Urgente + Altas", kpis["urgente_altas"])
    c3.metric("Demorados", kpis["demorados"])
    c4.metric("Completados", kpis["completados"])


def _chart_lens(df, lens: str):
    agg = compromisos.aggregate_lens(df, lens)
    if agg.empty:
        st.info("Sin datos para graficar.")
        return None
    plot_df = agg.rename(columns={"label": "segmento", "count": "cantidad"})
    fig = px.bar(
        plot_df,
        x="cantidad",
        y="segmento",
        orientation="h",
        title=f"Cantidad por {lens}",
        color="cantidad",
        color_continuous_scale=["#2D6A4F", "#1B4332"],
        labels={"cantidad": "Cantidad", "segmento": lens},
    )
    fig.update_layout(
        showlegend=False,
        height=max(300, len(agg) * 40),
        margin=dict(l=10, r=10, t=44, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=14),
        xaxis_title="Cantidad",
        yaxis_title=lens,
        hoverlabel=dict(bgcolor="white", font_size=13, font_family="sans-serif"),
    )
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>Cantidad: %{x}<extra></extra>",
    )
    fig.update_coloraxes(showscale=False)
    return fig, agg


def _render_lista_filas(df) -> None:
    for i, (_, row) in enumerate(df.iterrows()):
        estado = row.get("estado_display")
        if estado is None or (isinstance(estado, float) and estado != estado):
            estado = ""
        c1, c2 = st.columns([11, 1])
        with c1:
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
            if st.button("Ver", key=f"exec_ver_{row['id']}_{i}", use_container_width=True):
                exec_form.open_exec_detalle(row["id"], origen="lista")
                rerun_app()


def _render_lista_scroll(df) -> None:
    with st.container(height=EXEC_LIST_SCROLL_HEIGHT, border=True):
        if df.empty:
            st.info("No hay compromisos que coincidan con los criterios.")
            return
        _render_lista_filas(df)


@st.fragment
def _exec_lista_fragment(filtered) -> None:
    chart_filter = st.session_state.get("exec_chart_filter")
    lista = filtered
    if chart_filter:
        lens = chart_filter["lens"]
        label = chart_filter["label"]
        lista = compromisos.filter_by_lens(filtered, lens, label)
        fc1, fc2 = st.columns([5, 1])
        with fc1:
            st.markdown(
                f'<div class="exec-filter-banner">Filtrado desde gráfico: '
                f'<strong>{lens}</strong> = <strong>{label}</strong></div>',
                unsafe_allow_html=True,
            )
        with fc2:
            if st.button("Quitar filtro", key="clear_chart_filter", use_container_width=True):
                st.session_state.exec_chart_filter = None
                rerun_app()

    c1, c2, c3 = st.columns([3, 2, 1.2], vertical_alignment="bottom")
    with c1:
        st.markdown('<span class="exec-toolbar-label">Buscar</span>', unsafe_allow_html=True)
        q = st.text_input(
            "Buscar compromisos",
            placeholder="Ej: Vidal, obras, urgente…",
            key="exec_search",
            label_visibility="collapsed",
        )
    with c2:
        st.markdown('<span class="exec-toolbar-label">Ordenar por</span>', unsafe_allow_html=True)
        sort = st.selectbox(
            "Ordenar compromisos",
            list(compromisos.SORT_OPTIONS.keys()),
            index=0,
            key="exec_sort_select",
            label_visibility="collapsed",
        )
    with c3:
        if st.button("+ Nuevo compromiso", type="primary", key="exec_nuevo_compromiso", use_container_width=True):
            exec_form.open_exec_form_new(return_to="lista", solo_agenda=False)
            rerun_app()

    lista = compromisos.filter_search(lista, q)
    lista = compromisos.sort_panel(lista, sort)

    mc1, mc2 = st.columns([1, 4], vertical_alignment="center")
    with mc1:
        st.markdown(
            f'<p class="exec-list-count exec-list-count-inline">{len(lista)} compromiso(s)</p>',
            unsafe_allow_html=True,
        )
    with mc2:
        st.markdown(
            '<p class="exec-list-hint">Consultá el detalle de cada ítem con '
            "<strong>Ver</strong>. Desde ahí podés editar o eliminar.</p>",
            unsafe_allow_html=True,
        )

    _render_lista_scroll(lista)


def _render_tab_compromisos(filtered) -> None:
    _exec_lista_fragment(filtered)


def _render_tab_graficos(filtered) -> None:
    lens = st.selectbox("Ver por", LENSES, key="lens_select")
    st.session_state.exec_lens = lens

    result = _chart_lens(filtered, lens)
    if not result:
        return
    fig, agg = result
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Profundizar en un segmento")
    labels = agg["label"].tolist()
    pick = st.selectbox("Seleccionar segmento del gráfico", ["—"] + labels, key="chart_segment")
    if st.button("Ver compromisos de este segmento", key="chart_drill", use_container_width=False):
        if pick != "—":
            st.session_state.exec_chart_filter = {"lens": lens, "label": pick}
            st.session_state._nav_exec_lista = True
            st.rerun()


def _volver_desde_detalle() -> None:
    origen = st.session_state.get("exec_detail_from", "lista")
    st.session_state.exec_selected_id = None
    if origen == "agenda":
        st.session_state.exec_view = TAB_AGENDA
    else:
        st.session_state.exec_view = TAB_LISTA


def _volver_label() -> str:
    if st.session_state.get("exec_detail_from") == "agenda":
        return "← Volver a Agenda"
    return "← Volver al listado"


def _render_detalle(client: Client, compromiso_id: str) -> None:
    row = compromisos.fetch_compromiso(client, compromiso_id)
    if not row:
        st.warning("Compromiso no encontrado.")
        if st.button(_volver_label(), key="back_list_missing"):
            _volver_desde_detalle()
            st.rerun()
        return

    if _render_confirmacion_borrado(client):
        return

    lineas = compromisos.fetch_lineas(client, compromiso_id)
    es_agenda = row.get("categoria") == compromisos.AGENDA_CATEGORIA

    c_back, c_edit, c_del = st.columns([6, 1, 1])
    with c_back:
        if st.button(_volver_label(), key="back_list"):
            _volver_desde_detalle()
            st.rerun()
    with c_edit:
        if st.button("Editar", key="exec_detalle_editar", use_container_width=True):
            return_to = "agenda" if st.session_state.get("exec_detail_from") == "agenda" else "detalle"
            exec_form.open_exec_form_edit(compromiso_id, return_to=return_to)
            st.rerun()
    with c_del:
        if st.button("Eliminar", key="exec_detalle_eliminar", use_container_width=True):
            st.session_state.exec_pending_delete_id = compromiso_id
            st.session_state.exec_pending_delete_titulo = row.get("titulo", "")
            st.rerun()

    pk = prioridad_kind(row.get("prioridad", ""))
    cat = row_text(row.get("categoria"))
    cat_badge = badge(cat, "ambito") if cat else ""
    sub = row_text(row.get("subcategoria"))
    titulo = row.get("titulo") or ""
    ubicacion = row.get("ubicacion_display") or ""
    st.markdown(
        f'<div class="detalle-header">'
        f'{badge(row.get("prioridad", ""), pk)}{cat_badge}'
        f'<span class="detalle-ubicacion">{escape(ubicacion)}</span>'
        f"</div>"
        f"<h2>{escape(titulo)}</h2>"
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
        st.markdown("#### Ítems del compromiso")
        for ln in lineas:
            edo = ln.get("estados") or {}
            ename = edo.get("nombre", "")
            ek = estado_kind(ename)
            st.markdown(
                f"""
                <div class="linea-card">
                    <span>{ln.get('descripcion','')}</span>
                    <div class="linea-card-meta">
                        <span class="linea-avance">{int(ln.get('avance_pct') or 0)}%</span>
                        {badge(ename, ek)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_dashboard(client: Client) -> None:
    _init_state()
    _render_flash()

    if exec_form.exec_form_active():
        render_formulario(client, exec_form.get_exec_edit_id(), modo="ejecutivo")
        return

    df_all = compromisos.fetch_panel(client, incluir_inactivos=True)
    if df_all.empty:
        st.warning("No hay datos. Ejecutá la migración o `db/seed.sql` en Supabase.")
        return

    en_agenda = st.session_state.get("exec_view") == TAB_AGENDA

    if st.session_state.exec_selected_id:
        if not en_agenda:
            filtered, activos = _sidebar_filters(df_all)
            kpis = compromisos.compute_kpis(activos)
            _kpi_row(kpis)
        _render_detalle(client, st.session_state.exec_selected_id)
        return

    if en_agenda:
        st.sidebar.caption("Los filtros de compromisos no aplican a la vista Agenda.")
        filtered = df_all
    else:
        filtered, activos = _sidebar_filters(df_all)
        kpis = compromisos.compute_kpis(activos)
        _kpi_row(kpis)

    if st.session_state.pop("_nav_exec_lista", False):
        st.session_state["exec_view"] = TAB_LISTA

    view = st.radio(
        "Vista",
        [TAB_LISTA, TAB_AGENDA, TAB_GRAFICOS],
        horizontal=True,
        key="exec_view",
        label_visibility="collapsed",
    )
    if view == TAB_LISTA:
        _render_tab_compromisos(filtered)
    elif view == TAB_AGENDA:
        render_agenda(client, modo="ejecutivo")
    else:
        _render_tab_graficos(filtered)
