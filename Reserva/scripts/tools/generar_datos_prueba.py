#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash
from flask import Flask
from config import config

# Importar modelos
from database import db, Auxiliar, Profesor, Inventario, PrestamoEquipo, Reserva, init_db

def inicializar_flask_app():
    """Inicializar aplicación Flask para contexto de base de datos"""
    app = Flask(__name__)
    app.config.from_object(config[os.getenv('FLASK_CONFIG', 'development')])
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        # Crear todas las tablas
        db.create_all()
        return app

def conectar_db():
    """Conectar a la base de datos"""
    app = Flask(__name__)
    app.config.from_object(config[os.getenv('FLASK_CONFIG', 'development')])
    engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
    Session = sessionmaker(bind=engine)
    return Session()

def crear_datos_base():
    """Crear datos base necesarios: profesores, inventario, auxiliares"""
    # Usar la sesión de SQLAlchemy dentro del contexto de Flask
    
    # Profesores de ejemplo
    profesores = [
        (12345678, "Ana María García", "ana.garcia@institucion.edu.co"),
        (23456789, "Carlos Eduardo López", "carlos.lopez@institucion.edu.co"),
        (34567890, "Diana Patricia Martínez", "diana.martinez@institucion.edu.co"),
        (45678901, "Eduardo Alejandro Ruiz", "eduardo.ruiz@institucion.edu.co"),
        (56789012, "Fernanda Isabel Castro", "fernanda.castro@institucion.edu.co"),
        (67890123, "Gabriel Antonio Silva", "gabriel.silva@institucion.edu.co"),
        (78901234, "Helena Victoria Torres", "helena.torres@institucion.edu.co"),
        (89012345, "Ignacio Fernando Morales", "ignacio.morales@institucion.edu.co"),
        (90123456, "Julia Esperanza Jiménez", "julia.jimenez@institucion.edu.co"),
        (1234567, "Luis Miguel Herrera", "luis.herrera@institucion.edu.co"),
        (11223344, "Martha Lucía Vargas", "martha.vargas@institucion.edu.co"),
        (22334455, "Nelson Darío Ospina", "nelson.ospina@institucion.edu.co"),
        (33445566, "Olga Patricia Mendez", "olga.mendez@institucion.edu.co"),
        (44556677, "Pedro Alfonso Ramírez", "pedro.ramirez@institucion.edu.co"),
        (55667788, "Rocío Elena Delgado", "rocio.delgado@institucion.edu.co"),
    ]
    
    # Crear profesores si no existen
    for cedula, nombre, correo in profesores:
        if not Profesor.query.filter(Profesor.cedula == cedula).first():
            profesor = Profesor(cedula=cedula, nombre_completo=nombre, correo=correo)
            db.session.add(profesor)
    
    # Auxiliares adicionales
    auxiliares = [
        ("11111111", "Auxiliar Mañana 1", "aux1@institucion.edu.co", "auxiliar"),
        ("22222222", "Auxiliar Tarde 1", "aux2@institucion.edu.co", "auxiliar"),
        ("33333333", "Auxiliar Noche 1", "aux3@institucion.edu.co", "auxiliar"),
        ("44444444", "Auxiliar Mañana 2", "aux4@institucion.edu.co", "auxiliar"),
        ("55555555", "Auxiliar Admin 2", "aux5@institucion.edu.co", "admin"),
    ]
    
    for doc, nombre, correo, rol in auxiliares:
        if not Auxiliar.query.filter(Auxiliar.documento == doc).first():
            auxiliar = Auxiliar(
                documento=doc,
                nombre_completo=nombre,
                correo=correo,
                contraseña=generate_password_hash("123456"),
                rol=rol
            )
            db.session.add(auxiliar)
    
    # Inventario de equipos
    equipos = [
        ("Proyector Epson", "A001", "Proyector"),
        ("Proyector ViewSonic", "A002", "Proyector"),
        ("Proyector Sony", "A003", "Proyector"),
        ("Laptop HP", "B001", "Laptop"),
        ("Laptop Dell", "B002", "Laptop"),
        ("Laptop Lenovo", "B003", "Laptop"),
        ("Parlante JBL", "C001", "Audio"),
        ("Parlante Bose", "C002", "Audio"),
        ("Micrófono Inalámbrico", "D001", "Audio"),
        ("Micrófono de Solapa", "D002", "Audio"),
        ("Extensión Eléctrica", "E001", "Eléctrico"),
        ("Cable HDMI", "E002", "Cable"),
        ("Cable VGA", "E003", "Cable"),
        ("Adaptador USB", "E004", "Adaptador"),
        ("Cámara Web", "F001", "Video"),
        ("Trípode", "F002", "Soporte"),
        ("Pizarra Portátil", "G001", "Pizarra"),
        ("Mesa para Laptop", "G002", "Mesa"),
        ("Laser Pointer", "H001", "Puntero"),
        ("Tablet Android", "I001", "Tablet"),
    ]
    
    for item, numero_inventario, categoria in equipos:
        if not Inventario.query.filter(Inventario.numero_inventario == numero_inventario).first():
            equipo = Inventario(
                item=item,
                numero_inventario=numero_inventario,
                categoria=categoria,
                estado="Disponible"
            )
            db.session.add(equipo)
    
    db.session.commit()
    print("✓ Datos base creados: profesores, auxiliares e inventario")

