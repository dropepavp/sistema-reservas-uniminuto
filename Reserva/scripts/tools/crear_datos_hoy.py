#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from database import db, Profesor, Inventario, PrestamoEquipo, Reserva
from datetime import datetime, date, time, timedelta
import os
import random
import sys

# Asegurar que el directorio del proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app_improved import create_app

def crear_prestamos_y_reservas_hoy():
    app = create_app()
    
    with app.app_context():
        print("=== CREANDO PRÉSTAMOS Y RESERVAS PARA HOY ===")
        print(f"Fecha: {datetime.now().strftime('%d/%m/%Y')}\n")
        
        # Obtener datos necesarios
        profesores = Profesor.query.all()
        equipos_disponibles = Inventario.query.filter_by(estado='Disponible').all()
        
        print(f"📋 Profesores disponibles: {len(profesores)}")
        print(f"📦 Equipos disponibles: {len(equipos_disponibles)}")
        
        if not profesores:
            print("❌ No hay profesores en la base de datos")
            return
        
        if not equipos_disponibles:
            print("❌ No hay equipos disponibles")
            return
        
        # === CREAR PRÉSTAMOS PARA HOY ===
        print(f"\n🏷️ CREANDO PRÉSTAMOS PARA HOY...")
        
        jornadas = ["MAÑANA", "TARDE", "NOCHE"]
        ubicaciones = [
            "Aula 101", "Aula 102", "Aula 201", "Aula 202", "Aula 301", 
            "Laboratorio 1", "Laboratorio 2", "Auditorio", "Sala A", "Sala B"
        ]
        auxiliares_entrega = ["80140666", "11111111", "22222222", "33333333"]
        
        prestamos_creados = 0
        
        # Crear 5-8 préstamos para diferentes horarios del día
        num_prestamos = random.randint(5, 8)
        
        for i in range(num_prestamos):
            if not equipos_disponibles:
                break
                
            # Seleccionar profesor y equipo
            profesor = random.choice(profesores)
            equipo = random.choice(equipos_disponibles)
            equipos_disponibles.remove(equipo)  # Para no repetir
            
            # Generar horarios realistas
            jornada = random.choice(jornadas)
            if jornada == "MAÑANA":
                hora_inicio = time(random.randint(7, 12), random.choice([0, 30]))
                duracion = random.randint(2, 4)
            elif jornada == "TARDE":
                hora_inicio = time(random.randint(14, 16), random.choice([0, 30]))
                duracion = random.randint(2, 3)
            else:  # NOCHE
                hora_inicio = time(random.randint(18, 20), random.choice([0, 30]))
                duracion = random.randint(2, 3)
            
            # Calcular hora fin
            hora_fin_dt = datetime.combine(date.today(), hora_inicio)
            hora_fin_dt += timedelta(hours=duracion)
            hora_fin = hora_fin_dt.time()
            
            # Crear préstamo
            prestamo = PrestamoEquipo(
                id_grupo_prestamo=2000 + i,  # ID único
                cedula_profesor=profesor.cedula,
                nombre_profesor=profesor.nombre_completo,
                equipo_prestado=equipo.item,
                numero_inventario_equipo=equipo.numero_inventario,
                ubicacion=random.choice(ubicaciones),
                fecha_prestamo=date.today(),
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                jornada=jornada,
                horas_academicas=duracion,
                auxiliar_entrega=random.choice(auxiliares_entrega),
                estado="Prestado",
                observaciones=random.choice([
                    "Clase de programación",
                    "Presentación de proyecto",
                    "Conferencia magistral", 
                    "Taller práctico",
                    "Evaluación grupal",
                    ""
                ])
            )
            
            # Cambiar estado del equipo
            equipo.estado = "En Préstamo"
            
            db.session.add(prestamo)
            db.session.add(equipo)
            prestamos_creados += 1
            
            print(f"   ✓ Préstamo: {profesor.nombre_completo} - {equipo.item} ({jornada} {hora_inicio}-{hora_fin})")
        
        # === CREAR RESERVAS PARA HOY ===
        print(f"\n📅 CREANDO RESERVAS PARA HOY...")
        
        # Recursos disponibles
        salones = [
            "Salón 201", "Salón 202", "Salón 301", "Auditorio Principal", 
            "Sala de Juntas A", "Laboratorio 1", "Laboratorio 2", "Aula Magna"
        ]
        
        nineras = [
            "María Elena Rodríguez", "Carmen Lucía Pérez", "Rosa María González",
            "Ana Patricia López", "Luz Marina Torres", "Gloria Esperanza Vargas"
        ]
        
        tipos_reserva = ["Clase", "Reunión", "Taller", "Conferencia", "Evaluación"]
        reservas_creadas = 0
        
        # Crear 4-6 reservas para hoy
        num_reservas = random.randint(4, 6)
        
        for i in range(num_reservas):
            profesor = random.choice(profesores)
            tipo_recurso = random.choice(["salon", "ninera"])
            
            if tipo_recurso == "salon":
                recurso_nombre = random.choice(salones)
            else:
                recurso_nombre = random.choice(nineras)
            
            # Generar horarios
            jornada = random.choice(jornadas)
            if jornada == "MAÑANA":
                hora_inicio = time(random.randint(8, 11), random.choice([0, 30]))
                duracion = random.randint(1, 3)
            elif jornada == "TARDE":
                hora_inicio = time(random.randint(14, 17), random.choice([0, 30]))
                duracion = random.randint(1, 2)
            else:  # NOCHE
                hora_inicio = time(random.randint(18, 20), random.choice([0, 30]))
                duracion = random.randint(1, 2)
            
            hora_fin_dt = datetime.combine(date.today(), hora_inicio)
            hora_fin_dt += timedelta(hours=duracion)
            hora_fin = hora_fin_dt.time()
            
            # Crear reserva
            reserva = Reserva(
                cedula_profesor=profesor.cedula,
                nombre_profesor=profesor.nombre_completo,
                recurso_tipo=tipo_recurso,
                recurso_nombre=recurso_nombre,
                fecha=date.today(),
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                jornada=jornada,
                tipo_reserva=random.choice(tipos_reserva),
                estado="Activa",
                observaciones=random.choice([
                    "Reserva para clase magistral",
                    "Reunión de coordinación",
                    "Taller con estudiantes",
                    "Presentación de proyectos",
                    "Sesión de evaluación",
                    ""
                ])
            )
            
            db.session.add(reserva)
            reservas_creadas += 1
            
            tipo_texto = "Salón" if tipo_recurso == "salon" else "Niñera"
            print(f"   ✓ Reserva: {profesor.nombre_completo} - {tipo_texto}: {recurso_nombre} ({jornada} {hora_inicio}-{hora_fin})")
        
        # Guardar todos los cambios
        db.session.commit()
        
        print(f"\n✅ DATOS CREADOS PARA HOY ({date.today().strftime('%d/%m/%Y')}):")
        print(f"   📦 Préstamos activos: {prestamos_creados}")
        print(f"   📅 Reservas activas: {reservas_creadas}")
        print(f"   🎯 Total equipos en préstamo: {PrestamoEquipo.query.filter_by(estado='Prestado', fecha_prestamo=date.today()).count()}")
        print(f"   🏢 Total reservas de hoy: {Reserva.query.filter_by(fecha=date.today()).count()}")
        
        print(f"\n🌐 Ahora puedes ver:")
        print(f"   - Préstamos de hoy en: /prestamos_equipos")
        print(f"   - Reservas de hoy en: /reservas") 
        print(f"   - Estadísticas actualizadas en: /estadisticas")
        print(f"   - Dashboard con datos frescos en: /")

if __name__ == "__main__":
    crear_prestamos_y_reservas_hoy()