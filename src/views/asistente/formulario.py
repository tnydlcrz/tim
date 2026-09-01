from __future__ import annotations

import uuid
from datetime import date, time

import streamlit as st
from supabase import Client

from src.services import catalogos, compromisos
from src.ui import section_title

FORM_SCROLL_HEIGHT = 580


def _form_key(field: str, edit_id: str | None) -> str:
    return f"{field}_{edit_id or 'new'}"


def _linea_blank(
    descripcion: str = "",
    estado_id: str | None = None,
    avance_pct: int = 0,
    notas: str = "",
    uid: str | None = None,
) -> dict:
    return {
        "uid": uid or str(uuid.uuid4()),
        "descripcion": descripcion,
        "estado_id": estado_id,
        "avance_pct": compromisos.normalizar_avance(avance_pct),
        "notas": notas,
    }


def _sync_lineas_from_session(
    lineas_form: list[dict],
    estado_ids: list[str],
    avance_opts: tuple[int, ...],
) -> list[dict]:
    synced: list[dict] = []
    for ln in lineas_form:
        uid = ln["uid"]
        e_sel = st.session_state.get(f"le_{uid}", 0)
        a_sel = st.session_state.get(f"la_{uid}", 0)
        eid = estado_ids[e_sel] if estado_ids[e_sel] else ln.get("estado_id")
        avance = avance_opts[a_sel] if a_sel < len(avance_opts) else ln.get("avance_pct", 0)
        synced.append(
            {
                "uid": uid,
                "descripcion": st.session_state.get(f"ld_{uid}", ln.get("descripcion", "")),
                "estado_id": eid,
                "avance_pct": compromisos.normalizar_avance(avance),
                "notas": ln.get("notas", ""),
            }
        )
    return synced


def _lineas_validas(lineas_form: list[dict]) -> list[dict]:
    valid: list[dict] = []
    for ln in lineas_form:
        desc = (ln.get("descripcion") or "").strip()
        eid = ln.get("estado_id")
        if desc and eid:
            valid.append(
                {
                    "descripcion": desc,
                    "estado_id": eid,
                    "avance_pct": compromisos.normalizar_avance(ln.get("avance_pct")),
                }
            )
    return valid

def _parse_date(value: object | None) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _select_catalog(
    label: str,
    items: list[dict],
    key: str,
    required: bool = False,
    default_id: str | None = None,
) -> str | None:
    options = catalogos.catalogo_map(items, include_empty=not required)
    ids = list(options.keys())
    labels = list(options.values())
    default_idx = 0
    if default_id and default_id in ids:
        default_idx = ids.index(default_id)
    if key in st.session_state:
        idx_saved = st.session_state[key]
        if not isinstance(idx_saved, int) or idx_saved < 0 or idx_saved >= len(labels):
            del st.session_state[key]
    if key not in st.session_state:
        st.session_state[key] = default_idx
    idx = st.selectbox(
        label,
        range(len(labels)),
        format_func=lambda i, lbls=labels: lbls[i],
        key=key,
    )
    val = ids[idx]
    return val if val else None


def _reset_establecimiento_si_cambio_localidad(edit_id: str | None, loc_id: str | None) -> None:
    prev_key = _form_key("prev_loc", edit_id)
    est_key = _form_key("est", edit_id)
    if st.session_state.get(prev_key) != loc_id:
        st.session_state.pop(est_key, None)
        st.session_state[prev_key] = loc_id


