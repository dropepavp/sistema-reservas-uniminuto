"""
Script de migración para agregar columnas de gestión por cantidad
al inventario y al registro de préstamos.

Ejecutar UNA SOLA VEZ: python migracion_cantidad.py
"""
import sys
import os

# Asegurar que el directorio del proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app_improved import create_app
from database import db

def migrar():
    app = create_app()
    with app.app_context():
        print("Iniciando migración de columnas de cantidad...")
        
        columnas_inventario = [
            ("es_por_cantidad", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("cantidad_total",   "INTEGER"),
            ("cantidad_disponible", "INTEGER"),
        ]
        
        columnas_prestamos = [
            ("cantidad_prestada", "INTEGER DEFAULT 1"),
        ]
        
        def agregar_si_no_existe(tabla, col, tipo):
            # Verificar si la columna ya existe
            result = db.session.execute(db.text(
                f"SELECT column_name FROM information_schema.columns "
                f"WHERE table_name='{tabla}' AND column_name='{col}'"
            )).fetchone()
            if result:
                print(f"  ✔ {tabla}.{col} ya existe, omitiendo.")
            else:
                db.session.execute(db.text(
                    f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}"
                ))
                db.session.commit()
                print(f"  ✅ Columna {tabla}.{col} agregada exitosamente.")
        
        for col, tipo in columnas_inventario:
            agregar_si_no_existe("inventario", col, tipo)
        
        for col, tipo in columnas_prestamos:
            agregar_si_no_existe("prestamos_equipos", col, tipo)
        
        print("\n✅ Migración completada exitosamente.")

if __name__ == "__main__":
    migrar()
