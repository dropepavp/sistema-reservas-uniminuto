#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, render_template_string
from database import db, PrestamoEquipo, Inventario
from config import SystemConstants, config
from datetime import datetime, date
import os

def debug_ruta_prestamos():
    app = Flask(__name__)
    app.config.from_object(config[os.getenv('FLASK_CONFIG', 'development')])
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        print("=== DEBUG: SIMULANDO RUTA /prestamos_equipos EXACTA ===\n")
        
        # Reproducir exactamente la lógica de la ruta
        ESTADO_PRESTADO = SystemConstants.ESTADO_PRESTADO
        print(f"ESTADO_PRESTADO constant: '{ESTADO_PRESTADO}'")
        
        # --- Lógica para conteos de inventario ---
        disponibles_count = Inventario.query.filter_by(estado='Disponible').count()
        prestados_count = Inventario.query.filter_by(estado='En Préstamo').count()
        
        print(f"Inventario disponible: {disponibles_count}")
        print(f"Inventario en préstamo: {prestados_count}")
        
        # --- Filtrar para mostrar todos los préstamos activos ('Prestado') ---
        print(f"\n🔍 Ejecutando consulta: PrestamoEquipo.query.filter_by(estado='{ESTADO_PRESTADO}').order_by(desc).all()")
        prestamos_activos = PrestamoEquipo.query.filter_by(estado=ESTADO_PRESTADO).order_by(PrestamoEquipo.id_prestamo.desc()).all()
        
        print(f"Préstamos activos encontrados: {len(prestamos_activos)}")
        
        if len(prestamos_activos) > 0:
            print("\n✅ PRÉSTAMOS ENCONTRADOS - Primeros 3:")
            for i, p in enumerate(prestamos_activos[:3], 1):
                print(f"  {i}. ID: {p.id_prestamo} | Profesor: {p.nombre_profesor}")
                print(f"     Equipo: {p.equipo_prestado} | Fecha: {p.fecha_prestamo}")
                print(f"     Estado: '{p.estado}' | Ubicación: {p.ubicacion}")
                print()
        else:
            print("❌ NO SE ENCONTRARON PRÉSTAMOS ACTIVOS")
            
            # Investigar por qué
            print("\n🔍 INVESTIGANDO POSIBLES CAUSAS:")
            
            # Verificar todos los estados únicos
            all_prestamos = PrestamoEquipo.query.all()
            estados_unicos = set(p.estado for p in all_prestamos)
            print(f"Estados únicos en DB: {estados_unicos}")
            
            # Contar por estado
            for estado in estados_unicos:
                count = PrestamoEquipo.query.filter_by(estado=estado).count()
                print(f"  Estado '{estado}': {count} préstamos")
        
        # --- Lógica para notificaciones de préstamos vencidos ---
        prestamos_vencidos = []
        ahora = datetime.now()
        vencidos_query = PrestamoEquipo.query.filter(
            PrestamoEquipo.estado == ESTADO_PRESTADO
        ).all()
        
        print(f"\n🔍 Préstamos para verificar vencimiento: {len(vencidos_query)}")
        
        for prestamo in vencidos_query:
            try:
                # Combinar fecha del préstamo con la hora de fin prevista
                hora_devolucion_prevista = datetime.combine(prestamo.fecha_prestamo, prestamo.hora_fin)
                
                # Si la hora actual (sin timezone) es mayor que la hora de devolución prevista, está vencido
                if ahora > hora_devolucion_prevista:
                    prestamos_vencidos.append({
                        'nombre_profesor': prestamo.nombre_profesor,
                        'equipo_prestado': prestamo.equipo_prestado,
                        'hora_fin': prestamo.hora_fin.strftime('%H:%M')
                    })
            except (ValueError, TypeError) as e:
                print(f"Error procesando préstamo ID {prestamo.id_prestamo}: {e}")
                continue
        
        print(f"Préstamos vencidos: {len(prestamos_vencidos)}")
        
        # SIMULAR EL TEMPLATE
        print(f"\n📄 SIMULANDO TEMPLATE:")
        print(f"Variables que se pasarían al template:")
        print(f"  - prestamos: {len(prestamos_activos)} items")
        print(f"  - equipos: [] (vacío)")
        print(f"  - prestamos_vencidos: {len(prestamos_vencidos)} items")
        print(f"  - disponibles_count: {disponibles_count}")
        print(f"  - prestados_count: {prestados_count}")
        
        # Crear un mini-template para probar
        if len(prestamos_activos) > 0:
            template_test = """
            TEMPLATE TEST:
            {% for prestamo in prestamos %}
            - Préstamo {{ prestamo.id_prestamo }}: {{ prestamo.nombre_profesor }} - {{ prestamo.equipo_prestado }}
            {% else %}
            - NO HAY PRÉSTAMOS ACTIVOS
            {% endfor %}
            """
            
            try:
                resultado = render_template_string(template_test, prestamos=prestamos_activos)
                print(f"\n🎯 RESULTADO DEL TEMPLATE:")
                print(resultado)
            except Exception as e:
                print(f"❌ Error en template: {e}")
        else:
            print(f"\n❌ TEMPLATE MOSTRARÍA: 'No hay préstamos activos registrados.'")
        
        print(f"\n{'='*60}")
        print("💡 DIAGNÓSTICO FINAL:")
        if len(prestamos_activos) > 0:
            print("✅ Los datos están disponibles para mostrar en la tabla")
            print("⚠️  Si no se ven en el navegador, revisar:")
            print("   1. Templates HTML (errores de sintaxis)")
            print("   2. JavaScript que pueda estar ocultando filas")
            print("   3. CSS que pueda estar ocultando contenido")
            print("   4. Filtros del lado cliente")
        else:
            print("❌ NO hay datos para mostrar - problema en la consulta o constantes")

if __name__ == "__main__":
    debug_ruta_prestamos()