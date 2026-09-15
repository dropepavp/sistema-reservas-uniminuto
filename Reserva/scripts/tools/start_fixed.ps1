# Script para corregir la DATABASE_URL y lanzar la aplicación

# Establecer la DATABASE_URL correcta
$env:DATABASE_URL = "postgresql://postgres:Allison2023secure@127.0.0.1:5432/sistema_reserva"

Write-Host "DATABASE_URL configurada correctamente"
Write-Host "Host: 127.0.0.1"
Write-Host "Password: Allison2023secure"
Write-Host ""

# Activar el virtualenv
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
    Write-Host "✓ Entorno virtual activado"
} else {
    Write-Host "⚠️  No se encontró .venv"
}

# Lanzar la aplicación
Write-Host "Iniciando aplicación..."
python run_app.py
