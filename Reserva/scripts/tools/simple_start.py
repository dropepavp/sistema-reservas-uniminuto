"""
Script simple para iniciar la aplicación con la contraseña correcta
"""
import os
import subprocess
import sys

# Configurar DATABASE_URL con la contraseña CORRECTA
os.environ['DATABASE_URL'] = 'postgresql://postgres:Allison2023secure@127.0.0.1:5432/sistema_reserva'

print("="*60)
print("INICIANDO APLICACIÓN CON CREDENCIALES CORRECTAS")
print("="*60)
print(f"DATABASE_URL: postgresql://postgres:***@127.0.0.1:5432/sistema_reserva")
print(f"Host: 127.0.0.1")
print(f"Database: sistema_reserva")
print(f"User: postgres")
print(f"Password: Allison2023secure")
print("="*60)

# Lanzar run_app.py
result = subprocess.run([sys.executable, 'run_app.py'], env=os.environ.copy())
sys.exit(result.returncode)
