# Backup rápido de Supabase — TIEM
# Uso: .\backups\backup_db.ps1
#
# Requisito (una sola vez): SUPABASE_DB_URL en .streamlit\secrets.toml
# Ver backups\README.md

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "No se encontró .venv. Creá el entorno e instalá dependencias:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\Activate.ps1"
    Write-Host "  pip install -r requirements.txt psycopg2-binary"
    exit 1
}

& $Python -m pip install -q psycopg2-binary 2>$null
& $Python backups/backup_db.py @args
