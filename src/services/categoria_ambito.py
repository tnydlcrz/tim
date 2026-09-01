"""Relación categoría / subcategoría → ámbito (hoja datos-categoria del Sheet)."""

from __future__ import annotations

import csv
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "datos_categoria.csv"


def load_datos_categoria() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with DATA_PATH.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            cat = (row.get("categoria") or "").strip()
            sub = (row.get("subcategoria") or "").strip()
            amb = (row.get("ambito") or "").strip()
            if cat and amb:
                rows.append({"categoria": cat, "subcategoria": sub, "ambito": amb})
    return rows


def ambito_por_categoria_subcategoria(categoria: str, subcategoria: str | None = None) -> str:
    cat = (categoria or "").strip()
    sub = (subcategoria or "").strip()
    rows = load_datos_categoria()
    if sub:
        for row in rows:
            if row["categoria"] == cat and row["subcategoria"] == sub:
                return row["ambito"]
    for row in rows:
        if row["categoria"] == cat and not row["subcategoria"]:
            return row["ambito"]
    return "Sin clasificar"


def categorias_con_ambito() -> dict[str, str]:
    out: dict[str, str] = {}
    for row in load_datos_categoria():
        if not row["subcategoria"]:
            out[row["categoria"]] = row["ambito"]
    return out


def subcategorias_con_ambito() -> list[tuple[str, str, str]]:
    return [
        (row["categoria"], row["subcategoria"], row["ambito"])
        for row in load_datos_categoria()
        if row["subcategoria"]
    ]
