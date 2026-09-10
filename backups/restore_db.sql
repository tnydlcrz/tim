-- =============================================================================
-- TIEM · Restauración manual de datos (Supabase SQL Editor)
-- =============================================================================
-- Usá este archivo como guía cuando no tengas psql instalado.
--
-- PASOS:
-- 1. Hacé un backup actual:  python backups/backup_db.py
-- 2. Supabase → SQL Editor → New query
-- 3. Abrí el .sql generado (backups/backup_YYYYMMDD_HHMMSS.sql)
-- 4. Copiá TODO el contenido y ejecutalo en el proyecto destino
--
-- IMPORTANTE:
-- - Probá primero en un proyecto Supabase de prueba si podés.
-- - Los usuarios de login (auth.users) NO vienen en el backup de datos.
--   Los perfiles (profiles) referencian esos UUID; deben existir los mismos
--   usuarios en Authentication, o ajustá created_by / profiles manualmente.
-- - Las vistas panel_base y compromisos_con_avance se recrean con db/schema.sql
--   (no hace falta restaurarlas; son vistas, no tablas).
--
-- =============================================================================
-- Opcional: vaciar solo datos de la app (NO borra auth.users)
-- Descomentá y ejecutá ANTES del backup si querés limpiar y volver a cargar.
-- =============================================================================

/*
TRUNCATE TABLE
    public.compromiso_lineas,
    public.compromisos,
    public.profiles,
    public.subcategorias,
    public.establecimientos,
    public.categorias,
    public.areas,
    public.servicios,
    public.localidades,
    public.reparticiones,
    public.estados,
    public.prioridades,
    public.ambitos
RESTART IDENTITY CASCADE;
*/

-- Después de truncar (si aplica), pegá aquí el contenido de backup_*.sql
