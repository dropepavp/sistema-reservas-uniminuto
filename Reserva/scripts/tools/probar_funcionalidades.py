#!/usr/bin/env python3
"""
Script final para probar las funcionalidades clave del sistema.
"""

import sqlite3
from datetime import date, datetime

def probar_funcionalidades():
    """Prueba las funcionalidades principales del sistema."""
    db_path = 'instance/sistema_integrado.db'
    print("=" * 70)
    print("PRUEBAS DE FUNCIONALIDADES CLAVE")
    print("=" * 70)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        hoy = date.today().strftime('%Y-%m-%d')
        
        # 1. PRUEBA DE PRÉSTAMOS ACTIVOS
        print("\\n1. 🔄 PRUEBA: PRÉSTAMOS ACTIVOS")
        print("-" * 50)
        
        cursor.execute("""
            SELECT id_prestamo, nombre_profesor, equipo_prestado, 
                   ubicacion, fecha_prestamo, estado
            FROM prestamos_equipos 
            WHERE estado = 'Prestado'
            ORDER BY fecha_prestamo DESC, hora_inicio
            LIMIT 10
        """)
        
        prestamos_activos = cursor.fetchall()
        print(f"📊 Préstamos activos encontrados: {len(prestamos_activos)}")
        
        for prestamo in prestamos_activos[:5]:
            print(f"   ✅ ID:{prestamo[0]} | {prestamo[1][:30]}... | {prestamo[2][:25]}... | {prestamo[3]} | {prestamo[4]}")
        
        if len(prestamos_activos) > 5:
            print(f"   ... y {len(prestamos_activos) - 5} más")
        
        # 2. PRUEBA DE RESERVAS ACTIVAS
        print("\\n2. 📅 PRUEBA: RESERVAS ACTIVAS")
        print("-" * 50)
        
        cursor.execute("""
            SELECT id_reserva, nombre_profesor, recurso_tipo, 
                   recurso_nombre, fecha, estado
            FROM reservas 
            WHERE estado = 'Activa'
            ORDER BY fecha, hora_inicio
            LIMIT 10
        """)
        
        reservas_activas = cursor.fetchall()
        print(f"📊 Reservas activas encontradas: {len(reservas_activas)}")
        
        for reserva in reservas_activas[:5]:
            print(f"   ✅ ID:{reserva[0]} | {reserva[1][:30]}... | {reserva[2]} {reserva[3]} | {reserva[4]}")
        
        if len(reservas_activas) > 5:
            print(f"   ... y {len(reservas_activas) - 5} más")
        
        # 3. PRUEBA DE DATOS PARA HOY
        print(f"\\n3. 🎯 PRUEBA: DATOS PARA HOY ({hoy})")
        print("-" * 50)
        
        cursor.execute("""
            SELECT COUNT(*) FROM prestamos_equipos 
            WHERE date(fecha_prestamo) = ? AND estado = 'Prestado'
        """, (hoy,))
        prestamos_hoy = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM reservas 
            WHERE date(fecha) = ? AND estado = 'Activa'
        """, (hoy,))
        reservas_hoy = cursor.fetchone()[0]
        
        print(f"🔄 Préstamos activos para hoy: {prestamos_hoy}")
        print(f"📅 Reservas activas para hoy: {reservas_hoy}")
        
        if prestamos_hoy > 0 or reservas_hoy > 0:
            print("   ✅ HAY DATOS PARA MOSTRAR EN LA INTERFAZ HOY")
        else:
            print("   ⚠️ NO HAY DATOS PARA HOY - Se verán páginas vacías")
        
        # 4. PRUEBA DE INVENTARIO
        print("\\n4. 📦 PRUEBA: ESTADO DEL INVENTARIO")
        print("-" * 50)
        
        cursor.execute("SELECT estado, COUNT(*) FROM inventario GROUP BY estado")
        estados_inventario = cursor.fetchall()
        
        for estado, count in estados_inventario:
            print(f"   📊 {estado}: {count} items")
        
        # Verificar consistencia
        cursor.execute("SELECT COUNT(*) FROM prestamos_equipos WHERE estado = 'Prestado'")
        prestamos_activos_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM inventario WHERE estado = 'En Préstamo'")
        inventario_prestado_count = cursor.fetchone()[0]
        
        if prestamos_activos_count == inventario_prestado_count:
            print("   ✅ Consistencia préstamos-inventario: OK")
        else:
            print(f"   ⚠️ INCONSISTENCIA: {prestamos_activos_count} préstamos activos vs {inventario_prestado_count} items en préstamo")
        
        # 5. PRUEBA DE PROFESORES
        print("\\n5. 👨‍🏫 PRUEBA: PROFESORES MÁS ACTIVOS")
        print("-" * 50)
        
        cursor.execute("""
            SELECT nombre_profesor, COUNT(*) as total_prestamos
            FROM prestamos_equipos 
            GROUP BY cedula_profesor, nombre_profesor 
            ORDER BY total_prestamos DESC 
            LIMIT 5
        """)
        
        profesores_activos = cursor.fetchall()
        
        for i, (profesor, count) in enumerate(profesores_activos, 1):
            print(f"   {i}. {profesor[:40]}... - {count} préstamos")
        
        # 6. PRUEBA DE FECHAS RECIENTES
        print("\\n6. 📅 PRUEBA: ACTIVIDAD RECIENTE")
        print("-" * 50)
        
        # Últimos 7 días
        cursor.execute("""
            SELECT fecha_prestamo, COUNT(*) 
            FROM prestamos_equipos 
            WHERE fecha_prestamo >= date('now', '-7 days')
            GROUP BY fecha_prestamo 
            ORDER BY fecha_prestamo DESC
        """)
        
        actividad_prestamos = cursor.fetchall()
        
        cursor.execute("""
            SELECT fecha, COUNT(*) 
            FROM reservas 
            WHERE fecha >= date('now', '-7 days')
            GROUP BY fecha 
            ORDER BY fecha DESC
        """)
        
        actividad_reservas = cursor.fetchall()
        
        print("📊 Préstamos por día (últimos 7 días):")
        for fecha, count in actividad_prestamos:
            print(f"   - {fecha}: {count}")
        
        print("\\n📊 Reservas por día (últimos 7 días):")
        for fecha, count in actividad_reservas:
            print(f"   - {fecha}: {count}")
        
        # 7. PRUEBA DE INTEGRIDAD GENERAL
        print("\\n7. 🔍 PRUEBA: INTEGRIDAD GENERAL")
        print("-" * 50)
        
        issues = []
        
        # Verificar profesores huérfanos
        cursor.execute("""
            SELECT COUNT(*) FROM prestamos_equipos p
            WHERE NOT EXISTS (
                SELECT 1 FROM profesores pr WHERE pr.cedula = p.cedula_profesor
            )
        """)
        prof_huerfanos = cursor.fetchone()[0]
        if prof_huerfanos > 0:
            issues.append(f"Profesores huérfanos en préstamos: {prof_huerfanos}")
        
        # Verificar equipos huérfanos
        cursor.execute("""
            SELECT COUNT(*) FROM prestamos_equipos p
            WHERE NOT EXISTS (
                SELECT 1 FROM inventario i WHERE i.numero_inventario = p.numero_inventario_equipo
            )
        """)
        equipos_huerfanos = cursor.fetchone()[0]
        if equipos_huerfanos > 0:
            issues.append(f"Equipos huérfanos en préstamos: {equipos_huerfanos}")
        
        # Verificar fechas nulas
        cursor.execute("SELECT COUNT(*) FROM prestamos_equipos WHERE fecha_prestamo IS NULL")
        fechas_nulas = cursor.fetchone()[0]
        if fechas_nulas > 0:
            issues.append(f"Préstamos sin fecha: {fechas_nulas}")
        
        if issues:
            for issue in issues:
                print(f"   ⚠️ {issue}")
        else:
            print("   ✅ Integridad general: OK")
        
        # 8. ESTADÍSTICAS FINALES
        print("\\n8. 📈 ESTADÍSTICAS FINALES")
        print("-" * 50)
        
        cursor.execute("SELECT COUNT(*) FROM prestamos_equipos")
        total_prestamos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reservas")
        total_reservas = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM profesores")
        total_profesores = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM inventario")
        total_inventario = cursor.fetchone()[0]
        
        print(f"📊 Total préstamos: {total_prestamos}")
        print(f"📊 Total reservas: {total_reservas}")
        print(f"📊 Total profesores: {total_profesores}")
        print(f"📊 Total inventario: {total_inventario}")
        
        conn.close()
        
        # REPORTE FINAL
        print("\\n" + "=" * 70)
        print("🎯 REPORTE FINAL DE FUNCIONALIDADES")
        print("=" * 70)
        
        funcionalidades_ok = []
        funcionalidades_warning = []
        
        if len(prestamos_activos) > 0:
            funcionalidades_ok.append("✅ Préstamos activos disponibles")
        else:
            funcionalidades_warning.append("⚠️ No hay préstamos activos")
        
        if len(reservas_activas) > 0:
            funcionalidades_ok.append("✅ Reservas activas disponibles")
        else:
            funcionalidades_warning.append("⚠️ No hay reservas activas")
        
        if prestamos_hoy > 0:
            funcionalidades_ok.append(f"✅ Préstamos para hoy: {prestamos_hoy}")
        else:
            funcionalidades_warning.append("⚠️ No hay préstamos para hoy")
        
        if reservas_hoy > 0:
            funcionalidades_ok.append(f"✅ Reservas para hoy: {reservas_hoy}")
        else:
            funcionalidades_warning.append("⚠️ No hay reservas para hoy")
        
        if prestamos_activos_count == inventario_prestado_count:
            funcionalidades_ok.append("✅ Consistencia inventario-préstamos")
        else:
            funcionalidades_warning.append("⚠️ Inconsistencia inventario-préstamos")
        
        if not issues:
            funcionalidades_ok.append("✅ Integridad de datos")
        else:
            funcionalidades_warning.append("⚠️ Problemas de integridad detectados")
        
        print("\\n🎉 FUNCIONALIDADES CORRECTAS:")
        for item in funcionalidades_ok:
            print(f"   {item}")
        
        if funcionalidades_warning:
            print("\\n⚠️ ADVERTENCIAS:")
            for item in funcionalidades_warning:
                print(f"   {item}")
        
        if len(funcionalidades_ok) >= 4 and len(funcionalidades_warning) <= 2:
            print("\\n🏆 SISTEMA LISTO PARA PRODUCCIÓN")
        else:
            print("\\n⚙️ Sistema funcional, puede requerir ajustes menores")
        
        print("\\n" + "=" * 70)
        print("✅ PRUEBAS DE FUNCIONALIDADES COMPLETADAS")
        print("=" * 70)
        
    except Exception as e:
        print(f'❌ ERROR: {e}')

if __name__ == '__main__':
    probar_funcionalidades()