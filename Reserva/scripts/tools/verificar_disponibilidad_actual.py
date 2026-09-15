#!/usr/bin/env python3
"""
Verifica el estado actual de disponibilidad de equipos
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import db, Inventario, PrestamoEquipo
from sqlalchemy import text
from app import app

def verificar_disponibilidad():
    """Verifica qué equipos están disponibles"""
    
    with app.app_context():
        try:
            # Verificar laptops disponibles
            print("=== LAPTOPS DISPONIBLES ===")
            laptops = db.session.query(Inventario).filter(
                Inventario.estado == 'Disponible',
                Inventario.item.ilike('%portátil%')
            ).order_by(Inventario.numero_inventario).all()
            
            if not laptops:
                print("❌ No hay laptops disponibles")
            else:
                for laptop in laptops:
                    print(f"✅ {laptop.item} - {laptop.numero_inventario} - {laptop.marca_modelo or 'Sin marca'}")
            
            print(f"\nTotal laptops disponibles: {len(laptops)}")
            
            # Verificar préstamos activos de laptops
            print("\n=== LAPTOPS EN PRÉSTAMO ACTIVO ===")
            prestamos_laptops = db.session.query(PrestamoEquipo).filter(
                PrestamoEquipo.estado == 'Prestado',
                PrestamoEquipo.equipo_prestado.ilike('%portátil%')
            ).order_by(PrestamoEquipo.numero_inventario_equipo).all()
            
            if not prestamos_laptops:
                print("✅ No hay laptops en préstamo")
            else:
                for prestamo in prestamos_laptops:
                    print(f"🔴 {prestamo.equipo_prestado} - {prestamo.numero_inventario_equipo} - Profesor: {prestamo.nombre_profesor}")
            
            print(f"\nTotal laptops en préstamo: {len(prestamos_laptops)}")
            
            # Verificar específicamente LAP01, LAP05, LAP10
            print("\n=== ESTADO DE LAPTOPS ESPECÍFICOS ===")
            especificos = ['LAP01', 'LAP05', 'LAP10']
            for num in especificos:
                inventario = db.session.query(Inventario).filter(
                    Inventario.numero_inventario == num
                ).first()
                
                if inventario:
                    print(f"📋 {num}: {inventario.item} - Estado: {inventario.estado}")
                    
                    # Verificar si está en préstamo
                    prestamo = db.session.query(PrestamoEquipo).filter(
                        PrestamoEquipo.numero_inventario_equipo == num,
                        PrestamoEquipo.estado == 'Prestado'
                    ).first()
                    
                    if prestamo:
                        print(f"   🔴 En préstamo a: {prestamo.nombre_profesor}")
                    else:
                        print(f"   ✅ Disponible")
                else:
                    print(f"❌ {num}: No encontrado en inventario")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            db.session.close()

if __name__ == "__main__":
    verificar_disponibilidad()
