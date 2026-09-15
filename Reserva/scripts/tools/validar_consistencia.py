#!/usr/bin/env python3
"""
Script para validar y corregir inconsistencias en los datos del sistema.
"""

import sqlite3
from datetime import date, datetime

def corregir_inconsistencias():
    """Valida y corrige inconsistencias en los datos."""
    db_path = 'instance/sistema_integrado.db'
    print("=" * 60)
    print("VALIDACIÓN Y CORRECCIÓN DE INCONSISTENCIAS")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. VERIFICAR Y CORREGIR INVENTARIO INCONSISTENTE
        print("\n1. 🔍 REVISANDO INVENTARIO INCONSISTENTE")
        print("-" * 50)
        
        # Encontrar inventario marcado como 'En Préstamo' sin préstamo activo
        cursor.execute("""
            SELECT i.id, i.numero_inventario, i.item, i.estado
            FROM inventario i
            WHERE i.estado = 'En Préstamo' 
            AND i.numero_inventario NOT IN (
                SELECT numero_inventario_equipo 
                FROM prestamos_equipos 
                WHERE estado = 'Prestado'
            )
        """)
        
        inventario_inconsistente = cursor.fetchall()
        
        if inventario_inconsistente:
            print(f"⚠️  Encontrados {len(inventario_inconsistente)} items inconsistentes:")
            for item in inventario_inconsistente:
                print(f"   - ID {item[0]}: {item[2]} (Nº {item[1]}) - Estado: {item[3]}")
            
            # Corregir automáticamente
            respuesta = input("\n¿Deseas corregir estos items marcándolos como 'Disponible'? (s/n): ")
            if respuesta.lower() in ['s', 'si', 'y', 'yes']:
                for item in inventario_inconsistente:
                    cursor.execute(
                        "UPDATE inventario SET estado = 'Disponible' WHERE id = ?",
                        (item[0],)
                    )
                print("✅ Items corregidos automáticamente.")
            else:
                print("⏭️  Corrección omitida.")
        else:
            print("✅ No se encontraron inconsistencias en el inventario.")
        
        # 2. VERIFICAR PRÉSTAMOS CON FECHAS INVÁLIDAS
        print("\n2. 🔍 REVISANDO FECHAS DE PRÉSTAMOS")
        print("-" * 50)
        
        cursor.execute("""
            SELECT id_prestamo, nombre_profesor, fecha_prestamo, estado
            FROM prestamos_equipos
            WHERE fecha_prestamo IS NULL 
            OR fecha_prestamo = ''
        """)
        
        prestamos_sin_fecha = cursor.fetchall()
        
        if prestamos_sin_fecha:
            print(f"⚠️  Encontrados {len(prestamos_sin_fecha)} préstamos sin fecha válida:")
            for prestamo in prestamos_sin_fecha:
                print(f"   - ID {prestamo[0]}: {prestamo[1]} - Estado: {prestamo[3]}")
        else:
            print("✅ Todas las fechas de préstamos son válidas.")
        
        # 3. VERIFICAR RESERVAS CON FECHAS INVÁLIDAS
        print("\n3. 🔍 REVISANDO FECHAS DE RESERVAS")
        print("-" * 50)
        
        cursor.execute("""
            SELECT id_reserva, nombre_profesor, fecha, estado
            FROM reservas
            WHERE fecha IS NULL 
            OR fecha = ''
        """)
        
        reservas_sin_fecha = cursor.fetchall()
        
        if reservas_sin_fecha:
            print(f"⚠️  Encontradas {len(reservas_sin_fecha)} reservas sin fecha válida:")
            for reserva in reservas_sin_fecha:
                print(f"   - ID {reserva[0]}: {reserva[1]} - Estado: {reserva[3]}")
        else:
            print("✅ Todas las fechas de reservas son válidas.")
        
        # 4. VERIFICAR PROFESORES HUÉRFANOS
        print("\n4. 🔍 REVISANDO PROFESORES HUÉRFANOS")
        print("-" * 50)
        
        # Profesores en préstamos que no existen en la tabla profesores
        cursor.execute("""
            SELECT DISTINCT cedula_profesor, nombre_profesor
            FROM prestamos_equipos p
            WHERE NOT EXISTS (
                SELECT 1 FROM profesores pr 
                WHERE pr.cedula = p.cedula_profesor
            )
        """)
        
        profesores_huerfanos_prestamos = cursor.fetchall()
        
        if profesores_huerfanos_prestamos:
            print(f"⚠️  Profesores en préstamos sin registro: {len(profesores_huerfanos_prestamos)}")
            for prof in profesores_huerfanos_prestamos:
                print(f"   - Cédula: {prof[0]} - Nombre: {prof[1]}")
        else:
            print("✅ Todos los profesores en préstamos tienen registro válido.")
        
        # 5. ACTUALIZAR ESTADÍSTICAS GENERALES
        print("\n5. 📊 ESTADÍSTICAS ACTUALIZADAS")
        print("-" * 50)
        
        # Conteos actualizados
        cursor.execute("SELECT COUNT(*) FROM prestamos_equipos WHERE estado = 'Prestado'")
        prestamos_activos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reservas WHERE estado = 'Activa'")
        reservas_activas = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM inventario WHERE estado = 'Disponible'")
        inventario_disponible = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM inventario WHERE estado = 'En Préstamo'")
        inventario_prestado = cursor.fetchone()[0]
        
        print(f"📈 Préstamos activos: {prestamos_activos}")
        print(f"📅 Reservas activas: {reservas_activas}")
        print(f"📦 Inventario disponible: {inventario_disponible}")
        print(f"🔄 Inventario en préstamo: {inventario_prestado}")
        
        # Verificar que los conteos coincidan
        if prestamos_activos != inventario_prestado:
            print(f"⚠️  INCONSISTENCIA: {prestamos_activos} préstamos activos vs {inventario_prestado} items en préstamo")
        else:
            print("✅ Conteos de préstamos e inventario son consistentes.")
        
        # 6. GENERAR REPORTE DE SALUD DEL SISTEMA
        print("\n6. 🏥 REPORTE DE SALUD DEL SISTEMA")
        print("-" * 50)
        
        issues_found = 0
        issues_found += len(inventario_inconsistente)
        issues_found += len(prestamos_sin_fecha)
        issues_found += len(reservas_sin_fecha)
        issues_found += len(profesores_huerfanos_prestamos)
        
        if prestamos_activos != inventario_prestado:
            issues_found += 1
        
        if issues_found == 0:
            print("🎉 ¡SISTEMA EN PERFECTO ESTADO!")
            print("   No se encontraron inconsistencias.")
        else:
            print(f"⚠️  SE ENCONTRARON {issues_found} PROBLEMAS")
            print("   Revisa los detalles arriba y toma las acciones necesarias.")
        
        # Confirmar cambios
        if conn.in_transaction:
            conn.commit()
            print("\n✅ Cambios guardados en la base de datos.")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("VALIDACIÓN COMPLETADA")
        print("=" * 60)
        
    except Exception as e:
        print(f'❌ ERROR: {e}')

if __name__ == '__main__':
    corregir_inconsistencias()