# Restaura un backup .sql en Supabase PostgreSQL (TIEM)
#
# Requisitos:
#   - psql instalado (PostgreSQL client) O usar el SQL Editor de Supabase
#   - SUPABASE_DB_URL en .streamlit/secrets.toml o variable de entorno
#
# Uso:
#   .\backups\restore_db.ps1
#   .\backups\restore_db.ps1 -BackupFile .\backups\backup_20260908_120000.sql

param(
    [string]$BackupFile = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackupsDir = Join-Path $Root "backups"
$SecretsFile = Join-Path $Root ".streamlit\secrets.toml"

function Get-DbUrl {
    if ($env:SUPABASE_DB_URL) { return $env:SUPABASE_DB_URL.Trim() }
    if ($env:DATABASE_URL) { return $env:DATABASE_URL.Trim() }
    if (-not (Test-Path $SecretsFile)) {
        throw "No se encontró $SecretsFile"
    }
    $text = Get-Content $SecretsFile -Raw
    if ($text -match 'SUPABASE_DB_URL\s*=\s*"([^"]+)"') { return $Matches[1] }
    if ($text -match 'DATABASE_URL\s*=\s*"([^"]+)"') { return $Matches[1] }
    $pwd = $null
    $base = $null
    if ($text -match 'SUPABASE_DB_PASSWORD\s*=\s*"([^"]+)"') { $pwd = $Matches[1] }
    if ($text -match 'SUPABASE_URL\s*=\s*"([^"]+)"') { $base = $Matches[1] }
    if ($pwd -and $base -match 'https?://([^.]+)\.supabase\.co') {
        $ref = $Matches[1]
        $enc = [uri]::EscapeDataString($pwd)
        return "postgresql://postgres:${enc}@db.${ref}.supabase.co:5432/postgres"
    }
    throw "Agregá SUPABASE_DB_PASSWORD en secrets.toml (o SUPABASE_DB_URL). Ver backups\README.md"
}

if (-not $BackupFile) {
    $latest = Get-ChildItem -Path $BackupsDir -Filter "backup_*.sql" |
        Where-Object { $_.Name -ne "backup_latest.sql" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $latest) {
        throw "No hay archivos backup_*.sql en backups/. Ejecutá primero: python backups/backup_db.py"
    }
    $BackupFile = $latest.FullName
}

if (-not (Test-Path $BackupFile)) {
    throw "No existe el archivo: $BackupFile"
}

$dbUrl = Get-DbUrl
$psql = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psql) {
    Write-Host ""
    Write-Host "psql no está en el PATH." -ForegroundColor Yellow
    Write-Host "Alternativa manual:" -ForegroundColor Yellow
    Write-Host "  1. Supabase → SQL Editor"
    Write-Host "  2. Abrí el archivo: $BackupFile"
    Write-Host "  3. Pegá el contenido y ejecutá (preferible en un proyecto de prueba primero)."
    Write-Host ""
    exit 1
}

Write-Host "Restaurando: $BackupFile"
Write-Host "Destino: Supabase (public)"
$confirm = Read-Host "¿Continuar? Esto puede SOBRESCRIBIR datos. (s/N)"
if ($confirm -notin @("s", "S", "si", "Si", "SI")) {
    Write-Host "Cancelado."
    exit 0
}

& psql $dbUrl -v ON_ERROR_STOP=1 -f $BackupFile
Write-Host "Restauración finalizada." -ForegroundColor Green
