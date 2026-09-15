#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask
from database import db, Profesor, Inventario, PrestamoEquipo, Reserva
from datetime import datetime, date, time, timedelta
from config import config
import os
import random

def crear_prestamos_manana():
    app = Flask(__name__)
    app.config.from_object(config[os.getenv('FLASK_CONFIG', 'development')])
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        manana = date.today() + timedelta(days=1)
        print(f"=== CREANDO PRÉSTAMOS PARA MAÑANA ===")
        print(f"Fecha: {manana.strftime('%d/%m/%Y')}\n")
        
        # Obtener datos
        profesores = Profesor.query.all()
        equipos_disponibles = Inventario.query.filter_by(estado='Disponible').all()
        
        if len(equipos_disponibles) < 3:
            print("❌ No hay suficientes equipos disponibles")
            return
            
        # Crear 3 préstamos para mañana
        for i in range(3):
            profesor = random.choice(profesores)
            equipo = random.choice(equipos_disponibles)
            equipos_disponibles.remove(equipo)
            
            prestamo = PrestamoEquipo(
                id_grupo_prestamo=3000 + i,
                cedula_profesor=profesor.cedula,
                nombre_profesor=profesor.nombre_completo,
                equipo_prestado=equipo.item,
                numero_inventario_equipo=equipo.numero_inventario,
                ubicacion=f"Aula {random.randint(101, 301)}",
                fecha_prestamo=manana,
                hora_inicio=time(random.randint(8, 16), 0),
                hora_fin=time(random.randint(17, 20), 0),
                jornada=random.choice(["MAÑANA", "TARDE", "NOCHE"]),
                horas_academicas=random.randint(2, 4),
                auxiliar_entrega="80140666",
                estado="Prestado"
            )
            
            equipo.estado = "En Préstamo"
            
            db.session.add(prestamo)
            db.session.add(equipo)
            
            print(f"✓ Préstamo: {profesor.nombre_completo} - {equipo.item} (MAÑANA)")
        
        # Crear 2 reservas para mañana
        for i in range(2):
            profesor = random.choice(profesores)
            recurso_tipo = random.choice(["salon", "ninera"])
            
            if recurso_tipo == "salon":
                recurso_nombre = f"Salón {random.randint(201, 301)}"
            else:
                recurso_nombre = "Carmen Lucía Pérez"
            
            reserva = Reserva(
                cedula_profesor=profesor.cedula,
                nombre_profesor=profesor.nombre_completo,
                recurso_tipo=recurso_tipo,
                recurso_nombre=recurso_nombre,
                fecha=manana,
                hora_inicio=time(random.randint(8, 15), 0),
                hora_fin=time(random.randint(16, 18), 0),
                jornada=random.choice(["MAÑANA", "TARDE"]),
                tipo_reserva="Clase",
                estado="Activa"
            )
            
            db.session.add(reserva)
            print(f"✓ Reserva: {profesor.nombre_completo} - {recurso_nombre} (MAÑANA)")
        
        db.session.commit()
        
        print(f"\n✅ Datos para MAÑANA creados:")
        print(f"   📦 3 préstamos adicionales")
        print(f"   📅 2 reservas adicionales")
        print(f"\n🔍 Ahora deberías poder ver:")
        print(f"   - Préstamos de hoy Y mañana en la web")
        print(f"   - Reservas de hoy Y mañana en la web")

if __name__ == "__main__":
    crear_prestamos_manana()