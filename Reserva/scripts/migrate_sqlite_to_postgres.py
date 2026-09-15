"""
Script de migración: copia datos de `reserva.db` (SQLite) a PostgreSQL usando SQLAlchemy.
Uso:
    python scripts/migrate_sqlite_to_postgres.py

Requisitos: tener `psycopg2-binary` instalado y la variable de entorno `DATABASE_URL`
    p.ej. en PowerShell:
      $env:DATABASE_URL = "postgresql://postgres:Allison2.023*@localhost:5432/sistema_reserva"

El script: crea la base si no existe, crea tablas (según `database.py`) y copia fila por fila.
"""
import os
import sys
import sqlite3
from urllib.parse import urlparse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Rutas
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
SQLITE_PATH = os.path.join(PROJECT_ROOT, 'reserva.db')

# Config
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print('ERROR: la variable de entorno DATABASE_URL no está definida.')
    print('Ejemplo en PowerShell:')
    print('$env:DATABASE_URL = "postgresql://postgres:Allison2.023*@localhost:5432/sistema_reserva"')
    sys.exit(1)

# Helpers

def create_database_if_not_exists(database_url):
    parsed = urlparse(database_url)
    dbname = parsed.path.lstrip('/')
    if not dbname:
        raise ValueError('No se pudo determinar el nombre de la base desde DATABASE_URL')

    # Connect to default postgres database to create the DB
    admin_url = database_url.replace('/' + dbname, '/postgres')
    admin_engine = create_engine(admin_url)
    with admin_engine.connect() as conn:
        exists = conn.exec_driver_sql("select 1 from pg_database where datname = :d", {'d': dbname}).fetchone()
        if not exists:
            print(f"Creando base de datos '{dbname}'...")
            conn.exec_driver_sql('commit')
            conn.exec_driver_sql(text(f"CREATE DATABASE \"{dbname}\""))
            print('Base creada.')
        else:
            print(f"La base '{dbname}' ya existe.")


def run():
    if not os.path.exists(SQLITE_PATH):
        print(f'ERROR: no se encontró {SQLITE_PATH}')
        sys.exit(1)

    print('1) Verificando/creando base PostgreSQL...')
    try:
        create_database_if_not_exists(DATABASE_URL)
    except OperationalError as e:
        print('ERROR conectando a PostgreSQL:', e)
        sys.exit(1)

    # Import app models to create tables
    print('2) Creando tablas via SQLAlchemy (init_db)...')
    sys.path.insert(0, PROJECT_ROOT)
    try:
        from app_improved import create_app
        from database import db, init_db
    except Exception:
        # Fallback a app.py
        from app import app as flask_app
        from database import db, init_db
        flask_app.app_context().push()
        init_db(flask_app)
        print('Tablas creadas (fallback).')
    else:
        app = create_app('development')
        with app.app_context():
            init_db(app)
        print('Tablas creadas.')

    # Conexiones
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    pg_engine = create_engine(DATABASE_URL)

    # Mapear tablas simples: auxiliares, profesores, sedes, bodegas, categorias_inventario, inventario, prestamos_equipos, reservas, permisos_usuarios, auditorias, festivos
    tables = [
        'auxiliares', 'profesores', 'sedes', 'bodegas', 'categorias_inventario',
        'inventario', 'prestamos_equipos', 'reservas', 'permisos_usuarios', 'auditorias', 'festivos'
    ]

    print('3) Iniciando copia de tablas (fila por fila)...')
    with pg_engine.begin() as pg_conn:
        for t in tables:
            try:
                s = sqlite_conn.execute(f'SELECT * FROM {t}')
            except Exception as e:
                print(f'- Tabla {t}: no existe en SQLite o error: {e}')
                continue
            rows = s.fetchall()
            if not rows:
                print(f'- Tabla {t}: sin filas, saltando.')
                continue
            cols = rows[0].keys()
            col_list = ','.join([f'"{c}"' for c in cols])
            placeholders = ','.join([f':{c}' for c in cols])
            insert_sql = text(f'INSERT INTO "{t}" ({col_list}) VALUES ({placeholders})')
            count = 0
            for r in rows:
                params = {c: r[c] for c in cols}
                try:
                    pg_conn.execute(insert_sql, params)
                    count += 1
                except Exception as e:
                    # Mostrar pero no abortar
                    print(f'  ! Error insertando en {t}: {e}')
            print(f'- Tabla {t}: {count} filas copiadas.')

    sqlite_conn.close()
    print('Migración finalizada. Verifica la base en PostgreSQL.')

if __name__ == '__main__':
    run()