def generar_prestamos_3_meses():
    """Genera préstamos de equipos para los últimos 3 meses (2 por día)"""
    # Obtener datos necesarios
    profesores = Profesor.query.all()
    auxiliares = Auxiliar.query.all()
    equipos = Inventario.query.all()
    
    if not profesores or not auxiliares or not equipos:
        print("❌ Error: Faltan datos base. Ejecuta crear_datos_base() primero")
        return
    
    # Fechas para los últimos 3 meses
    fecha_fin = datetime.now()
    fecha_inicio = fecha_fin - timedelta(days=90)
    
    jornadas = ["MAÑANA", "TARDE", "NOCHE"]
    ubicaciones = [f"Aula {i:03d}" for i in range(101, 131)]  # Aulas 101-130
    
    contador_prestamos = 0
    fecha_actual = fecha_inicio
    
    while fecha_actual <= fecha_fin:
        # Solo crear préstamos en días de semana (lunes a viernes)
        if fecha_actual.weekday() < 5:  # 0-4 son lunes a viernes
            
            # 2 préstamos por día
            for prestamo_num in range(2):
                # Generar un grupo de préstamo único
                id_grupo = contador_prestamos + 1000  # ID numérico
                
                # Seleccionar datos aleatorios
                profesor = random.choice(profesores)
                auxiliar = random.choice(auxiliares)
                jornada = random.choice(jornadas)
                ubicacion = random.choice(ubicaciones)
                
                # Cantidad de equipos en este préstamo (1-4 equipos)
                num_equipos = random.randint(1, 4)
                equipos_prestamo = random.sample(equipos, num_equipos)
                
                # Horas de inicio y fin
                hora_inicio = random.randint(7, 17)
                duracion = random.randint(1, 4)  # 1-4 horas
                hora_fin = hora_inicio + duracion
                
                # Crear los registros de préstamo para cada equipo
                for equipo in equipos_prestamo:
                    from datetime import time
                    prestamo = PrestamoEquipo(
                        id_grupo_prestamo=id_grupo,
                        cedula_profesor=profesor.cedula,
                        nombre_profesor=profesor.nombre_completo,
                        equipo_prestado=equipo.item,
                        numero_inventario_equipo=equipo.numero_inventario,
                        ubicacion=ubicacion,
                        fecha_prestamo=fecha_actual.date(),
                        hora_inicio=time(hora_inicio, 0),
                        hora_fin=time(hora_fin, 0),
                        jornada=jornada,
                        estado=random.choice(["Prestado", "Devuelto"]) if fecha_actual < fecha_fin - timedelta(days=7) else "Devuelto",
                        auxiliar_entrega=auxiliar.documento,
                        auxiliar_recibe=auxiliar.documento if random.choice([True, False]) else None,
                        horas_academicas=duracion
                    )
                    db.session.add(prestamo)
                
                contador_prestamos += 1
        
        fecha_actual += timedelta(days=1)
    
    db.session.commit()
    print(f"✓ Generados {contador_prestamos} grupos de préstamo ({contador_prestamos * 2} préstamos individuales aprox.)")