def _render_ubicacion(
    cats: dict[str, list[dict]],
    ex: dict,
    edit_id: str | None,
    default_rep: str | None,
    default_loc: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Repartición, localidad y establecimiento (fuera del form para filtrar sedes)."""
    section_title("Ubicación")
    c1, c2, c3 = st.columns(3)
    with c1:
        rep_id = _select_catalog(
            "Repartición *",
            cats["reparticiones"],
            _form_key("rep", edit_id),
            default_id=default_rep,
        )
    with c2:
        loc_id = _select_catalog(
            "Localidad",
            cats["localidades"],
            _form_key("loc", edit_id),
            default_id=default_loc,
        )
    _reset_establecimiento_si_cambio_localidad(edit_id, loc_id)

    est_filtrados = catalogos.establecimientos_por_localidad(cats["establecimientos"], loc_id)
    est_items = [{**row, "display": row["nombre"]} for row in est_filtrados]
    default_est = ex.get("establecimiento_id")
    if default_est and default_est not in {row["id"] for row in est_filtrados}:
        default_est = None

    with c3:
        if loc_id and not est_filtrados:
            st.selectbox("Establecimiento", ["—"], disabled=True, key=_form_key("est_na", edit_id))
            est_id = None
        else:
            est_id = _select_catalog(
                "Establecimiento",
                est_items,
                _form_key("est", edit_id),
                default_id=default_est,
            )
    return rep_id, loc_id, est_id


def _render_agenda_detalle(
    ex: dict,
    edit_id: str | None,
) -> tuple[date | None, time | None, str]:
    """Fecha, hora y contacto de agenda (fuera del form para checkboxes reactivos)."""
    section_title("Detalle del evento")
    st.caption(
        "Evento de una sola vez: fecha y horario opcionales. "
        "Si no se cancela, se asume que se realizó."
    )
    c10, c11 = st.columns(2)
    with c10:
        default_fi = _parse_date(ex.get("fecha_inicio"))
        if not edit_id and default_fi is None:
            default_fi = compromisos.hoy_ar()
        con_fecha = st.checkbox(
            "Asignar fecha",
            value=default_fi is not None,
            key=_form_key("con_fecha", edit_id),
        )
        fecha_inicio = None
        if con_fecha:
            fecha_inicio = st.date_input(
                "Fecha del evento",
                value=default_fi or compromisos.hoy_ar(),
                format="DD/MM/YYYY",
                key=_form_key("fi", edit_id),
            )
    with c11:
        hora_prev = compromisos.parse_hora(ex.get("hora_inicio"))
        con_hora = st.checkbox(
            "Definir horario",
            value=hora_prev is not None,
            key=_form_key("con_hora", edit_id),
        )
        hora_inicio = None
        if con_hora:
            hora_inicio = st.time_input(
                "Hora",
                value=hora_prev or time(9, 0),
                key=_form_key("hi", edit_id),
            )
    persona_sol = st.text_input(
        "Persona / contacto",
        value=ex.get("persona_solicitante", "") or "",
        key=_form_key("ps", edit_id),
    )
    return fecha_inicio, hora_inicio, persona_sol


def _categorias_para_formulario(
    categorias: list[dict],
    *,
    solo_agenda: bool,
    excluir_agenda: bool,
) -> list[dict]:
    if solo_agenda:
        return [c for c in categorias if c.get("nombre") == compromisos.AGENDA_CATEGORIA]
    if excluir_agenda:
        return [c for c in categorias if c.get("nombre") != compromisos.AGENDA_CATEGORIA]
    return categorias


def _render_clasificacion(
    client: Client,
    cats: dict[str, list[dict]],
    ex: dict,
    edit_id: str | None,
    *,
    solo_agenda: bool = False,
    excluir_agenda: bool = False,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Prioridad, categoría, subcategoría y ámbito (fuera del form para actualizar al cambiar)."""
    c4, c5, c6 = st.columns(3)
    with c4:
        default_pri = ex.get("prioridad_id") or catalogos.id_por_nombre(cats["prioridades"], "Media")
        pri_id = _select_catalog(
            "Prioridad *",
            cats["prioridades"],
            _form_key("pri", edit_id),
            required=True,
            default_id=default_pri,
        )
    categorias = _categorias_para_formulario(
        cats["categorias"],
        solo_agenda=solo_agenda,
        excluir_agenda=excluir_agenda,
    )
    with c5:
        if solo_agenda and len(categorias) == 1:
            cat = categorias[0]
            st.selectbox(
                "Categoría *",
                [cat["nombre"]],
                disabled=True,
                key=_form_key("cat_agenda_locked", edit_id),
            )
            cat_id = cat["id"]
        elif categorias:
            cat_id = _select_catalog(
                "Categoría *",
                categorias,
                _form_key("cat", edit_id),
                required=True,
                default_id=ex.get("categoria_id"),
            )
        else:
            st.error("No hay categorías disponibles para este formulario.")
            cat_id = None
    with c6:
        subcats = catalogos.fetch_subcategorias(client, cat_id)
        if subcats:
            default_sub = ex.get("subcategoria_id") if ex.get("categoria_id") == cat_id else None
            sub_id = _select_catalog(
                "Subcategoría",
                subcats,
                _form_key(f"sub_{cat_id}", edit_id),
                default_id=default_sub,
            )
        else:
            sub_id = None
            st.selectbox(
                "Subcategoría",
                ["—"],
                disabled=True,
                key=_form_key(f"sub_na_{cat_id or 'none'}", edit_id),
            )

    amb_id = catalogos.resolve_ambito_id(cats["categorias"], subcats, cat_id, sub_id)
    amb_nombre = catalogos.nombre_por_id(cats["ambitos"], amb_id) if amb_id else "—"
    st.caption(f"Ámbito: {amb_nombre} (según categoría / subcategoría)")
    return pri_id, cat_id, sub_id, amb_id


def _cancelar_formulario(modo: str = "asistente") -> None:
    st.session_state.pop("lineas_form", None)
    st.session_state.pop("_form_edit", None)
    st.session_state.pop("form_solo_agenda", None)
    if modo == "ejecutivo":
        return_to = st.session_state.pop("exec_form_return", "lista")
        return_id = st.session_state.pop("exec_form_return_id", None)
        st.session_state.pop("exec_form_mode", None)
        st.session_state.pop("exec_form_edit_id", None)
        if return_to == "detalle" and return_id:
            st.session_state.exec_selected_id = return_id
        elif return_to == "agenda":
            st.session_state.exec_selected_id = None
            st.session_state.exec_view = "Agenda"
        else:
            st.session_state.exec_selected_id = None
            st.session_state.exec_view = "Compromisos"
    else:
        st.session_state.pop("edit_compromiso_id", None)
        return_page = st.session_state.pop("form_return_to", "Listado")
        st.session_state._nav_asistente_page = return_page


def _finalizar_guardado(modo: str, edit_id: str | None, nuevo_id: str | None = None) -> None:
    if modo == "ejecutivo":
        if (
            st.session_state.get("exec_form_mode") == "new"
            and nuevo_id
            and st.session_state.get("exec_form_return") != "agenda"
        ):
            st.session_state.exec_form_return = "detalle"
            st.session_state.exec_form_return_id = nuevo_id
        st.session_state._exec_flash_msg = "Compromiso guardado."
    else:
        st.session_state._flash_msg = "Compromiso guardado."
    _cancelar_formulario(modo)


def render_formulario(client: Client, edit_id: str | None = None, modo: str = "asistente") -> None:
    cats = catalogos.load_catalogos(client)
    existing = compromisos.fetch_compromiso(client, edit_id) if edit_id else None
    lineas_existing = compromisos.fetch_lineas(client, edit_id) if edit_id else []

    if st.session_state.pop("form_preset_agenda", False) and not edit_id:
        st.session_state.form_solo_agenda = True

    if edit_id and existing:
        cat_nombre_ex = catalogos.nombre_por_id(cats["categorias"], existing.get("categoria_id"))
        if cat_nombre_ex == compromisos.AGENDA_CATEGORIA:
            st.session_state.form_solo_agenda = True
        else:
            st.session_state.pop("form_solo_agenda", None)

    solo_agenda = bool(st.session_state.get("form_solo_agenda"))

    if solo_agenda:
        st.subheader("Editar evento de agenda" if edit_id else "Nuevo evento de agenda")
    else:
        st.subheader("Editar compromiso" if edit_id else "Nuevo compromiso")
    cancel_label = (
        "← Cancelar y volver"
        if modo == "ejecutivo"
        else (
            "← Cancelar y volver a Agenda"
            if st.session_state.get("form_return_to") == "Agenda"
            else "← Cancelar y volver al listado"
        )
    )
    if st.button(cancel_label, key="form_cancel_top"):
        _cancelar_formulario(modo)
        st.rerun()

    if "lineas_form" not in st.session_state or st.session_state.get("_form_edit") != edit_id:
        if lineas_existing:
            st.session_state.lineas_form = [
                _linea_blank(
                    descripcion=ln["descripcion"],
                    estado_id=ln["estado_id"],
                    avance_pct=compromisos.normalizar_avance(ln.get("avance_pct")),
                    notas=ln.get("notas") or "",
                    uid=str(ln["id"]),
                )
                for ln in lineas_existing
            ]
        else:
            st.session_state.lineas_form = [_linea_blank()]
        st.session_state._form_edit = edit_id

    ex = existing or {}
    default_rep = ex.get("reparticion_id") or catalogos.id_por_nombre(
        cats["reparticiones"], "Ministerio de Salud"
    )
    default_loc = ex.get("localidad_id") or catalogos.id_por_nombre(cats["localidades"], "Corrientes")

    with st.container(height=FORM_SCROLL_HEIGHT, border=True):
        section_title("Clasificación")
        pri_id, cat_id, sub_id, amb_id = _render_clasificacion(
            client,
            cats,
            ex,
            edit_id,
            solo_agenda=solo_agenda,
            excluir_agenda=not solo_agenda,
        )
        cat_nombre = catalogos.nombre_por_id(cats["categorias"], cat_id)
        es_agenda = cat_nombre == compromisos.AGENDA_CATEGORIA

        titulo = ex.get("titulo", "")
        if es_agenda:
            section_title("Cabecera")
            titulo = st.text_input(
                "Título del compromiso *",
                value=ex.get("titulo", ""),
                key=_form_key("titulo", edit_id),
            )

        rep_id, loc_id, est_id = _render_ubicacion(cats, ex, edit_id, default_rep, default_loc)

        fecha_inicio: date | None = None
        fecha_fin: date | None = None
        hora_inicio: time | None = None
        persona_sol = ""
        numero_expte = ""
        empresa = ""
        srv_id: str | None = None
        area_id: str | None = None

        if es_agenda:
            fecha_inicio, hora_inicio, persona_sol = _render_agenda_detalle(ex, edit_id)

        with st.form("compromiso_form", clear_on_submit=not edit_id):
            if not es_agenda:
                section_title("Cabecera")
                titulo = st.text_input("Título del compromiso *", value=ex.get("titulo", ""))

            if not es_agenda:
                c7, c8 = st.columns(2)
                with c7:
                    srv_id = _select_catalog(
                        "Servicio",
                        cats["servicios"],
                        _form_key("srv", edit_id),
                        default_id=ex.get("servicio_id"),
                    )
                with c8:
                    area_id = _select_catalog(
                        "Área / Sector",
                        cats["areas"],
                        _form_key("area", edit_id),
                        default_id=ex.get("area_id"),
                    )

            activo = st.checkbox(
                "Evento programado" if es_agenda else "Activo",
                value=ex.get("activo", True),
                help="Desmarcá si el evento fue cancelado." if es_agenda else None,
            )

            if not es_agenda and cat_nombre in ("Obras", "Equipamiento", "Nombramiento") and not est_id:
                st.warning("Se recomienda indicar establecimiento para esta categoría.")

            if not es_agenda:
                section_title("Detalle operativo")
                c10, c11 = st.columns(2)
                with c10:
                    fecha_inicio = st.date_input(
                        "Fecha inicio",
                        value=_parse_date(ex.get("fecha_inicio")),
                        format="DD/MM/YYYY",
                        key=_form_key("fi", edit_id),
                    )
                with c11:
                    fecha_fin = st.date_input(
                        "Fecha fin",
                        value=_parse_date(ex.get("fecha_fin")),
                        format="DD/MM/YYYY",
                        key=_form_key("ff", edit_id),
                    )
                c12, c13, c14 = st.columns(3)
                with c12:
                    persona_sol = st.text_input(
                        "Persona solicitante",
                        value=ex.get("persona_solicitante", "") or "",
                        key=_form_key("ps", edit_id),
                    )
                with c13:
                    numero_expte = st.text_input(
                        "Número de expediente",
                        value=ex.get("numero_expte", "") or "",
                        key=_form_key("nex", edit_id),
                    )
                with c14:
                    empresa = st.text_input(
                        "Empresa",
                        value=ex.get("empresa", "") or "",
                        key=_form_key("emp", edit_id),
                    )

            if not es_agenda:
                section_title("Líneas de compromiso")
                st.caption("Cada línea tiene estado y avance independientes.")

            if not es_agenda:
                estados_map = catalogos.catalogo_map(cats["estados"], include_empty=True)
                estado_ids = list(estados_map.keys())
                estado_labels = list(estados_map.values())
                avance_opts = list(compromisos.AVANCE_NIVELES)
                lineas_ui = st.session_state.lineas_form
                delete_uid: str | None = None

                for i, ln in enumerate(lineas_ui):
                    uid = ln["uid"]
                    lh, la = st.columns([5, 1])
                    with lh:
                        st.markdown(f'<p class="linea-label">Línea {i + 1}</p>', unsafe_allow_html=True)
                    with la:
                        if len(lineas_ui) > 1 and st.form_submit_button(
                            "Eliminar",
                            key=f"del_{uid}",
                            use_container_width=True,
                        ):
                            delete_uid = uid

                    desc = st.text_input(
                        "Descripción *",
                        value=ln.get("descripcion", ""),
                        key=f"ld_{uid}",
                    )
                    ce, ca = st.columns(2)
                    with ce:
                        eidx = 0
                        if ln.get("estado_id") in estado_ids:
                            eidx = estado_ids.index(ln["estado_id"])
                        st.selectbox(
                            "Estado *",
                            range(len(estado_labels)),
                            index=eidx,
                            format_func=lambda x, lbls=estado_labels: lbls[x],
                            key=f"le_{uid}",
                        )
                    with ca:
                        avance_val = compromisos.normalizar_avance(ln.get("avance_pct"))
                        aidx = avance_opts.index(avance_val) if avance_val in avance_opts else 0
                        st.selectbox(
                            "Avance *",
                            range(len(avance_opts)),
                            index=aidx,
                            format_func=lambda x, opts=avance_opts: f"{opts[x]}%",
                            key=f"la_{uid}",
                        )
                    ln["descripcion"] = desc

                add_line = st.form_submit_button("+ Agregar otra línea", type="secondary")
            else:
                delete_uid = None
                add_line = False

            c_save, c_cancel = st.columns(2)
            with c_save:
                save_label = "Guardar evento" if es_agenda else "Guardar compromiso"
                save = st.form_submit_button(save_label, type="primary", use_container_width=True)
            with c_cancel:
                cancel = st.form_submit_button("Cancelar", type="secondary", use_container_width=True)

            if cancel:
                _cancelar_formulario(modo)
                st.rerun()

            if not es_agenda and delete_uid is not None:
                st.session_state.lineas_form = [
                    ln for ln in _sync_lineas_from_session(lineas_ui, estado_ids, tuple(avance_opts))
                    if ln["uid"] != delete_uid
                ]
                st.rerun()

            if not es_agenda and add_line:
                st.session_state.lineas_form = _sync_lineas_from_session(
                    lineas_ui, estado_ids, tuple(avance_opts)
                )
                st.session_state.lineas_form.append(_linea_blank())
                st.rerun()

            if save:
                titulo_guardar = (titulo or "").strip()
                if es_agenda:
                    estado_id = catalogos.id_por_nombre(cats["estados"], "Sin iniciar")
                    if not estado_id and cats["estados"]:
                        estado_id = cats["estados"][0]["id"]
                    valid_lineas = [
                        {
                            "descripcion": titulo_guardar,
                            "estado_id": estado_id,
                            "avance_pct": 0,
                        }
                    ]
                else:
                    synced = _sync_lineas_from_session(lineas_ui, estado_ids, tuple(avance_opts))
                    valid_lineas = _lineas_validas(synced)
                if not titulo_guardar:
                    st.error("El título es obligatorio.")
                    return
                if not cat_id or not pri_id:
                    st.error("Completá categoría y prioridad.")
                    return
                if not amb_id:
                    st.error("No se pudo determinar el ámbito para la categoría seleccionada.")
                    return
                if not valid_lineas:
                    st.error("Agregá al menos una línea con descripción, estado y avance.")
                    return
                subcats = catalogos.fetch_subcategorias(client, cat_id)
                subcategoria_id = sub_id if subcats and sub_id in {s["id"] for s in subcats} else None

                master = {
                    "titulo": titulo_guardar,
                    "reparticion_id": rep_id,
                    "localidad_id": loc_id,
                    "establecimiento_id": est_id,
                    "servicio_id": srv_id,
                    "area_id": area_id,
                    "categoria_id": cat_id,
                    "subcategoria_id": subcategoria_id,
                    "ambito_id": amb_id,
                    "prioridad_id": pri_id,
                    "activo": activo,
                    "persona_solicitante": persona_sol or None,
                    "fecha_inicio": str(fecha_inicio) if fecha_inicio else None,
                }
                if es_agenda:
                    master["hora_inicio"] = compromisos.format_hora_db(hora_inicio)
                    master["fecha_fin"] = None
                    master["numero_expte"] = None
                    master["empresa"] = None
                    master["servicio_id"] = None
                    master["area_id"] = None
                else:
                    master["numero_expte"] = numero_expte.strip() or None
                    master["empresa"] = empresa.strip() or None
                    master["fecha_fin"] = str(fecha_fin) if fecha_fin else None
                if edit_id:
                    master.pop("created_by", None)
                try:
                    nuevo_id = compromisos.save_compromiso(client, master, valid_lineas, edit_id)
                    _finalizar_guardado(modo, edit_id, nuevo_id)
                    st.rerun()
                except Exception as exc:
                    st.error(compromisos.format_save_error(exc))
