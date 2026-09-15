#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask
from database import db, PrestamoEquipo, Reserva
from datetime import datetime, date
from config import config
import os

def verificar_datos_hoy():
    app = Flask(__name__)
    app.config.from_object(config[os.getenv('FLASK_CONFIG', 'development')])
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        hoy = date.today()
        print(f"=== VERIFICANDO DATOS PARA HOY ({hoy.strftime('%d/%m/%Y')}) ===\n")
        
        # Verificar préstamos de hoy
        prestamos_hoy = PrestamoEquipo.query.filter_by(fecha_prestamo=hoy).all()
        print(f"🏷️ PRÉSTAMOS DE HOY: {len(prestamos_hoy)}")
        
        if prestamos_hoy:
            for p in prestamos_hoy:
                print(f"   - ID: {p.id_prestamo}, Estado: {p.estado}")
                print(f"     Profesor: {p.nombre_profesor}")
                print(f"     Equipo: {p.equipo_prestado}")
                print(f"     Fecha: {p.fecha_prestamo}, Hora: {p.hora_inicio}-{p.hora_fin}")
                print(f"     Jornada: {p.jornada}")
                print(f"     Ubicación: {p.ubicacion}")
                print()
        
        # Verificar préstamos activos (estado Prestado)
        prestamos_activos = PrestamoEquipo.query.filter_by(estado='Prestado').all()
        prestamos_activos_hoy = [p for p in prestamos_activos if p.fecha_prestamo == hoy]
        
        print(f"🔄 PRÉSTAMOS ACTIVOS TOTAL: {len(prestamos_activos)}")
        print(f"🔄 PRÉSTAMOS ACTIVOS HOY: {len(prestamos_activos_hoy)}")
        
        # Verificar reservas de hoy
        reservas_hoy = Reserva.query.filter_by(fecha=hoy).all()
        print(f"\n📅 RESERVAS DE HOY: {len(reservas_hoy)}")
        
        if reservas_hoy:
            for r in reservas_hoy:
                print(f"   - ID: {r.id_reserva}, Estado: {r.estado}")
                print(f"     Profesor: {r.nombre_profesor}")
                print(f"     Recurso: {r.recurso_nombre} ({r.recurso_tipo})")
                print(f"     Fecha: {r.fecha}, Hora: {r.hora_inicio}-{r.hora_fin}")
                print(f"     Jornada: {r.jornada}")
                print()
        
        # Verificar reservas activas
        reservas_activas = Reserva.query.filter_by(estado='Activa').all()
        reservas_activas_hoy = [r for r in reservas_activas if r.fecha == hoy]
        
        print(f"🔄 RESERVAS ACTIVAS TOTAL: {len(reservas_activas)}")
        print(f"🔄 RESERVAS ACTIVAS HOY: {len(reservas_activas_hoy)}")
        
        print(f"\n{'='*50}")
        print("DIAGNÓSTICO:")
        
        if len(prestamos_hoy) == 0:
            print("❌ No hay préstamos registrados para hoy")
        elif len(prestamos_activos_hoy) == 0:
            print("❌ Hay préstamos para hoy pero ninguno está en estado 'Prestado'")
        else:
            print("✅ Hay préstamos activos para hoy")
        
        if len(reservas_hoy) == 0:
            print("❌ No hay reservas registradas para hoy")
        elif len(reservas_activas_hoy) == 0:
            print("❌ Hay reservas para hoy pero ninguna está en estado 'Activa'")
        else:
            print("✅ Hay reservas activas para hoy")

if __name__ == "__main__":
    verificar_datos_hoy()