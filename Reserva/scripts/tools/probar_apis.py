#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask
from database import db, PrestamoEquipo, Reserva
from datetime import datetime, date
from config import config
import os

def probar_apis():
    app = Flask(__name__)
    app.config.from_object(config[os.getenv('FLASK_CONFIG', 'development')])
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        hoy = date.today()
        print(f"=== PROBANDO CONSULTAS COMO LAS APIs ({hoy.strftime('%d/%m/%Y')}) ===\n")
        
        # Simular consulta de préstamos activos (como en /prestamos_equipos)
        print("🏷️ CONSULTA: Préstamos activos (estado='Prestado')")
        prestamos_activos = PrestamoEquipo.query.filter_by(estado='Prestado').order_by(PrestamoEquipo.id_prestamo.desc()).all()
        print(f"   Total préstamos activos: {len(prestamos_activos)}")
        
        prestamos_hoy = [p for p in prestamos_activos if p.fecha_prestamo == hoy]
        print(f"   Préstamos activos HOY: {len(prestamos_hoy)}")
        
        if prestamos_hoy:
            print("   Detalles préstamos de hoy:")
            for p in prestamos_hoy[:5]:  # Solo primeros 5
                print(f"     - {p.nombre_profesor}: {p.equipo_prestado} ({p.hora_inicio}-{p.hora_fin})")
        
        # Simular consulta de reservas (como en /reservas)
        print(f"\n📅 CONSULTA: Reservas activas desde hoy (estado='Activa' AND fecha >= {hoy})")
        reservas_filtro = Reserva.query.filter(
            Reserva.estado == 'Activa',
            Reserva.fecha >= hoy
        ).order_by(Reserva.fecha, Reserva.hora_inicio).all()
        
        print(f"   Total reservas futuras (incluye hoy): {len(reservas_filtro)}")
        
        reservas_hoy = [r for r in reservas_filtro if r.fecha == hoy]
        print(f"   Reservas de HOY: {len(reservas_hoy)}")
        
        if reservas_hoy:
            print("   Detalles reservas de hoy:")
            for r in reservas_hoy:
                print(f"     - {r.nombre_profesor}: {r.recurso_nombre} ({r.recurso_tipo}) {r.hora_inicio}-{r.hora_fin}")
        
        # Simular API de reservas (como en /api/reservas) 
        print(f"\n🌐 CONSULTA: API Reservas (estado='Activa' sin filtro de fecha)")
        api_reservas = Reserva.query.filter_by(estado='Activa').all()
        print(f"   Total reservas API: {len(api_reservas)}")
        
        api_reservas_hoy = [r for r in api_reservas if r.fecha == hoy]
        print(f"   API reservas de HOY: {len(api_reservas_hoy)}")
        
        print(f"\n{'='*60}")
        print("🔍 DIAGNÓSTICO DE VISUALIZACIÓN:")
        
        if len(prestamos_hoy) > 0:
            print(f"✅ HAY {len(prestamos_hoy)} préstamos activos de hoy que DEBERÍAN verse en /prestamos_equipos")
        else:
            print("❌ NO hay préstamos activos de hoy")
            
        if len(reservas_hoy) > 0:
            print(f"✅ HAY {len(reservas_hoy)} reservas de hoy que DEBERÍAN verse en /reservas")
        else:
            print("❌ NO hay reservas de hoy")
            
        if len(api_reservas_hoy) > 0:
            print(f"✅ HAY {len(api_reservas_hoy)} reservas de hoy que DEBERÍAN verse en la API /api/reservas")
        else:
            print("❌ NO hay reservas de hoy en la API")
        
        print(f"\n💡 Si no ves datos en la web, puede ser:")
        print("   1. Problema de JavaScript en el frontend")
        print("   2. Problema de template HTML")
        print("   3. Filtros adicionales en JavaScript")
        print("   4. Problema de timezone/fecha")

if __name__ == "__main__":
    probar_apis()