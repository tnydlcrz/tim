# Tablero de Compromisos — TIM Salud

App **Streamlit + Supabase** para gestión de compromisos del Ministerio de Salud.

- **Asistente:** carga maestro-detalle (prioridad en cabecera, avance por línea).
- **Ejecutivo:** tablero multi-criterio con drill-down, KPIs y diseño institucional.

## Requisitos

- Python 3.11+
- Proyecto [Supabase](https://supabase.com) (plan gratuito)
- Cuenta [Streamlit Community Cloud](https://streamlit.io/cloud) (opcional, para publicar)

## 1. Configurar Supabase

1. Crear proyecto en Supabase.
2. En **SQL Editor**, ejecutar en orden:
   - [`db/schema.sql`](db/schema.sql)
   - [`db/seed.sql`](db/seed.sql)
3. En **Authentication → Users**, crear 2 usuarios (email + contraseña):
   - `asistente@...`
   - `ejecutivo@...`
4. Asignar roles en **SQL Editor**:

```sql
UPDATE profiles SET rol = 'asistente', nombre = 'Asistente'
WHERE email = 'asistente@TU_DOMINIO.com';

UPDATE profiles SET rol = 'ejecutivo', nombre = 'Ejecutivo'
WHERE email = 'ejecutivo@TU_DOMINIO.com';
```

5. Copiar **Project URL** y **anon public key** desde Settings → API.

## 2. Ejecutar localmente

```bash
cd TIEM
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Copiar secrets:

```bash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

Editar `.streamlit/secrets.toml` con tus claves Supabase.

```bash
streamlit run app.py
```

## 3. Publicar en Streamlit Cloud

1. Subir el repo a GitHub.
2. En [share.streamlit.io](https://share.streamlit.io) → New app → seleccionar repo y `app.py`.
3. En **Secrets**, pegar:

```toml
SUPABASE_URL = "https://xxx.supabase.co"
SUPABASE_ANON_KEY = "eyJ..."
```

4. Deploy. Solo los usuarios creados en Supabase Auth podrán iniciar sesión.

## Modelo de datos

| Tabla | Rol |
|---|---|
| `compromisos` | Maestro: título, ubicación, categoría, **prioridad**, ámbito |
| `compromiso_lineas` | Detalle: descripción + **estado** (avance por ítem) |
| Vista `panel_base` | Tablero ejecutivo con `avance_pct` prorrateado |

**Avance del compromiso** = promedio de `estados.peso_avance` de sus líneas.

## Migrar datos del Google Sheet

### Establecimientos y localidades (Ministerio de Salud)

1. En el Google Sheet, exportá la pestaña **`organismos`** como CSV → `data/organismos.csv`  
   (columnas esperadas: `reparticion`, `localidad`, `establecimiento`, `codigo_sisa`; filtramos Ministerio de Salud).
2. Generá el SQL:

```bash
python scripts/generate_establecimientos_sql.py
# o: python scripts/generate_establecimientos_sql.py --organismos ruta/organismos.csv
```

3. Ejecutá `db/migration_establecimientos.sql` en Supabase → SQL Editor.

Si aún no tenés `organismos.csv`, el script usa los pares únicos de `data/incidencias.csv` como respaldo.

### Compromisos (incidencias)

Exportar pestaña `incidencias` como CSV y ejecutar:

```bash
python scripts/seed_from_sheet.py --csv ruta/incidencias.csv
```

(Requiere `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` en variables de entorno para carga masiva.)

## Estructura

```
app.py                  # Entry point
db/schema.sql           # Tablas, vistas, RLS
db/seed.sql             # Catálogos + datos demo
src/views/asistente/    # Formulario y listado
src/views/ejecutivo/    # Tablero drill-down
assets/styles.css       # Tema institucional
```
