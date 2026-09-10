"""
Backup de la base Supabase (PostgreSQL) del proyecto TIEM.

Genera un archivo .sql en esta carpeta con esquema public + datos.

Configuración en .streamlit/secrets.toml (elegí una):

  Opción A — contraseña + región (recomendado en Windows):
    SUPABASE_DB_PASSWORD = "..."
    SUPABASE_DB_REGION = "sa-east-1"   # ver en Supabase → Database → Connect

  Opción B — URI copiada del panel Connect (Session o Direct):
    SUPABASE_DB_URL = "postgresql://postgres.[ref]:...@aws-0-....pooler.supabase.com:5432/postgres"

Uso:
  python backups/backup_db.py
  python backups/backup_db.py --test
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent.parent
BACKUPS_DIR = Path(__file__).resolve().parent
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"

DATA_TABLES = [
    "ambitos",
    "prioridades",
    "estados",
    "reparticiones",
    "localidades",
    "servicios",
    "areas",
    "categorias",
    "establecimientos",
    "subcategorias",
    "profiles",
    "compromisos",
    "compromiso_lineas",
]

# Regiones frecuentes si no indicás SUPABASE_DB_REGION (se prueban en orden)
DEFAULT_REGIONS = (
    "sa-east-1",
    "us-east-1",
    "us-west-1",
    "eu-west-1",
    "eu-central-1",
)


def _normalize_db_url(url: str) -> str:
    url = url.strip().strip('"').strip("'")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    return url


def _project_ref_from_supabase_url(url: str) -> str | None:
    url = url.strip().rstrip("/")
    m = re.search(r"https?://([^.]+)\.supabase\.co", url)
    return m.group(1) if m else None


def _read_secrets_text() -> str:
    if SECRETS_PATH.exists():
        return SECRETS_PATH.read_text(encoding="utf-8")
    return ""


def _secret_value(text: str, key: str) -> str | None:
    m = re.search(rf'{key}\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else None


def _env_or_secret(text: str, key: str) -> str | None:
    return os.environ.get(key) or _secret_value(text, key)


def _pooler_url(ref: str, password: str, region: str, port: int, *, aws0: bool = True) -> str:
    host = f"aws-0-{region}.pooler.supabase.com" if aws0 else f"aws-{region}.pooler.supabase.com"
    user = f"postgres.{ref}"
    pwd = quote_plus(password)
    return f"postgresql://{user}:{pwd}@{host}:{port}/postgres"


def _direct_url(ref: str, password: str) -> str:
    pwd = quote_plus(password)
    return f"postgresql://postgres:{pwd}@db.{ref}.supabase.co:5432/postgres"


def build_connection_candidates() -> list[tuple[str, str]]:
    text = _read_secrets_text()

    for key in ("SUPABASE_DB_URL", "DATABASE_URL"):
        val = _env_or_secret(text, key)
        if val:
            url = _normalize_db_url(val)
            return [("URI configurada", url)]

    password = _env_or_secret(text, "SUPABASE_DB_PASSWORD")
    supabase_url = _env_or_secret(text, "SUPABASE_URL")
    if not password or not supabase_url:
        raise SystemExit(
            "Falta configuración para conectar a PostgreSQL.\n\n"
            "Opción A — agregá en .streamlit/secrets.toml:\n"
            '  SUPABASE_DB_PASSWORD = "tu-contraseña"\n'
            '  SUPABASE_DB_REGION = "sa-east-1"\n'
            "  (La región aparece en Supabase → Database → Connect → Session pooler)\n\n"
            "Opción B — pegá la URI completa del panel Connect:\n"
            '  SUPABASE_DB_URL = "postgresql://..."\n\n'
            "Nota: SUPABASE_URL de la app NO sirve para backup; es la API HTTP."
        )

    ref = _project_ref_from_supabase_url(supabase_url)
    if not ref:
        raise SystemExit("No se pudo obtener el project ref desde SUPABASE_URL.")

    region = _env_or_secret(text, "SUPABASE_DB_REGION")
    regions = [region] if region else list(DEFAULT_REGIONS)

    candidates: list[tuple[str, str]] = []
    for reg in regions:
        candidates.append((f"Pooler session (5432) {reg}", _pooler_url(ref, password, reg, 5432, aws0=True)))
        candidates.append((f"Pooler session (5432) {reg} alt", _pooler_url(ref, password, reg, 5432, aws0=False)))
    candidates.append(("Direct db.* (IPv6)", _direct_url(ref, password)))
    return candidates


def connect_db(candidates: list[tuple[str, str]]):
    try:
        import psycopg2
    except ImportError as exc:
        raise SystemExit("pip install psycopg2-binary") from exc

    errors: list[str] = []
    for label, url in candidates:
        try:
            conn = psycopg2.connect(url, connect_timeout=15)
            print(f"Conectado ({label})")
            return conn, url
        except Exception as exc:
            errors.append(f"  • {label}: {exc}")

    raise SystemExit(
        "No se pudo conectar a Supabase PostgreSQL.\n\n"
        + "\n".join(errors)
        + "\n\nSolución recomendada en Windows:\n"
        "  1. Supabase → Project Settings → Database → Connect\n"
        "  2. Elegí **Session pooler** (puerto 5432)\n"
        "  3. Copiá la URI completa en secrets.toml como SUPABASE_DB_URL\n"
        "     (y comentá o borrá SUPABASE_DB_PASSWORD si usás la URI)\n"
    )


def default_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return BACKUPS_DIR / f"backup_{stamp}.sql"


def backup_with_pg_dump(db_url: str, output: Path) -> None:
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise FileNotFoundError("pg_dump no está instalado o no está en el PATH")

    cmd = [
        pg_dump,
        db_url,
        "--schema=public",
        "--no-owner",
        "--no-acl",
        "--format=plain",
        f"--file={output}",
    ]
    subprocess.run(cmd, check=True)


def backup_with_psycopg2(conn, output: Path) -> None:
    from psycopg2 import sql

    conn.autocommit = True

    lines: list[str] = [
        "-- TIEM · Backup generado con backups/backup_db.py",
        f"-- Fecha UTC: {datetime.now(timezone.utc).isoformat()}",
        "BEGIN;",
        "SET session_replication_role = replica;",
        "",
    ]

    with conn.cursor() as cur:
        for table in DATA_TABLES:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = %s
                )
                """,
                (table,),
            )
            if not cur.fetchone()[0]:
                lines.append(f"-- Tabla omitida (no existe): {table}")
                continue

            cur.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table)))
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            lines.append(f"-- {table}: {len(rows)} fila(s)")
            lines.append(f"TRUNCATE TABLE public.{table} CASCADE;")

            if not rows:
                lines.append("")
                continue

            col_list = ", ".join(f'"{c}"' for c in cols)
            for row in rows:
                vals = []
                for v in row:
                    if v is None:
                        vals.append("NULL")
                    elif isinstance(v, bool):
                        vals.append("TRUE" if v else "FALSE")
                    elif isinstance(v, (int, float)):
                        vals.append(str(v))
                    else:
                        s = str(v).replace("'", "''")
                        vals.append(f"'{s}'")
                lines.append(
                    f"INSERT INTO public.{table} ({col_list}) VALUES ({', '.join(vals)});"
                )
            lines.append("")

    lines.extend(["SET session_replication_role = DEFAULT;", "COMMIT;", ""])
    output.write_text("\n".join(lines), encoding="utf-8")
    conn.close()


