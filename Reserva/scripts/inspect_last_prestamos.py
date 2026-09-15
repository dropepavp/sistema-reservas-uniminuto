import sys
import os
# Asegurar que el repo root esté en sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app import create_app
from database import PrestamoEquipo, db

app = create_app()

with app.app_context():
    prestamos = PrestamoEquipo.query.order_by(PrestamoEquipo.id_prestamo.desc()).limit(20).all()
    for p in prestamos:
        print(f"ID: {p.id_prestamo} | Grupo: {p.id_grupo_prestamo} | Profesor: {p.nombre_profesor} | Equipo: {p.equipo_prestado} | Estado: {p.estado} | Fecha: {p.fecha_prestamo} | Sede: {p.sede_id}")
    if not prestamos:
        print('No hay registros de préstamos')
