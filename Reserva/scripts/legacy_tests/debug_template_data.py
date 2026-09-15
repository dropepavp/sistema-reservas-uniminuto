#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask
from database import db, PrestamoEquipo, Reserva, Inventario
from config import SystemConstants, config
from datetime import datetime, date, timedelta
import os

def debug_template_data():
    app = Flask(__name__)
    app.config.from_object(config[os.getenv('FLASK_CONFIG', 'development')])
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        print("=== SIMULANDO EXACTAMENTE LA RUTA /prestamos_equipos ===\n")
        
        ESTADO_PRESTADO = SystemConstants.ESTADO_PRESTADO
        ESTADO_ACTIVA = SystemConstants.ESTADO_ACTIVA
        
        hoy = date.today()
        print(f"Fecha de hoy: {hoy}")
        print(f"ESTADO_PRESTADO: '{ESTADO_PRESTADO}'\n")
        
        # === REPRODUCIR EXACTA LÓGICA DE /prestamos_equipos ===
        
        # --- Lógica para conteos de inventario ---
        disponibles_count = Inventario.query.filter_by(estado='Disponible').count()
        prestados_count = Inventario.query.filter_by(estado='En Préstamo').count()
        print(f"📦 Inventario disponible: {disponibles_count}")
        print(f"📦 Inventario en préstamo: {prestados_count}")
        
        # --- Filtrar para mostrar todos los préstamos activos ('Prestado') ---
        prestamos_activos = PrestamoEquipo.query.filter_by(estado=ESTADO_PRESTADO).order_by(PrestamoEquipo.id_prestamo.desc()).all()
        print(f"\n🏷️ Query: PrestamoEquipo.query.filter_by(estado='{ESTADO_PRESTADO}').order_by(desc).all()")
        print(f"🏷️ Préstamos activos TOTALES: {len(prestamos_activos)}")
        
        # Analizar por fecha
        prestamos_hoy = [p for p in prestamos_activos if p.fecha_prestamo == hoy]
        prestamos_ayer = [p for p in prestamos_activos if p.fecha_prestamo == hoy - timedelta(days=1)]
        prestamos_manana = [p for p in prestamos_activos if p.fecha_prestamo == hoy + timedelta(days=1)]
        prestamos_otros = [p for p in prestamos_activos if p.fecha_prestamo not in [hoy, hoy - timedelta(days=1), hoy + timedelta(days=1)]]
        
        print(f"\n📊 DISTRIBUCIÓN POR FECHAS:")
        print(f"   Préstamos de HOY ({hoy}): {len(prestamos_hoy)}")
        print(f"   Préstamos de AYER ({hoy - timedelta(days=1)}): {len(prestamos_ayer)}")
        print(f"   Préstamos de MAÑANA ({hoy + timedelta(days=1)}): {len(prestamos_manana)}")
        print(f"   Préstamos de otras fechas: {len(prestamos_otros)}")
        
        # Mostrar algunos ejemplos de cada categoría
        if prestamos_hoy:
            print(f"\n✅ Préstamos de HOY (primeros 3):")
            for i, p in enumerate(prestamos_hoy[:3], 1):
                print(f"   {i}. ID {p.id_prestamo}: {p.nombre_profesor} - {p.equipo_prestado}")
        
        if prestamos_manana:
            print(f"\n📅 Préstamos de MAÑANA (primeros 3):")
            for i, p in enumerate(prestamos_manana[:3], 1):
                print(f"   {i}. ID {p.id_prestamo}: {p.nombre_profesor} - {p.equipo_prestado}")
        
        if prestamos_otros:
            print(f"\n📝 Préstamos de OTRAS FECHAS (primeros 5):")
            for i, p in enumerate(prestamos_otros[:5], 1):
                print(f"   {i}. ID {p.id_prestamo}: {p.nombre_profesor} - {p.equipo_prestado} (Fecha: {p.fecha_prestamo})")
        
        # === DATOS QUE SE PASAN AL TEMPLATE ===
        print(f"\n🎯 DATOS PASADOS AL TEMPLATE prestamos_equipos.html:")
        print(f"   prestamos: {len(prestamos_activos)} items (TODOS los activos)")
        print(f"   equipos: [] (vacío)")
        print(f"   disponibles_count: {disponibles_count}")
        print(f"   prestados_count: {prestados_count}")
        
        # === SIMULACIÓN DEL TEMPLATE ===
        print(f"\n📄 SIMULACIÓN DEL LOOP DEL TEMPLATE:")
        print(f"Template loop itera sobre {len(prestamos_activos)} préstamos")
        print("   - Debería mostrar TODOS los préstamos activos, sin filtro de fecha")
        
        # === VERIFICAR RESERVAS TAMBIÉN ===
        print(f"\n📅 VERIFICANDO RESERVAS:")
        reservas_activas_total = Reserva.query.filter_by(estado=ESTADO_ACTIVA).all()
        reservas_desde_hoy = Reserva.query.filter(
            Reserva.estado == ESTADO_ACTIVA,
            Reserva.fecha >= hoy
        ).all()
        
        print(f"   Reservas activas TOTAL: {len(reservas_activas_total)}")
        print(f"   Reservas desde hoy: {len(reservas_desde_hoy)}")
        
        reservas_hoy = [r for r in reservas_desde_hoy if r.fecha == hoy]
        print(f"   Reservas de HOY: {len(reservas_hoy)}")
        
        if reservas_hoy:
            print(f"\n✅ Reservas de HOY:")
            for i, r in enumerate(reservas_hoy, 1):
                print(f"   {i}. {r.nombre_profesor} - {r.recurso_nombre} ({r.recurso_tipo})")
        
        print(f"\n{'='*70}")
        print("🔍 CONCLUSIÓN:")
        
        if len(prestamos_activos) > 10:
            print(f"✅ HAY {len(prestamos_activos)} préstamos activos que DEBERÍAN aparecer en la tabla")
            print(f"   - {len(prestamos_hoy)} son de hoy")
            print(f"   - {len(prestamos_activos) - len(prestamos_hoy)} son de otras fechas")
        else:
            print("❌ Pocos préstamos activos encontrados")
        
        print(f"\n💡 Si solo ves {len(prestamos_hoy)} filas en la tabla, significa que:")
        print("   1. JavaScript está filtrando por fecha")
        print("   2. CSS está ocultando filas")
        print("   3. El template tiene un filtro que no vemos")

if __name__ == "__main__":
    debug_template_data()