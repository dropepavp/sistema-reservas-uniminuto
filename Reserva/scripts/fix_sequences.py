"""
Script para sincronizar y actualizar todas las secuencias (auto-incrementales / SERIAL) en Neon PostgreSQL.
"""
import psycopg2

NEON_URL = "postgresql://neondb_owner:npg_gfN7lxKRrp3X@ep-lively-king-acufthob.sa-east-1.aws.neon.tech/neondb?sslmode=require"

def main():
    print("Conectando a Neon para actualizar secuencias...")
    conn = psycopg2.connect(NEON_URL)
    cur = conn.cursor()

    # Mapeo de tablas y sus columnas de clave primaria numérica
    table_pks = [
        ('auditorias', 'id'),
        ('sedes', 'id'),
        ('ubicaciones', 'id'),
        ('recursos', 'id'),
        ('bodegas', 'id'),
        ('categorias_inventario', 'id'),
        ('inventario', 'id'),
        ('programas_academicos', 'id'),
        ('estudiantes', 'id'),
        ('prestamos_equipos', 'id_prestamo'),
        ('reservas', 'id_reserva'),
        ('clases_salas_computo', 'id_clase'),
        ('permisos_usuarios', 'id'),
        ('colaboradores', 'id'),
        ('horarios_colaboradores', 'id'),
        ('tareas_colaboradores', 'id'),
        ('permisos_colaboradores', 'id'),
        ('puestos_computo', 'id'),
        ('software_salas', 'id'),
        ('software_asignado_salas', 'id'),
        ('novedades_tecnicas_salas', 'id'),
        ('mantenimientos_inventario', 'id'),
        ('practicas_libres', 'id')
    ]

    for table, pk in table_pks:
        try:
            # Obtener el nombre de la secuencia asociada a la columna
            cur.execute(f"SELECT pg_get_serial_sequence('{table}', '{pk}')")
            seq = cur.fetchone()[0]
            
            if seq:
                # Actualizar el valor actual de la secuencia al MAX(pk)
                cur.execute(f"""
                    SELECT setval(
                        '{seq}',
                        COALESCE((SELECT MAX("{pk}") FROM "{table}"), 1),
                        true
                    )
                """)
                new_val = cur.fetchone()[0]
                print(f"  [OK] {table}.{pk} -> secuencia '{seq}' actualizada a {new_val}")
            else:
                print(f"  [-] {table}.{pk} -> no tiene secuencia vinculada.")
        except Exception as e:
            print(f"  [!] Error en {table}.{pk}: {e}")

    conn.commit()
    conn.close()
    print("\n¡Todas las secuencias fueron sincronizadas exitosamente en Neon!")

if __name__ == '__main__':
    main()
