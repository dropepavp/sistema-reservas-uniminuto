"""
Script de migración:
- Busca si la tabla 'prestamos_equipos' tiene la columna 'hora_devolucion' (datetime) y, si existe,
  copia su valor a 'fecha_devolucion' (date) y 'hora_devolucion_real' (time) cuando corresponda.
- No elimina la columna original; solo realiza la migración de datos.

Uso:
  desde el directorio del proyecto ejecutar:
    .\.venv\Scripts\python.exe scripts\tools\migrate_hora_devolucion.py

Asegurarse de tener la variable de entorno DATABASE_URL configurada si no se usa sqlite por defecto.
"""

from sqlalchemy import create_engine, MetaData, Table, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import os

DB_URL = os.environ.get('DATABASE_URL') or 'sqlite:///Reserva_dev.db'

print(f"Usando DATABASE_URL={DB_URL}")

engine: Engine = create_engine(DB_URL)
metadata = MetaData()

try:
    metadata.reflect(bind=engine, only=['prestamos_equipos'])
except Exception as e:
    print('Error al reflejar metadatos:', e)
    raise

if 'prestamos_equipos' not in metadata.tables:
    print("La tabla 'prestamos_equipos' no existe en la base de datos. Abortando.")
    exit(0)

prestamos = metadata.tables['prestamos_equipos']

cols = set(c.name for c in prestamos.columns)

if 'hora_devolucion' not in cols:
    print("No se encontró la columna 'hora_devolucion'. No hay nada que migrar.")
    exit(0)

if 'fecha_devolucion' not in cols or 'hora_devolucion_real' not in cols:
    print("Advertencia: las columnas 'fecha_devolucion' o 'hora_devolucion_real' no existen. Abortando migración.")
    exit(1)

conn = engine.connect()
trans = conn.begin()

try:
    sel = select([prestamos.c.id_prestamo, prestamos.c.hora_devolucion, prestamos.c.fecha_devolucion, prestamos.c.hora_devolucion_real]).where(prestamos.c.hora_devolucion != None)
    results = conn.execute(sel).fetchall()
    print(f"Registros encontrados con hora_devolucion no nula: {len(results)}")

    migrated = 0
    for row in results:
        id_p = row['id_prestamo']
        hora_dev = row['hora_devolucion']
        # hora_dev puede ser str o datetime; intentar parsear
        if isinstance(hora_dev, str):
            try:
                hora_dt = datetime.fromisoformat(hora_dev)
            except Exception:
                try:
                    # último recurso: parsear con formato conocido
                    hora_dt = datetime.strptime(hora_dev, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    print(f"No se pudo parsear hora_devolucion para id {id_p}: {hora_dev}")
                    continue
        elif isinstance(hora_dev, datetime):
            hora_dt = hora_dev
        else:
            # Otros tipos (date/time) convierten a str
            try:
                hora_dt = datetime.fromisoformat(str(hora_dev))
            except Exception:
                print(f"Tipo inesperado para hora_devolucion en id {id_p}: {type(hora_dev)}")
                continue

        fecha_val = hora_dt.date()
        hora_val = hora_dt.time()

        # Solo actualizar si fecha_devolucion o hora_devolucion_real son NULL
        upd_stmt = update(prestamos).where(prestamos.c.id_prestamo == id_p).values(
            fecha_devolucion = fecha_val,
            hora_devolucion_real = hora_val
        )
        conn.execute(upd_stmt)
        migrated += 1

    trans.commit()
    print(f"Migración completada. Registros actualizados: {migrated}")
except SQLAlchemyError as e:
    print('Error durante migración, haciendo rollback:', e)
    trans.rollback()
finally:
    conn.close()

print('Terminado.')
