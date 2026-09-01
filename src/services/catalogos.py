from __future__ import annotations

import streamlit as st
from supabase import Client


def _table(client: Client, name: str, order: str = "nombre") -> list[dict]:
    return client.table(name).select("*").order(order).execute().data or []


def _table_establecimientos(client: Client) -> list[dict]:
    rows = (
        client.table("establecimientos")
        .select("id, nombre, localidad_id, codigo_sisa, localidades(nombre)")
        .order("nombre")
        .execute()
        .data
        or []
    )
    for row in rows:
        loc = (row.get("localidades") or {}).get("nombre")
        row["display"] = f"{row['nombre']} ({loc})" if loc else row["nombre"]
    return rows


def _load_catalogos_impl(client: Client) -> dict[str, list[dict]]:
    return {
        "reparticiones": _table(client, "reparticiones"),
        "localidades": _table(client, "localidades"),
        "establecimientos": _table_establecimientos(client),
        "servicios": _table(client, "servicios"),
        "areas": _table(client, "areas"),
        "categorias": _table(client, "categorias"),
        "prioridades": client.table("prioridades").select("*").order("orden").execute().data or [],
        "estados": client.table("estados").select("*").order("peso_avance").execute().data or [],
        "ambitos": _table(client, "ambitos"),
    }


def load_catalogos(client: Client) -> dict[str, list[dict]]:
    from src.data_cache import load_catalogos_cached, user_cache_key

    return load_catalogos_cached(user_cache_key())


def _fetch_subcategorias_impl(client: Client, categoria_id: str | None) -> list[dict]:
    if not categoria_id:
        return []
    return (
        client.table("subcategorias")
        .select("*")
        .eq("categoria_id", categoria_id)
        .order("nombre")
        .execute()
        .data
        or []
    )


def fetch_subcategorias(client: Client, categoria_id: str | None) -> list[dict]:
    from src.data_cache import fetch_subcategorias_cached, user_cache_key

    return fetch_subcategorias_cached(categoria_id, user_cache_key())


def establecimientos_por_localidad(
    establecimientos: list[dict],
    localidad_id: str | None,
) -> list[dict]:
    """Establecimientos de una localidad; sin localidad devuelve todos."""
    if not localidad_id:
        return establecimientos
    return [row for row in establecimientos if row.get("localidad_id") == localidad_id]


def catalogo_map(items: list[dict], include_empty: bool = True) -> dict[str, str]:
    m = {}
    if include_empty:
        m[""] = "—"
    for item in items:
        label = item.get("display") or item["nombre"]
        m[item["id"]] = label
    return m


def nombre_por_id(items: list[dict], item_id: str | None) -> str:
    if not item_id:
        return ""
    for item in items:
        if item["id"] == item_id:
            return item["nombre"]
    return ""


def id_por_nombre(items: list[dict], nombre: str) -> str | None:
    for item in items:
        if item["nombre"] == nombre:
            return item["id"]
    return None


def resolve_ambito_id(
    categorias: list[dict],
    subcategorias: list[dict],
    categoria_id: str | None,
    subcategoria_id: str | None = None,
) -> str | None:
    if subcategoria_id:
        for sub in subcategorias:
            if sub.get("id") == subcategoria_id and sub.get("ambito_id"):
                return sub["ambito_id"]
    if categoria_id:
        for cat in categorias:
            if cat.get("id") == categoria_id and cat.get("ambito_id"):
                return cat["ambito_id"]
    return None