def write_latest_pointer(output: Path) -> None:
    pointer = BACKUPS_DIR / "backup_latest.sql"
    try:
        pointer.write_text(
            f"-- Apunta al último backup: {output.name}\n"
            f"-- Restaurar: .\\backups\\restore_db.ps1 -BackupFile .\\backups\\{output.name}\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup Supabase → archivo .sql")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--method", choices=("auto", "pg_dump", "psycopg2"), default="auto")
    parser.add_argument("--test", action="store_true", help="Solo probar conexión")
    args = parser.parse_args()

    candidates = build_connection_candidates()
    conn, db_url = connect_db(candidates)

    if args.test:
        conn.close()
        print("Prueba OK. Podés ejecutar el backup sin --test.")
        return

    output = args.output or default_output_path()
    output.parent.mkdir(parents=True, exist_ok=True)

    method = args.method
    if method == "auto":
        method = "pg_dump" if shutil.which("pg_dump") else "psycopg2"

    print(f"Backup → {output}")
    print(f"Método: {method}")

    if method == "pg_dump":
        conn.close()
        try:
            backup_with_pg_dump(db_url, output)
        except FileNotFoundError:
            print("pg_dump no disponible; usando psycopg2…")
            conn, _ = connect_db(candidates)
            backup_with_psycopg2(conn, output)
        except subprocess.CalledProcessError:
            print("pg_dump falló; usando psycopg2…")
            conn, _ = connect_db(candidates)
            backup_with_psycopg2(conn, output)
    else:
        backup_with_psycopg2(conn, output)

    size_kb = output.stat().st_size / 1024
    print(f"Listo: {output.name} ({size_kb:.1f} KB)")
    write_latest_pointer(output)
    print("\nNota: auth.users (logins) no se incluye. Los usuarios siguen en Supabase Auth.")


if __name__ == "__main__":
    main()
