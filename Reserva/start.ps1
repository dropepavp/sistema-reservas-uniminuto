# PowerShell helper para iniciar el proyecto localmente
# Ejecútalo desde la raíz del repositorio:
#   PS> .\start.ps1

# 1. crear/activar virtualenv
if (-not (Test-Path -Path .venv)) {
    python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1

# 2. instalar dependencias
pip install -r requirements.txt

# 3. asegurar que PostgreSQL esté corriendo y fijar URL si es necesario
if (-not $env:DATABASE_URL) {
    Write-Host "DATABASE_URL no definida; se usará el valor por defecto" -ForegroundColor Yellow
    $env:DATABASE_URL = "postgresql://postgres:Allison2023secure@localhost:5432/sistema_reserva"
} else {
    Write-Host "DATABASE_URL ya está definida (primeros 60): $($env:DATABASE_URL.Substring(0,[Math]::Min(60,$env:DATABASE_URL.Length)))..."
}

# corregir errores típicos de escritura en la URL
if ($env:DATABASE_URL -match '^postgresql\.') {
    Write-Host "⚠️  Se detectó 'postgresql.' en lugar del esquema correcto 'postgresql://'" -ForegroundColor Yellow
    $env:DATABASE_URL = $env:DATABASE_URL -replace '^postgresql\.', 'postgresql://'
    Write-Host "   URL corregida automáticamente: $env:DATABASE_URL"
}
if ($env:DATABASE_URL -notmatch '^postgresql://') {
    Write-Host "⚠️  La URL de la base no comienza con 'postgresql://'" -ForegroundColor Yellow
}

# advertir si el password podría necesitar codificación
if ($env:DATABASE_URL -match 'postgresql://[^:]+:([^@]+)@') {
    $pwd = $matches[1]
    if ($pwd -match '[@:#%?/]') {
        Write-Host "⚠️  La contraseña en DATABASE_URL contiene caracteres especiales." -ForegroundColor Yellow
        Write-Host "    Use gen_database_url.py para generar una URL codificada o codifique manualmente." -ForegroundColor Yellow
    }
}

# 4. lanzar el servidor (sanitización incluida en run scripts)
python run_with_postgres.py
