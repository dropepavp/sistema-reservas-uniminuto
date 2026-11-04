"""
Sincronización robusta y completa de esquema y datos desde PostgreSQL local a Neon.
"""
import sys
import os

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

LOCAL_URL = "postgresql://postgres:Allison2023secure@localhost:5432/sistema_reserva"
NEON_URL = "postgresql://neondb_owner:npg_gfN7lxKRrp3X@ep-lively-king-acufthob.sa-east-1.aws.neon.tech/neondb?sslmode=require"

def sync_schema_columns(conn_local, conn_neon, table):
    """Sincroniza columnas faltantes en Neon para que coincidan con la BD local."""
    cur_local = conn_local.cursor()
    cur_neon = conn_neon.cursor()

    cur_local.execute(f"""
        SELECT column_name, data_type, character_maximum_length, is_nullable
        FROM information_schema.columns
        WHERE table_name = '{table}' AND table_schema = 'public'
    """)
    local_cols = {r[0]: r for r in cur_local.fetchall()}

    cur_neon.execute(f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = '{table}' AND table_schema = 'public'
    """)
    neon_cols = set(r[0] for r in cur_neon.fetchall())

    for col_name, (c_name, data_type, max_len, is_null) in local_cols.items():
        if col_name not in neon_cols:
            type_str = data_type
            if max_len:
                type_str += f"({max_len})"
            try:
                cur_neon.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col_name}" {type_str};')
                conn_neon.commit()
                print(f"  + Columna '{col_name}' añadida a tabla '{table}' en Neon.")
            except Exception as e:
                conn_neon.rollback()
                print(f"  ! Error al agregar columna '{col_name}' a '{table}': {e}")

def main():
    print("=" * 60)
    print("SINCRONIZANDO LOCAL -> NEON POSTGRESQL")
    print("=" * 60)

    conn_local = psycopg2.connect(LOCAL_URL)
    conn_neon = psycopg2.connect(NEON_URL)

    cur_local = conn_local.cursor(cursor_factory=RealDictCursor)
    cur_neon = conn_neon.cursor()

    tables = [
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

    total_registros = 0

    # 1. Sincronizar columnas de todas las tablas
    for table in tables:
        cur_local.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')")
        if cur_local.fetchone()['exists']:
            sync_schema_columns(conn_local, conn_neon, table)

    # 2. Desactivar temporalmente restricciones de foreign key por tabla truncando en orden inverso
    for table in reversed(tables):
        try:
            cur_neon.execute(f'TRUNCATE TABLE "{table}" CASCADE;')
            conn_neon.commit()
        except Exception:
            conn_neon.rollback()

    # 3. Transferir datos en orden directo
    for table in tables:
        try:
            cur_local.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')")
            if not cur_local.fetchone()['exists']:
                continue

            cur_local.execute(f'SELECT * FROM "{table}"')
            rows = cur_local.fetchall()
            count = len(rows)

            if count == 0:
                print(f"  [-] {table}: 0 registros en local.")
                continue

            # Obtener columnas válidas de Neon
            cur_neon.execute(f"""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = '{table}' AND table_schema = 'public'
            """)
            neon_cols = set(r[0] for r in cur_neon.fetchall())

            columns = [c for c in rows[0].keys() if c in neon_cols]
            cols_str = ', '.join([f'"{c}"' for c in columns])
            
            values_list = [[r[c] for c in columns] for r in rows]

            query = f'INSERT INTO "{table}" ({cols_str}) VALUES %s ON CONFLICT DO NOTHING'
            execute_values(cur_neon, query, values_list, page_size=1000)

            conn_neon.commit()
            print(f"  [OK] {table}: {count} registros transferidos.")
            total_registros += count
        except Exception as e:
            conn_neon.rollback()
            print(f"  [ERROR] en tabla '{table}': {e}")

    conn_local.close()
    conn_neon.close()

    print("=" * 60)
    print(f"MIGRACION COMPLETADA: {total_registros} registros guardados en Neon!")
    print("=" * 60)

if __name__ == '__main__':
    main()
