#!/usr/bin/env python3
"""
Script actualizado para generar datos de prueba en la base de datos correcta.
Usa la estructura real de la base de datos: instance/sistema_integrado.db
"""

import sqlite3
from datetime import date, datetime, time, timedelta
import random

def generar_datos_prueba():
    """Genera datos de prueba para testing del sistema."""
    db_path = 'instance/sistema_integrado.db'
    print("=" * 70)
    print("GENERACIÓN DE DATOS DE PRUEBA ACTUALIZADOS")
    print("=" * 70)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar que tenemos datos base
        cursor.execute("SELECT COUNT(*) FROM profesores")
        prof_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM inventario WHERE estado = 'Disponible'")
        inv_count = cursor.fetchone()[0]
        
        print(f"📊 Estado actual:")
        print(f"   - Profesores: {prof_count}")
        print(f"   - Inventario disponible: {inv_count}")
        
        if prof_count < 10 or inv_count < 5:
            print("⚠️ Se necesitan más datos base para generar pruebas significativas.")
            return
        
        # Obtener algunos profesores existentes
        cursor.execute("SELECT cedula, nombre_completo FROM profesores ORDER BY RANDOM() LIMIT 15")
        profesores = cursor.fetchall()
        
        # Obtener inventario disponible
        cursor.execute("""
            SELECT numero_inventario, item, marca_modelo 
            FROM inventario 
            WHERE estado = 'Disponible' 
            AND numero_inventario IS NOT NULL 
            AND numero_inventario != ''
            LIMIT 20
        """)
        inventario_disponible = cursor.fetchall()
        
        print(f"\\n🎯 Generando datos de prueba...")
        print(f"   - Usando {len(profesores)} profesores")
        print(f"   - Usando {len(inventario_disponible)} items de inventario")
        
        # Definir fechas para generar datos
        hoy = date.today()
        ayer = hoy - timedelta(days=1)
        manana = hoy + timedelta(days=1)
        semana_pasada = hoy - timedelta(days=7)
        
        fechas_prueba = []
        # Últimos 10 días
        for i in range(10, 0, -1):
            fechas_prueba.append(hoy - timedelta(days=i))
        # Hoy
        fechas_prueba.append(hoy)
        # Próximos 5 días
        for i in range(1, 6):
            fechas_prueba.append(hoy + timedelta(days=i))
        
        # Horarios típicos por jornada
        horarios_jornada = {
            'MAÑANA': [
                ('07:00', '09:30'), ('08:00', '10:30'), ('09:00', '11:30'),
                ('10:00', '12:30'), ('11:00', '13:00')
            ],
            'TARDE': [
                ('14:00', '16:30'), ('15:00', '17:30'), ('16:00', '18:00'),
                ('13:45', '16:00'), ('17:00', '18:14')
            ],
            'NOCHE': [
                ('18:15', '20:45'), ('19:00', '21:30'), ('20:00', '22:00')
            ]
        }
        
        ubicaciones = ['101', '102', '201', '202', '301', '302', '401', '402', '501', '502', '601', '602', 'Laboratorio', 'Oficina']
        
        prestamos_generados = 0
        reservas_generadas = 0
        
        print(f"\\n📝 Generando préstamos...")
        
        # Generar préstamos variados
        for fecha in fechas_prueba:
            # Determinar cuántos préstamos generar para esta fecha
            if fecha == hoy:
                num_prestamos = random.randint(3, 6)  # Más préstamos para hoy
            elif fecha < hoy:
                num_prestamos = random.randint(1, 4)  # Historial
            else:
                num_prestamos = random.randint(1, 3)  # Futuro
            
            for _ in range(num_prestamos):
                if not profesores or not inventario_disponible:
                    break
                
                profesor = random.choice(profesores)
                item = random.choice(inventario_disponible)
                jornada = random.choice(['MAÑANA', 'TARDE', 'NOCHE'])
                horario = random.choice(horarios_jornada[jornada])
                ubicacion = random.choice(ubicaciones)
                
                # Determinar estado del préstamo
                if fecha < hoy:
                    estado = 'Devuelto' if random.random() > 0.2 else 'Prestado'
                elif fecha == hoy:
                    estado = 'Prestado'
                else:
                    estado = 'Prestado'  # Préstamos futuros (programados)
                
                # Calcular horas académicas aproximadas
                inicio_time = datetime.strptime(horario[0], '%H:%M').time()
                fin_time = datetime.strptime(horario[1], '%H:%M').time()
                inicio_dt = datetime.combine(date.today(), inicio_time)
                fin_dt = datetime.combine(date.today(), fin_time)
                horas_academicas = round((fin_dt - inicio_dt).total_seconds() / 3600, 2)
                
                # Datos de devolución si está devuelto
                fecha_devolucion = None
                hora_devolucion_real = None
                auxiliar_recibe = None
                
                if estado == 'Devuelto':
                    # Fecha de devolución entre la fecha del préstamo y hoy
                    days_diff = (hoy - fecha).days
                    if days_diff > 0:
                        devolucion_offset = random.randint(0, min(days_diff, 3))
                        fecha_devolucion = fecha + timedelta(days=devolucion_offset)
                    else:
                        fecha_devolucion = fecha
                    
                    # Hora de devolución (un poco después de la hora fin prevista)
                    devolucion_minutes = random.randint(0, 120)  # 0-2 horas después
                    hora_devolucion_dt = fin_dt + timedelta(minutes=devolucion_minutes)
                    hora_devolucion_real = hora_devolucion_dt.time()
                    auxiliar_recibe = profesor[1]  # Por simplicidad, el mismo profesor
                
                try:
                    cursor.execute("""
                        INSERT INTO prestamos_equipos (
                            cedula_profesor, numero_inventario_equipo, equipo_prestado,
                            nombre_profesor, ubicacion, fecha_prestamo, jornada,
                            hora_inicio, hora_fin, horas_academicas, auxiliar_entrega,
                            auxiliar_recibe, hora_devolucion_real, fecha_devolucion,
                            observaciones, estado
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        profesor[0], item[0], f"{item[1]} ({item[2]})", profesor[1],
                        ubicacion, fecha.strftime('%Y-%m-%d'), jornada,
                        horario[0], horario[1], horas_academicas, profesor[1],
                        auxiliar_recibe,
                        hora_devolucion_real.strftime('%H:%M:%S') if hora_devolucion_real else None,
                        fecha_devolucion.strftime('%Y-%m-%d') if fecha_devolucion else None,
                        '', estado
                    ))
                    
                    prestamos_generados += 1
                    
                    # Actualizar inventario si el préstamo está activo
                    if estado == 'Prestado':
                        cursor.execute(
                            "UPDATE inventario SET estado = 'En Préstamo' WHERE numero_inventario = ?",
                            (item[0],)
                        )
                        # Remover de la lista de disponibles
                        inventario_disponible = [i for i in inventario_disponible if i[0] != item[0]]
                
                except sqlite3.IntegrityError:
                    # El ítem ya podría estar en préstamo, continuar
                    continue
        
        print(f"📝 Generando reservas...")
        
        # Recursos para reservas
        salones = ["LS1", "LS2", "LS3"]
        nineras = ["Niñera 1 (31 PC)", "Niñera 2 (31 PC)"]
        todos_recursos = [("Salón", s) for s in salones] + [("Niñera", n) for n in nineras]
        
        # Generar reservas
        for fecha in fechas_prueba:
            # Más reservas para fechas cercanas
            if fecha == hoy:
                num_reservas = random.randint(2, 4)
            elif abs((fecha - hoy).days) <= 3:
                num_reservas = random.randint(1, 3)
            else:
                num_reservas = random.randint(0, 2)
            
            for _ in range(num_reservas):
                if not profesores:
                    break
                
                profesor = random.choice(profesores)
                recurso_tipo, recurso_nombre = random.choice(todos_recursos)
                jornada = random.choice(['MAÑANA', 'TARDE', 'NOCHE'])
                horario = random.choice(horarios_jornada[jornada])
                nrc = f"{random.randint(10000, 99999)}"
                
                try:
                    cursor.execute("""
                        INSERT INTO reservas (
                            cedula_profesor, nombre_profesor, nrc, recurso_tipo,
                            recurso_nombre, fecha, jornada, hora_inicio, hora_fin,
                            tipo_reserva, estado, observaciones
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        profesor[0], profesor[1], nrc, recurso_tipo, recurso_nombre,
                        fecha.strftime('%Y-%m-%d'), jornada, horario[0], horario[1],
                        'Por Horario', 'Activa', f'Reserva generada para pruebas - {fecha}'
                    ))
                    
                    reservas_generadas += 1
                    
                except sqlite3.IntegrityError:
                    # Posible conflicto de horario, continuar
                    continue
        
        # Confirmar cambios
        conn.commit()
        
        # Estadísticas finales
        cursor.execute("SELECT COUNT(*) FROM prestamos_equipos WHERE estado = 'Prestado'")
        prestamos_activos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM prestamos_equipos WHERE estado = 'Devuelto'")
        prestamos_devueltos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reservas WHERE estado = 'Activa'")
        reservas_activas = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM prestamos_equipos WHERE date(fecha_prestamo) = '{hoy}'")
        prestamos_hoy = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM reservas WHERE date(fecha) = '{hoy}'")
        reservas_hoy = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"\\n✅ DATOS DE PRUEBA GENERADOS EXITOSAMENTE")
        print("=" * 50)
        print(f"📊 Préstamos generados: {prestamos_generados}")
        print(f"📊 Reservas generadas: {reservas_generadas}")
        print("\\n📈 Estado final del sistema:")
        print(f"   - Préstamos activos: {prestamos_activos}")
        print(f"   - Préstamos devueltos: {prestamos_devueltos}")
        print(f"   - Reservas activas: {reservas_activas}")
        print(f"\\n🎯 Para HOY ({hoy}):")
        print(f"   - Préstamos: {prestamos_hoy}")
        print(f"   - Reservas: {reservas_hoy}")
        
        print(f"\\n🎉 ¡Sistema listo para pruebas!")
        
    except Exception as e:
        print(f'❌ ERROR: {e}')
        if conn:
            conn.rollback()

if __name__ == '__main__':
    generar_datos_prueba()