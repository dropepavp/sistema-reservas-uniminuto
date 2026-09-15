#!/usr/bin/env python3
"""
Debug de la búsqueda de equipos
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import db, Inventario, PrestamoEquipo
from sqlalchemy import text, or_
from app import app

def debug_busqueda():
    """Debug de la búsqueda de equipos"""
    
    with app.app_context():
        try:
            print("=== DEBUG BÚSQUEDA DE LAPTOPS ===")
            
            # 1. Ver todas las laptops sin importar estado
            print("\n1. TODAS LAS LAPTOPS (sin filtro de estado):")
            all_laptops = db.session.query(Inventario).filter(
                or_(
                    Inventario.item.ilike('%portátil%'),
                    Inventario.item.ilike('%portatil%'),
                    Inventario.item.ilike('%laptop%')
                )
            ).order_by(Inventario.numero_inventario).all()
            
            print(f"Total encontradas: {len(all_laptops)}")
            for laptop in all_laptops:
                print(f"  {laptop.item} - {laptop.numero_inventario} - Estado: {laptop.estado}")
            
            # 2. Ver laptops disponibles
            print("\n2. LAPTOPS DISPONIBLES:")
            available_laptops = db.session.query(Inventario).filter(
                Inventario.estado == 'Disponible',
                or_(
                    Inventario.item.ilike('%portátil%'),
                    Inventario.item.ilike('%portatil%'),
                    Inventario.item.ilike('%laptop%')
                )
            ).order_by(Inventario.numero_inventario).all()
            
            print(f"Total disponibles: {len(available_laptops)}")
            for laptop in available_laptops:
                print(f"  {laptop.item} - {laptop.numero_inventario}")
            
            # 3. Verificar LAP01 específicamente
            print("\n3. VERIFICACIÓN ESPECÍFICA LAP01:")
            lap01 = db.session.query(Inventario).filter(
                Inventario.numero_inventario == 'LAP01'
            ).first()
            
            if lap01:
                print(f"  LAP01 encontrado: {lap01.item} - Estado: '{lap01.estado}'")
                print(f"  ¿Coincide con 'Disponible'?: {lap01.estado == 'Disponible'}")
                print(f"  ¿Coincide con laptop?: {'laptop' in lap01.item.lower()}")
            else:
                print("  LAP01 NO encontrado")
            
            # 4. Simular búsqueda exacta como la hace el sistema
            print("\n4. SIMULACIÓN BÚSQUEDA EXACTA (como el sistema):")
            query = db.session.query(Inventario).filter(
                Inventario.estado == 'Disponible'
            )
            
            # Aplicar filtro PORTATIL
            query = query.filter(
                or_(
                    Inventario.item.ilike('%portátil%'),
                    Inventario.item.ilike('%portatil%'),
                    Inventario.item.ilike('%laptop%')
                )
            )
            
            # Aplicar filtro por número 1
            query = query.filter(
                or_(
                    Inventario.numero_inventario.ilike('%1%'),
                    Inventario.activo_fijo.ilike('%1%')
                )
            )
            
            results = query.all()
            print(f"Resultados búsqueda '1': {len(results)}")
            for result in results:
                print(f"  {result.item} - {result.numero_inventario}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.session.close()

if __name__ == "__main__":
    debug_busqueda()
