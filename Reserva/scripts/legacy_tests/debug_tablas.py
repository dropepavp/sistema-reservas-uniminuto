#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask
from database import db, PrestamoEquipo, Reserva
from datetime import datetime, date
from config import config
import os
import json

def debug_tablas():
    app = Flask(__name__)
    app.config.from_object(config[os.getenv('FLASK_CONFIG', 'development')])
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        hoy = date.today()
        print(f"=== DEBUG: ¿POR QUÉ NO SE MUESTRAN LAS TABLAS? ===")
        print(f"Fecha actual: {hoy.strftime('%d/%m/%Y')}\n")
        
        # === PRÉSTAMOS ACTIVOS ===
        print("🏷️ SIMULANDO CONSULTA DE /prestamos_equipos")
        print("Query: PrestamoEquipo.query.filter_by(estado='Prestado').order_by(desc)")
        
        prestamos_activos = PrestamoEquipo.query.filter_by(estado='Prestado').order_by(PrestamoEquipo.id_prestamo.desc()).all()
        print(f"Resultados totales: {len(prestamos_activos)}")
        
        prestamos_hoy = [p for p in prestamos_activos if p.fecha_prestamo == hoy]
        print(f"Préstamos de HOY: {len(prestamos_hoy)}")
        
        if prestamos_hoy:
            print("\nPRIMEROS 3 PRÉSTAMOS DE HOY (como aparecerían en tabla):")
            for i, p in enumerate(prestamos_hoy[:3], 1):
                print(f"\nFila {i}:")
                print(f"  ID: {p.id_prestamo}")
                print(f"  Profesor: {p.nombre_profesor}")
                print(f"  Equipo: {p.equipo_prestado}")
                print(f"  Fecha: {p.fecha_prestamo}")
                print(f"  Hora: {p.hora_inicio} - {p.hora_fin}")
                print(f"  Ubicación: {p.ubicacion}")
                print(f"  Estado: {p.estado}")
                print(f"  Jornada: {p.jornada}")
        else:
            print("❌ NO HAY PRÉSTAMOS DE HOY para mostrar en tabla")
        
        # === RESERVAS ===
        print(f"\n📅 SIMULANDO CONSULTA DE /reservas")
        print(f"Query: Reserva.query.filter(estado='Activa', fecha >= {hoy}).order_by(fecha, hora)")
        
        reservas = Reserva.query.filter(
            Reserva.estado == 'Activa',
            Reserva.fecha >= hoy
        ).order_by(Reserva.fecha, Reserva.hora_inicio).all()
        
        print(f"Resultados totales: {len(reservas)}")
        
        reservas_hoy = [r for r in reservas if r.fecha == hoy]
        print(f"Reservas de HOY: {len(reservas_hoy)}")
        
        if reservas_hoy:
            print("\nPRIMERAS 3 RESERVAS DE HOY (como aparecerían en tabla):")
            for i, r in enumerate(reservas_hoy[:3], 1):
                print(f"\nFila {i}:")
                print(f"  ID: {r.id_reserva}")
                print(f"  Profesor: {r.nombre_profesor}")
                print(f"  Recurso: {r.recurso_nombre}")
                print(f"  Tipo: {r.recurso_tipo}")
                print(f"  Fecha: {r.fecha}")
                print(f"  Hora: {r.hora_inicio} - {r.hora_fin}")
                print(f"  Estado: {r.estado}")
                print(f"  Jornada: {r.jornada}")
        else:
            print("❌ NO HAY RESERVAS DE HOY para mostrar en tabla")
        
        # === API RESERVAS ===
        print(f"\n🌐 SIMULANDO API /api/reservas")
        print("Query: Reserva.query.filter_by(estado='Activa').all()")
        
        api_reservas = Reserva.query.filter_by(estado='Activa').all()
        print(f"API resultados totales: {len(api_reservas)}")
        
        api_reservas_hoy = [r for r in api_reservas if r.fecha == hoy]
        print(f"API reservas de HOY: {len(api_reservas_hoy)}")
        
        if api_reservas_hoy:
            print("\nDATO EJEMPLO PARA CALENDARIO (formato JSON):")
            r = api_reservas_hoy[0]
            evento = {
                'id': r.id_reserva,
                'title': f"{r.nombre_profesor} - {r.recurso_nombre}",
                'start': f"{r.fecha}T{r.hora_inicio}",
                'end': f"{r.fecha}T{r.hora_fin}",
                'recurso_tipo': r.recurso_tipo
            }
            print(json.dumps(evento, indent=2, default=str))
        
        print(f"\n{'='*60}")
        print("🔍 POSIBLES PROBLEMAS:")
        
        if len(prestamos_hoy) == 0:
            print("❌ PROBLEMA: No hay préstamos de hoy para mostrar")
        else:
            print("✅ Datos de préstamos están disponibles")
            
        if len(reservas_hoy) == 0:
            print("❌ PROBLEMA: No hay reservas de hoy para mostrar")
        else:
            print("✅ Datos de reservas están disponibles")
        
        print(f"\n💡 POSIBLES CAUSAS DEL PROBLEMA:")
        print("1. Las fechas en DB pueden estar en formato diferente al esperado")
        print("2. Los templates HTML pueden tener filtros adicionales")
        print("3. JavaScript puede estar filtrando los datos")
        print("4. Timezone difference entre sistema y base de datos")
        print("5. Los templates están mostrando campos que no existen")
        
        # Verificar formato de fecha
        if prestamos_hoy:
            p = prestamos_hoy[0]
            print(f"\n🔍 FORMATO DE FECHAS EN DB:")
            print(f"  fecha_prestamo tipo: {type(p.fecha_prestamo)}")
            print(f"  fecha_prestamo valor: {p.fecha_prestamo}")
            print(f"  fecha_prestamo str: '{str(p.fecha_prestamo)}'")

if __name__ == "__main__":
    debug_tablas()