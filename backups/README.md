# Backups — TIEM / Supabase

## ¿Por qué falla `db....supabase.co` en Windows?

La conexión **directa** (`db.tu-proyecto.supabase.co`) en plan gratuito suele ser **solo IPv6**. Muchas PCs en Windows no la resuelven → error *"could not translate host name"*.

**Solución:** usar el **Session pooler** (IPv4), que Supabase muestra en **Database → Connect**.

---

## Configuración (elegí una)

### Opción A — Contraseña + región

```toml
SUPABASE_DB_PASSWORD = "tu-contraseña"
SUPABASE_DB_REGION = "sa-east-1"
```

La **región** aparece en la URI del panel Connect, por ejemplo:
`aws-0-**sa-east-1**.pooler.supabase.com`

Contraseña: **Database** → **Database password**

### Opción B — URI completa (más confiable)

1. Supabase → **Project Settings** → **Database** → **Connect**
2. Elegí **Session pooler** (puerto **5432**)
3. Copiá la URI y pegala en secrets:

```toml
SUPABASE_DB_URL = "postgresql://postgres.[ref]:[password]@aws-0-sa-east-1.pooler.supabase.com:5432/postgres"
```

---

## Probar conexión

```powershell
python backups/backup_db.py --test
```

---

## Hacer backup

```powershell
.\backups\backup_db.ps1
```

Genera `backups/backup_YYYYMMDD_HHMMSS.sql`.

---

## Restaurar

```powershell
.\backups\restore_db.ps1
```

O manual: `restore_db.sql` + SQL Editor de Supabase.
