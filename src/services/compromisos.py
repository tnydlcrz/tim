from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from supabase import Client

AGENDA_CATEGORIA = "Agenda"
TZ_AR = ZoneInfo("America/Argentina/Cordoba")


def format_save_error(exc: BaseException) -> str:
    msg = str(exc).lower()
    if "42501" in str(exc) or "row-level security" in msg:
        rol = st.session_state.get("user_rol")
        if rol == "ejecutivo":
            return (
                "No tenés permiso para guardar cambios. En Supabase → SQL Editor ejecutá "
                "`db/migration_rls_ejecutivo_write.sql` para habilitar escritura al rol ejecutivo."
            )
        return (
            "No tenés permiso para guardar (política RLS). Verificá que tu usuario exista "
            "en la tabla `profiles` con rol `asistente` o `ejecutivo`."
        )
    return f"Error al guardar: {exc}"


def _subcategoria_map(client: Client) -> dict[str, str]:
    rows = client.table("subcategorias").select("id,nombre").execute().data or []
    return {r["id"]: r["nombre"] for r in rows}


def _attach_subcategoria_df(df: pd.DataFrame, client: Client) -> pd.DataFrame:
    if df.empty or "subcategoria_id" not in df.columns:
        return df
    sub_map = _subcategoria_map(client)
    out = df.copy()
    if "subcategoria" not in out.columns:
        out["subcategoria"] = out["subcategoria_id"].map(sub_map)
    else:
        missing = out["subcategoria"].isna() & out["subcategoria_id"].notna()
        out.loc[missing, "subcategoria"] = out.loc[missing, "subcategoria_id"].map(sub_map)
    return out


def _attach_subcategoria_row(row: dict, client: Client) -> dict:
    if not row.get("subcategoria") and row.get("subcategoria_id"):
        sub_map = _subcategoria_map(client)
        row = dict(row)
        row["subcategoria"] = sub_map.get(row["subcategoria_id"])
    return row


