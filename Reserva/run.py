from dotenv import load_dotenv
load_dotenv()

import os
import sys
from sqlalchemy import text

# Asegurar que el directorio del proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# FIX: Establecer codificación a latin1 para evitar UnicodeDecodeError
# cuando PostgreSQL devuelve mensajes de error en español (Windows CP1252) durante la autenticación.
os.environ['PGCLIENTENCODING'] = 'latin1'

# valores predeterminados básicos para facilitar el arranque local
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('FLASK_CONFIG', 'development')

# si hace falta, fijar URL de base de datos y sanitizarla
# Se actualiza la contraseña a 'Allison2.023*' para coincidir con run_with_postgres.py
os.environ.setdefault('DATABASE_URL',
                      'postgresql://postgres:Allison2.023*@localhost:5432/sistema_reserva')

try:
    from config import sanitize_database_url
    os.environ['DATABASE_URL'] = sanitize_database_url(os.environ['DATABASE_URL'])
except ImportError:
    pass

from app import create_app
from database import db

app = create_app()

if __name__ == "__main__":
    # Verificar conexión a la base de datos antes de iniciar
    # Emoji Unicode no soportado por la consola CP1252; usar texto plano.
    print("Verificando conexión a base de datos...")
    with app.app_context():
        try:
            db.session.execute(text('SELECT 1'))
            print("CONEXION A POSTGRESQL EXITOSA.")
        except Exception as e:
            print("ERROR CRITICO: No se pudo conectar a la base de datos.")
            print(f"   Detalle: {e}")
            # Continuar para permitir depuración, aunque la DB falle
            # sys.exit(1)

    # Configuración para correr la aplicación
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    # El modo debug se infiere automáticamente de FLASK_ENV='development',
    # por lo que no es necesario pasarlo a app.run().
    
    print(f"Iniciando servidor en http://127.0.0.1:{port}")
    print(f"   Accesible en la red local en: http://{host}:{port} (si el host es 0.0.0.0)")
    app.run(host=host, port=port)