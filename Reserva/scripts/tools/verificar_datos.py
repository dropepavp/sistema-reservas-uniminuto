#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask
from database import db, Auxiliar, Profesor, Inventario, PrestamoEquipo, Reserva
from config import config
import os

def verificar_datos():
    app = Flask(__name__)
    app.config.from_object(config[os.getenv('FLASK_CONFIG', 'development')])
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        print("=== VERIFICACIÓN DE DATOS EN LA BASE DE DATOS ===\n")
        
        # Verificar profesores
        profesores = Profesor.query.all()
        print(f"📋 PROFESORES: {len(profesores)}")
        for p in profesores[:5]:  # Mostrar solo los primeros 5
            print(f"   - {p.cedula}: {p.nombre_completo}")
        if len(profesores) > 5:
            print(f"   ... y {len(profesores) - 5} más")
        
        # Verificar auxiliares
        auxiliares = Auxiliar.query.all()
        print(f"\n👨‍💼 AUXILIARES: {len(auxiliares)}")
        for a in auxiliares:
            print(f"   - {a.documento}: {a.nombre_completo} ({a.rol})")
        
        # Verificar inventario
        inventario = Inventario.query.all()
        print(f"\n📦 INVENTARIO: {len(inventario)}")
        for i in inventario[:10]:  # Mostrar solo los primeros 10
            print(f"   - {i.numero_inventario}: {i.item} ({i.categoria})")
        if len(inventario) > 10:
            print(f"   ... y {len(inventario) - 10} más")
        
        # Verificar préstamos
        prestamos = PrestamoEquipo.query.all()
        print(f"\n🏷️ PRÉSTAMOS: {len(prestamos)}")
        if prestamos:
            print("   Primeros 5 préstamos:")
            for p in prestamos[:5]:
                print(f"   - ID: {p.id_prestamo}, Grupo: {p.id_grupo_prestamo}, Equipo: {p.equipo_prestado}, Fecha: {p.fecha_prestamo}")
        
        # Verificar reservas
        reservas = Reserva.query.all()
        print(f"\n📅 RESERVAS: {len(reservas)}")
        if reservas:
            print("   Primeras 5 reservas:")
            for r in reservas[:5]:
                print(f"   - ID: {r.id_reserva}, Recurso: {r.recurso_nombre} ({r.recurso_tipo}), Fecha: {r.fecha}")
        
        print(f"\n{'='*50}")
        print("RESUMEN:")
        print(f"- Profesores: {len(profesores)}")
        print(f"- Auxiliares: {len(auxiliares)}")
        print(f"- Inventario: {len(inventario)}")
        print(f"- Préstamos: {len(prestamos)}")
        print(f"- Reservas: {len(reservas)}")
        
        if len(prestamos) == 0:
            print("\n❌ NO HAY PRÉSTAMOS - Puede haber un problema en la estructura de datos")
            print("\nVerificando estructura de tabla de préstamos...")
            try:
                # Verificar columnas de la tabla
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                columns = inspector.get_columns('prestamos_equipos')
                print("Columnas en prestamos_equipos:")
                for col in columns:
                    print(f"   - {col['name']}: {col['type']}")
            except Exception as e:
                print(f"Error verificando estructura: {e}")

if __name__ == "__main__":
    verificar_datos()