def generar_reservas_3_meses():
    """Genera reservas de salones y niñeras para los últimos 3 meses"""
    profesores = Profesor.query.all()
    
    if not profesores:
        print("❌ Error: Faltan datos base")
        return
    
    # Fechas para los últimos 3 meses
    fecha_fin = datetime.now()
    fecha_inicio = fecha_fin - timedelta(days=90)
    
    # Recursos disponibles
    salones = [
        "Salón 201", "Salón 202", "Salón 203", "Salón 301", "Salón 302",
        "Auditorio Principal", "Sala de Juntas A", "Sala de Juntas B",
        "Laboratorio 1", "Laboratorio 2", "Aula Magna"
    ]
    
    nineras = [
        "María Elena Rodríguez", "Carmen Lucía Pérez", "Rosa María González",
        "Ana Patricia López", "Luz Marina Torres", "Gloria Esperanza Vargas",
        "Martha Isabel Castro", "Olga Lidia Moreno", "Teresa de Jesús Silva"
    ]
    
    jornadas = ["MAÑANA", "TARDE", "NOCHE"]
    tipos_recurso = ["salon", "ninera"]
    tipos_reserva = ["Clase", "Reunión", "Taller", "Conferencia"]
    
    contador_reservas = 0
    fecha_actual = fecha_inicio
    
    while fecha_actual <= fecha_fin:
        # Solo reservas en días de semana
        if fecha_actual.weekday() < 5:
            
            # 1-3 reservas por día
            num_reservas_dia = random.randint(1, 3)
            
            for _ in range(num_reservas_dia):
                profesor = random.choice(profesores)
                jornada = random.choice(jornadas)
                tipo_recurso = random.choice(tipos_recurso)
                
                # Seleccionar recurso según el tipo
                if tipo_recurso == "salon":
                    recurso = random.choice(salones)
                else:
                    recurso = random.choice(nineras)
                
                # Horas de inicio y fin
                hora_inicio = random.randint(7, 17)
                duracion = random.randint(1, 4)  # 1-4 horas de duración
                hora_fin = hora_inicio + duracion
                
                from datetime import time
                reserva = Reserva(
                    cedula_profesor=profesor.cedula,
                    nombre_profesor=profesor.nombre_completo,
                    recurso_tipo=tipo_recurso,
                    recurso_nombre=recurso,
                    fecha=fecha_actual.date(),
                    hora_inicio=time(hora_inicio, 0),
                    hora_fin=time(hora_fin, 0),
                    jornada=jornada,
                    tipo_reserva=random.choice(tipos_reserva),
                    estado=random.choice(["Activa", "Completada"]) if fecha_actual < fecha_fin - timedelta(days=3) else "Activa",
                    observaciones=random.choice([
                        "Clase magistral",
                        "Reunión académica", 
                        "Taller práctico",
                        "Evaluación",
                        "Conferencia",
                        "Cuidado durante examen",
                        "Apoyo clase especial",
                        ""
                    ])
                )
                db.session.add(reserva)
                contador_reservas += 1
        
        fecha_actual += timedelta(days=1)
    
    db.session.commit()
    print(f"✓ Generadas {contador_reservas} reservas de salones y niñeras")

def main():
    print("=== GENERADOR DE DATOS DE PRUEBA ===")
    print("Generando datos para los últimos 3 meses...\n")
    
    try:
        # 0. Inicializar Flask y base de datos
        print("0. Inicializando base de datos...")
        app = inicializar_flask_app()
        
        with app.app_context():
            # 1. Crear datos base
            print("1. Creando datos base...")
            crear_datos_base()
            
            # 2. Generar préstamos
            print("\n2. Generando préstamos de equipos...")
            generar_prestamos_3_meses()
            
            # 3. Generar reservas
            print("\n3. Generando reservas...")
            generar_reservas_3_meses()
            
            print("\n✅ ¡DATOS DE PRUEBA GENERADOS EXITOSAMENTE!")
            print("\nAhora puedes:")
            print("- Ver estadísticas completas en /estadisticas")
            print("- Filtrar por jornada (MAÑANA, TARDE, NOCHE)")
            print("- Ver préstamos en /prestamos_equipos")
            print("- Ver reservas en /reservas")
            print("\n¡Listo para hacer pruebas completas! 🚀")
        
    except Exception as e:
        print(f"❌ Error generando datos: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()