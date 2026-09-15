#!/usr/bin/env python3
"""
Script para realizar una revisión completa del sistema.
"""

import sqlite3
from datetime import date, datetime, timedelta
import os

def revisar_base_datos():
    """Revisa el estado completo de la base de datos."""
    db_path = 'instance/sistema_integrado.db'
    print("=" * 60)
    print("REVISIÓN COMPLETA DEL SISTEMA")
    print("=" * 60)
    print(f'\nBase de datos: {db_path}')
    print(f'Archivo existe: {os.path.exists(db_path)}')
    
    if not os.path.exists(db_path):
        print('❌ ERROR: La base de datos no existe.')
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. VERIFICAR TABLAS Y ESTRUCTURA
        print("\n" + "="*50)
        print("1. ESTRUCTURA DE LA BASE DE DATOS")
        print("="*50)
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        
        for table_name in [t[0] for t in tables]:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f'📊 {table_name}: {count} registros')
        
        # 2. REVISAR PRÉSTAMOS DETALLADO
        print("\n" + "="*50)
        print("2. ANÁLISIS DE PRÉSTAMOS")
        print("="*50)
        
        # Estados de préstamos
        cursor.execute("SELECT estado, COUNT(*) FROM prestamos_equipos GROUP BY estado")
        estados = cursor.fetchall()
        print("\n📈 Préstamos por estado:")
        for estado, count in estados:
            print(f"  - {estado}: {count}")
        
        # Préstamos por fecha (últimos 7 días)
        today = date.today()
        week_ago = today - timedelta(days=7)
        
        cursor.execute("""
            SELECT fecha_prestamo, COUNT(*) 
            FROM prestamos_equipos 
            WHERE fecha_prestamo >= ? 
            GROUP BY fecha_prestamo 
            ORDER BY fecha_prestamo DESC
        """, (week_ago.strftime('%Y-%m-%d'),))
        
        fechas = cursor.fetchall()
        print(f"\n📅 Préstamos últimos 7 días:")
        for fecha, count in fechas:
            print(f"  - {fecha}: {count}")
        
        # Préstamos activos de hoy
        today_str = today.strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT id_prestamo, nombre_profesor, equipo_prestado, ubicacion, 
                   hora_inicio, hora_fin, estado
            FROM prestamos_equipos 
            WHERE date(fecha_prestamo) = ? AND estado = 'Prestado'
            ORDER BY hora_inicio
        """, (today_str,))
        
        prestamos_hoy = cursor.fetchall()
        print(f"\n🔄 Préstamos ACTIVOS para HOY ({today_str}): {len(prestamos_hoy)}")
        for prestamo in prestamos_hoy:
            print(f"  - ID:{prestamo[0]} | {prestamo[1]} | {prestamo[2]} | {prestamo[3]} | {prestamo[4]}-{prestamo[5]} | {prestamo[6]}")
        
        # 3. REVISAR RESERVAS DETALLADO
        print("\n" + "="*50)
        print("3. ANÁLISIS DE RESERVAS")
        print("="*50)
        
        # Estados de reservas
        cursor.execute("SELECT estado, COUNT(*) FROM reservas GROUP BY estado")
        estados_res = cursor.fetchall()
        print("\n📈 Reservas por estado:")
        for estado, count in estados_res:
            print(f"  - {estado}: {count}")
        
        # Reservas por tipo de recurso
        cursor.execute("SELECT recurso_tipo, COUNT(*) FROM reservas GROUP BY recurso_tipo")
        tipos = cursor.fetchall()
        print(f"\n🏢 Reservas por tipo de recurso:")
        for tipo, count in tipos:
            print(f"  - {tipo}: {count}")
        
        # Reservas activas de hoy
        cursor.execute("""
            SELECT id_reserva, nombre_profesor, recurso_tipo, recurso_nombre, 
                   hora_inicio, hora_fin, estado
            FROM reservas 
            WHERE date(fecha) = ? AND estado = 'Activa'
            ORDER BY hora_inicio
        """, (today_str,))
        
        reservas_hoy = cursor.fetchall()
        print(f"\n🔄 Reservas ACTIVAS para HOY ({today_str}): {len(reservas_hoy)}")
        for reserva in reservas_hoy:
            print(f"  - ID:{reserva[0]} | {reserva[1]} | {reserva[2]} {reserva[3]} | {reserva[4]}-{reserva[5]} | {reserva[6]}")
        
        # 4. REVISAR INVENTARIO
        print("\n" + "="*50)
        print("4. ANÁLISIS DE INVENTARIO")
        print("="*50)
        
        # Estados del inventario
        cursor.execute("SELECT estado, COUNT(*) FROM inventario GROUP BY estado")
        estados_inv = cursor.fetchall()
        print("\n📦 Inventario por estado:")
        for estado, count in estados_inv:
            print(f"  - {estado}: {count}")
        
        # Inventario por categoría
        cursor.execute("SELECT categoria, COUNT(*) FROM inventario GROUP BY categoria")
        categorias = cursor.fetchall()
        print(f"\n📂 Inventario por categoría:")
        for categoria, count in categorias:
            print(f"  - {categoria}: {count}")
        
        # 5. REVISAR PROFESORES Y AUXILIARES
        print("\n" + "="*50)
        print("5. USUARIOS DEL SISTEMA")
        print("="*50)
        
        cursor.execute("SELECT COUNT(*) FROM profesores")
        prof_count = cursor.fetchone()[0]
        print(f"👨‍🏫 Profesores registrados: {prof_count}")
        
        cursor.execute("SELECT COUNT(*) FROM auxiliares")
        aux_count = cursor.fetchone()[0]
        print(f"👨‍💼 Auxiliares registrados: {aux_count}")
        
        # Profesores con más préstamos
        cursor.execute("""
            SELECT nombre_profesor, COUNT(*) as total_prestamos
            FROM prestamos_equipos 
            GROUP BY cedula_profesor, nombre_profesor 
            ORDER BY total_prestamos DESC 
            LIMIT 5
        """)
        top_profesores = cursor.fetchall()
        print(f"\n🏆 Top 5 profesores con más préstamos:")
        for prof, count in top_profesores:
            print(f"  - {prof}: {count} préstamos")
        
        # 6. VERIFICAR DATOS DE FECHAS ESPECÍFICAS
        print("\n" + "="*50)
        print("6. VERIFICACIÓN POR FECHAS CLAVE")
        print("="*50)
        
        # Ayer
        yesterday = (today - timedelta(days=1)).strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) FROM prestamos_equipos WHERE date(fecha_prestamo) = ?", (yesterday,))
        ayer_prestamos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reservas WHERE date(fecha) = ?", (yesterday,))
        ayer_reservas = cursor.fetchone()[0]
        
        print(f"📅 Ayer ({yesterday}):")
        print(f"  - Préstamos: {ayer_prestamos}")
        print(f"  - Reservas: {ayer_reservas}")
        
        # Mañana
        tomorrow = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) FROM prestamos_equipos WHERE date(fecha_prestamo) = ?", (tomorrow,))
        manana_prestamos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reservas WHERE date(fecha) = ?", (tomorrow,))
        manana_reservas = cursor.fetchone()[0]
        
        print(f"📅 Mañana ({tomorrow}):")
        print(f"  - Préstamos: {manana_prestamos}")
        print(f"  - Reservas: {manana_reservas}")
        
        # 7. VERIFICAR INTEGRIDAD DE DATOS
        print("\n" + "="*50)
        print("7. VERIFICACIÓN DE INTEGRIDAD")
        print("="*50)
        
        # Préstamos sin devolución que deberían estar devueltos
        cursor.execute("""
            SELECT COUNT(*) FROM prestamos_equipos 
            WHERE estado = 'Prestado' 
            AND date(fecha_prestamo) < date('now', '-1 day')
        """)
        vencidos = cursor.fetchone()[0]
        print(f"⚠️  Préstamos potencialmente vencidos: {vencidos}")
        
        # Inventario inconsistente
        cursor.execute("""
            SELECT COUNT(*) FROM inventario i
            WHERE i.estado = 'En Préstamo' 
            AND i.numero_inventario NOT IN (
                SELECT numero_inventario_equipo 
                FROM prestamos_equipos 
                WHERE estado = 'Prestado'
            )
        """)
        inconsistente = cursor.fetchone()[0]
        print(f"⚠️  Inventario marcado como 'En Préstamo' sin préstamo activo: {inconsistente}")
        
        conn.close()
        
        print("\n" + "="*60)
        print("✅ REVISIÓN COMPLETADA")
        print("="*60)
        
    except Exception as e:
        print(f'❌ ERROR: {e}')

if __name__ == '__main__':
    revisar_base_datos()