def _fetch_panel_impl(client: Client, incluir_inactivos: bool = False) -> pd.DataFrame:
    q = client.table("panel_base").select("*")
    if not incluir_inactivos:
        q = q.eq("activo", True)
    rows = q.execute().data or []
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for col in ("fecha_inicio", "fecha_fin"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return _attach_subcategoria_df(df, client)


def fetch_panel(client: Client, incluir_inactivos: bool = False) -> pd.DataFrame:
    from src.data_cache import fetch_panel_cached, user_cache_key

    return fetch_panel_cached(incluir_inactivos, user_cache_key())


def hoy_ar() -> date:
    return datetime.now(TZ_AR).date()


def parse_hora(value: object | None) -> time | None:
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value
    s = str(value).strip()
    if not s or s.lower() in ("none", "nan", "nat"):
        return None
    parts = s.split(":")
    if len(parts) < 2:
        return None
    try:
        return time(int(parts[0]), int(parts[1]))
    except ValueError:
        return None


def format_hora_db(value: time | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%H:%M:%S")


def _hora_sort_key(value: object) -> tuple[int, str]:
    if value is None or (isinstance(value, float) and value != value):
        return (1, "99:99:99")
    s = str(value).strip()
    if not s or s.lower() in ("none", "nan", "nat"):
        return (1, "99:99:99")
    return (0, s[:8])


def _agenda_base(df: pd.DataFrame, incluir_inactivos: bool) -> pd.DataFrame:
    if df.empty or "categoria" not in df.columns:
        return df.iloc[0:0]
    out = df[df["categoria"] == AGENDA_CATEGORIA].copy()
    if not incluir_inactivos and "activo" in out.columns:
        out = out[out["activo"].astype(bool)]
    return out


def sort_agenda_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "hora_inicio" in out.columns:
        out["_sort_hora"] = out["hora_inicio"].apply(_hora_sort_key)
    else:
        out["_sort_hora"] = [(1, "99:99:99")] * len(out)
    out = out.sort_values(by=["_sort_hora", "titulo"], ascending=[True, True])
    return out.drop(columns=["_sort_hora"])


def fetch_agenda_dia(
    client: Client,
    dia: date,
    incluir_inactivos: bool = False,
) -> pd.DataFrame:
    df = _agenda_base(fetch_panel(client, incluir_inactivos=True), incluir_inactivos)
    if df.empty or "fecha_inicio" not in df.columns:
        return df.iloc[0:0]
    fechas = df["fecha_inicio"].dt.date
    return sort_agenda_df(df[fechas == dia])


def fetch_agenda_sin_fecha(client: Client, incluir_inactivos: bool = False) -> pd.DataFrame:
    df = _agenda_base(fetch_panel(client, incluir_inactivos=True), incluir_inactivos)
    if df.empty or "fecha_inicio" not in df.columns:
        return df.iloc[0:0]
    return sort_agenda_df(df[df["fecha_inicio"].isna()])


def fetch_agenda_todos(client: Client, incluir_inactivos: bool = False) -> pd.DataFrame:
    df = _agenda_base(fetch_panel(client, incluir_inactivos=True), incluir_inactivos)
    if df.empty:
        return df
    out = df.copy()
    if "hora_inicio" in out.columns:
        out["_sort_hora"] = out["hora_inicio"].apply(_hora_sort_key)
    else:
        out["_sort_hora"] = [(1, "99:99:99")] * len(out)
    out = out.sort_values(
        by=["fecha_inicio", "_sort_hora", "titulo"],
        ascending=[True, True, True],
        na_position="last",
    )
    return out.drop(columns=["_sort_hora"])


AVANCE_NIVELES = (0, 25, 50, 75, 100)

AVANCE_DESDE_ESTADO = {
    "Sin iniciar": 0,
    "En curso": 25,
    "Demorado": 25,
    "Iniciado": 50,
    "Completado": 100,
}


def avance_desde_estado(nombre: str | None) -> int:
    if not nombre:
        return 0
    return AVANCE_DESDE_ESTADO.get(nombre.strip(), 0)


def normalizar_avance(val: int | None) -> int:
    if val is None:
        return 0
    try:
        v = int(val)
    except (TypeError, ValueError):
        return 0
    if v in AVANCE_NIVELES:
        return v
    return min(AVANCE_NIVELES, key=lambda x: abs(x - v))


def fetch_lineas(client: Client, compromiso_id: str) -> list[dict]:
    rows = (
        client.table("compromiso_lineas")
        .select("*, estados(nombre, color)")
        .eq("compromiso_id", compromiso_id)
        .order("orden")
        .execute()
        .data
        or []
    )
    return rows


def fetch_compromiso(client: Client, compromiso_id: str) -> dict | None:
    rows = (
        client.table("panel_base")
        .select("*")
        .eq("id", compromiso_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return _attach_subcategoria_row(rows[0], client) if rows else None


def compute_kpis(df: pd.DataFrame) -> dict[str, int]:
    if df.empty:
        return {"total": 0, "urgente_altas": 0, "demorados": 0, "completados": 0}
    pri = df["prioridad"].str.lower()
    urgente_altas = df[pri.str.contains("urgent|alta", na=False)].shape[0]
    completados = df[df["avance_pct"] >= 100].shape[0]
    if "tiene_demorado" in df.columns:
        demorados = df[df["tiene_demorado"].fillna(False).astype(bool)].shape[0]
    elif "estado_display" in df.columns:
        demorados = df[df["estado_display"].astype(str).str.lower().eq("demorado")].shape[0]
    else:
        today = pd.Timestamp(date.today())
        demorados = df[
            (df["fecha_fin"].notna())
            & (df["fecha_fin"] < today)
            & (df["avance_pct"] < 100)
        ].shape[0]
    return {
        "total": len(df),
        "urgente_altas": int(urgente_altas),
        "demorados": int(demorados),
        "completados": int(completados),
    }


SEARCH_COLUMNS = (
    "titulo",
    "ubicacion_display",
    "categoria",
    "subcategoria",
    "ambito",
    "prioridad",
    "estado_display",
)

SORT_OPTIONS = {
    "Prioridad (urgente primero)": ("prioridad", True),
    "Prioridad (baja primero)": ("prioridad", False),
    "Avance (menor primero)": ("avance_pct", True),
    "Avance (mayor primero)": ("avance_pct", False),
    "Fecha inicio (más reciente)": ("fecha_inicio", False),
    "Fecha inicio (más antigua)": ("fecha_inicio", True),
    "Título (A → Z)": ("titulo", True),
    "Título (Z → A)": ("titulo", False),
    "Categoría (A → Z)": ("categoria", True),
    "Establecimiento (A → Z)": ("ubicacion_display", True),
}

_PRIORIDAD_ORDEN = {"Urgente": 0, "Alta": 1, "Media": 2, "Baja": 3}


def filter_search(df: pd.DataFrame, query: str) -> pd.DataFrame:
    q = (query or "").strip().lower()
    if not q or df.empty:
        return df
    mask = df.apply(
        lambda r: q in " ".join(str(r.get(c, "")) for c in SEARCH_COLUMNS).lower(),
        axis=1,
    )
    return df[mask]


def sort_panel(df: pd.DataFrame, sort_label: str) -> pd.DataFrame:
    if df.empty:
        return df
    field, ascending = SORT_OPTIONS.get(sort_label, ("prioridad", True))
    out = df.copy()
    if field == "prioridad":
        out["_sort_pri"] = out["prioridad"].map(_PRIORIDAD_ORDEN).fillna(99)
        return out.sort_values("_sort_pri", ascending=ascending).drop(columns="_sort_pri")
    if field in ("fecha_inicio", "avance_pct", "titulo", "categoria", "ubicacion_display"):
        return out.sort_values(field, ascending=ascending, na_position="last")
    return out


def apply_filters(
    df: pd.DataFrame,
    *,
    establecimiento: str | None = None,
    ambito: str | None = None,
    categoria: str | None = None,
    prioridad: str | None = None,
    anio: int | None = None,
    mes: int | None = None,
    solo_ministerial: bool = False,
) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if solo_ministerial:
        out = out[out["establecimiento_id"].isna()]
    if establecimiento and establecimiento != "Todos":
        if establecimiento == "Ministerio de Salud (sin sede)":
            out = out[out["establecimiento_id"].isna()]
        else:
            out = out[out["ubicacion_display"] == establecimiento]
    if ambito and ambito != "Todos":
        out = out[out["ambito"] == ambito]
    if categoria and categoria != "Todos":
        out = out[out["categoria"] == categoria]
    if prioridad and prioridad != "Todos":
        out = out[out["prioridad"] == prioridad]
    if anio:
        out = out[out["fecha_inicio"].dt.year == anio]
    if mes:
        out = out[out["fecha_inicio"].dt.month == mes]
    return out


def filter_by_lens(df: pd.DataFrame, lens: str, label: str) -> pd.DataFrame:
    if lens == "Avance":
        pct = int(label.replace("%", "")) if label.endswith("%") else 0
        return df[df["avance_pct"] == pct]
    col_map = {
        "Categoría": "categoria",
        "Ámbito": "ambito",
        "Establecimiento": "ubicacion_display",
        "Prioridad": "prioridad",
    }
    if lens == "Mes / Año":
        tmp = df.copy()
        tmp["_lbl"] = tmp["fecha_inicio"].dt.strftime("%Y-%m").fillna("Sin fecha")
        return tmp[tmp["_lbl"] == label]
    col = col_map.get(lens)
    if col:
        return df[df[col] == label]
    return df


def aggregate_lens(df: pd.DataFrame, lens: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["label", "count"])
    col_map = {
        "Categoría": "categoria",
        "Ámbito": "ambito",
        "Establecimiento": "ubicacion_display",
        "Prioridad": "prioridad",
    }
    col = col_map.get(lens, "categoria")
    if lens == "Avance":
        bins = pd.cut(
            df["avance_pct"].fillna(0),
            bins=[-1, 0, 25, 50, 75, 100],
            labels=["0%", "25%", "50%", "75%", "100%"],
        )
        agg = bins.value_counts().reset_index()
        agg.columns = ["label", "count"]
        return agg.sort_values("count", ascending=True)
    if lens == "Mes / Año" and "fecha_inicio" in df.columns:
        df = df.copy()
        df["label"] = df["fecha_inicio"].dt.strftime("%Y-%m").fillna("Sin fecha")
        agg = df.groupby("label").size().reset_index(name="count")
        return agg.sort_values("label")
    agg = df.groupby(col).size().reset_index(name="count")
    agg = agg.rename(columns={col: "label"})
    return agg.sort_values("count", ascending=True)


def save_compromiso(
    client: Client,
    master: dict,
    lineas: list[dict],
    compromiso_id: str | None = None,
) -> str:
    user_id = st.session_state.get("user_id")
    if compromiso_id:
        client.table("compromisos").update(master).eq("id", compromiso_id).execute()
        client.table("compromiso_lineas").delete().eq("compromiso_id", compromiso_id).execute()
        cid = compromiso_id
    else:
        master["created_by"] = user_id
        res = client.table("compromisos").insert(master).execute()
        cid = res.data[0]["id"]

    for i, linea in enumerate(lineas):
        payload = {
            "compromiso_id": cid,
            "descripcion": linea["descripcion"],
            "estado_id": linea["estado_id"],
            "avance_pct": normalizar_avance(linea.get("avance_pct")),
            "orden": i,
            "notas": linea.get("notas"),
        }
        client.table("compromiso_lineas").insert(payload).execute()
    from src.data_cache import invalidate_data_cache

    invalidate_data_cache()
    return cid


def delete_compromiso(client: Client, compromiso_id: str) -> None:
    client.table("compromisos").delete().eq("id", compromiso_id).execute()
    from src.data_cache import invalidate_data_cache

    invalidate_data_cache()
