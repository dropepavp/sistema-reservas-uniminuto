"""
Migración que utiliza la aplicación Flask para identificar la base de datos configurada
y migrar valores de la columna `hora_devolucion` (si existe) a `fecha_devolucion` y
`hora_devolucion_real` en la tabla `prestamos_equipos`.

Este script debe ejecutarse desde el entorno del proyecto con el virtualenv activo:
  .\.venv\Scripts\python.exe scripts\tools\migrate_hora_devolucion_app.py

El script mostrará cuántos registros va a actualizar y procederá automáticamente.
"""

import os, sys
# Asegurar que la raíz del proyecto esté en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import create_app
from database import db
from sqlalchemy import inspect, text
from datetime import datetime

app = create_app()

with app.app_context():
    engine = db.engine
    inspector = inspect(engine)
    if 'prestamos_equipos' not in inspector.get_table_names():
        print("La tabla 'prestamos_equipos' no existe en la base de datos configurada. Abortando.")
        raise SystemExit(0)

    cols = [c['name'] for c in inspector.get_columns('prestamos_equipos')]
    print('Columnas encontradas en prestamos_equipos:', cols)

    if 'hora_devolucion' not in cols:
        print("No existe la columna 'hora_devolucion'. Nada que migrar.")
        raise SystemExit(0)

    if 'fecha_devolucion' not in cols or 'hora_devolucion_real' not in cols:
        print("Faltan columnas destino 'fecha_devolucion' o 'hora_devolucion_real'. Abortando.")
        raise SystemExit(1)

    # Contar registros a migrar
    sel_count = text("SELECT COUNT(*) AS c FROM prestamos_equipos WHERE hora_devolucion IS NOT NULL")
    res = db.session.execute(sel_count).fetchone()
    total = res['c'] if res else 0
    print(f'Registros con hora_devolucion no nula: {total}')

    if total == 0:
        print('Nada por hacer.')
        raise SystemExit(0)

    print('Iniciando migración...')

    # Seleccionar registros y actualizar por lotes
    sel = text("SELECT id_prestamo, hora_devolucion FROM prestamos_equipos WHERE hora_devolucion IS NOT NULL")
    rows = db.session.execute(sel).fetchall()
    migrated = 0
    for row in rows:
        id_p = row['id_prestamo']
        hora_dev = row['hora_devolucion']
        # hora_dev puede ser datetime, str, etc.
        if isinstance(hora_dev, str):
            try:
                hora_dt = datetime.fromisoformat(hora_dev)
            except Exception:
                try:
                    hora_dt = datetime.strptime(hora_dev, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    print(f"No se pudo parsear hora_devolucion para id {id_p}: {hora_dev}")
                    continue
        elif hasattr(hora_dev, 'year'):
            hora_dt = hora_dev
        else:
            try:
                hora_dt = datetime.fromisoformat(str(hora_dev))
            except Exception:
                print(f"Tipo inesperado para hora_devolucion en id {id_p}: {type(hora_dev)}")
                continue

        fecha_val = hora_dt.date().isoformat()
        hora_val = hora_dt.time().isoformat()

        upd = text("""
            UPDATE prestamos_equipos
            SET fecha_devolucion = :fecha_val,
                hora_devolucion_real = :hora_val
            WHERE id_prestamo = :id_p
        """)
        db.session.execute(upd, {'fecha_val': fecha_val, 'hora_val': hora_val, 'id_p': id_p})
        migrated += 1

    db.session.commit()
    print(f'Migración finalizada. Registros actualizados: {migrated}')
