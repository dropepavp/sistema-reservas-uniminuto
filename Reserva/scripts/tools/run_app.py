#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher para ejecutar app_improved.py con la configuración correcta.
"""
import os
import sys

# Configurar DATABASE_URL ANTES de cualquier importación
os.environ.setdefault('DATABASE_URL',
                      'postgresql://postgres:Allison2023secure@localhost:5432/sistema_reserva')
# si se proporcionó la variable con caracteres especiales, limpiarla
try:
    from config import sanitize_database_url
    os.environ['DATABASE_URL'] = sanitize_database_url(os.environ['DATABASE_URL'])
except ImportError:
    # en caso de que config.py cambie radicalmente, ignore
    pass

os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('FLASK_CONFIG', 'development')

# Ahora importar y ejecutar
if __name__ == '__main__':
    try:
        from app_improved import create_app
        print("[*] Creando aplicación...")
        app = create_app()
        print("[✓] Aplicación creada exitosamente.")
        print("\n" + "="*60)
        print("🚀 Iniciando servidor Flask en http://127.0.0.1:5000")
        print("="*60 + "\n")
        print("Presiona CTRL+C para detener.\n")
        app.run(debug=True, host='127.0.0.1', port=5000)
    except Exception as e:
        print(f"[✗] ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
