"""
Script para migrar todas las tablas y datos desde PostgreSQL local a Neon PostgreSQL.
"""
import sys
import os

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine

LOCAL_URL = "postgresql://postgres:Allison2023secure@localhost:5432/sistema_reserva"
NEON_URL = "postgresql://neondb_owner:npg_gfN7lxKRrp3X@ep-lively-king-acufthob-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require"

def main():
    print("=" * 60)
    print("INICIANDO MIGRACIÓN: Local PostgreSQL -> Neon PostgreSQL")
    print("=" * 60)

    # 1. Probar conexiones
    print("\n1. Conectando a PostgreSQL Local...")
    try:
        conn_local = psycopg2.connect(LOCAL_URL)
        print("   -> Conexión local EXITOSA.")
    except Exception as e:
        print(f"   [ERROR] No se pudo conectar a PostgreSQL local: {e}")
        return

    print("2. Conectando a Neon PostgreSQL...")
    try:
        conn_neon = psycopg2.connect(NEON_URL)
        print("   -> Conexión Neon EXITOSA.")
    except Exception as e:
        print(f"   [ERROR] No se pudo conectar a Neon: {e}")
        return

    # 2. Inicializar esquema en Neon usando SQLAlchemy models
    print("\n3. Creando tablas en Neon mediante modelos SQLAlchemy...")
    from extensions import db, Base
    from app import create_app
    import database  # Carga todos los modelos

    neon_engine = create_engine(NEON_URL)
    with neon_engine.begin() as conn:
        Base.metadata.create_all(conn)
    print("   -> Esquema y tablas creadas exitosamente en Neon.")

    # 3. Obtener orden de tablas para respetar claves foráneas
    # Orden de inserción respetando dependencias
    table_order = [
        'sedes',
        'ubicaciones',
        'recursos',
        'bodegas',
        'categorias_inventario',
        'inventario',
        'auxiliares',
        'auxiliar_sedes',
        'programas_academicos',
        'estudiantes',
        'profesores',
        'prestamos_equipos',
        'reservas',
        'clases_salas_computo',
        'permisos_usuarios',
        'auditorias',
        'festivos',
        'colaboradores',
        'horarios_colaboradores',
        'tareas_colaboradores',
        'permisos_colaboradores',
        'puestos_computo',
        'software_salas',
        'software_asignado_salas',
        'novedades_tecnicas_salas',
        'mantenimientos_inventario',
        'practicas_libres'
    ]

    cur_local = conn_local.cursor(cursor_factory=RealDictCursor)
    cur_neon = conn_neon.cursor()

    print("\n4. Transfiriendo registros tabla por tabla...")
    total_migrados = 0

    for table in table_order:
        try:
            # Verificar si la tabla existe en local
            cur_local.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')")
            if not cur_local.fetchone()['exists']:
                print(f"   [-] Tabla '{table}' no existe en local (omitida).")
                continue

            cur_local.execute(f'SELECT * FROM "{table}"')
            rows = cur_local.fetchall()
            count = len(rows)

            if count == 0:
                print(f"   [0] Tabla '{table}': 0 registros.")
                continue

            # Obtener columnas
            columns = list(rows[0].keys())
            cols_str = ', '.join([f'"{c}"' for c in columns])
            vals_str = ', '.join(['%s'] * len(columns))
            
            # Limpiar tabla en Neon antes de insertar para evitar duplicados
            cur_neon.execute(f'TRUNCATE TABLE "{table}" CASCADE')

            insert_sql = f'INSERT INTO "{table}" ({cols_str}) VALUES ({vals_str})'
            for r in rows:
                values = [r[c] for c in columns]
                cur_neon.execute(insert_sql, values)

            conn_neon.commit()
            print(f"   [✓] Tabla '{table}': {count} registros transferidos.")
            total_migrados += count
        except Exception as e:
            conn_neon.rollback()
            print(f"   [!] Error migrando tabla '{table}': {e}")

    conn_local.close()
    conn_neon.close()

    print("\n" + "=" * 60)
    print(f"MIGRACIÓN COMPLETADA: {total_migrados} registros transferidos a Neon!")
    print("=" * 60)

if __name__ == '__main__':
    main()
