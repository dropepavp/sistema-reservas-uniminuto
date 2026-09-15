#!/usr/bin/env python3
"""
Debug específico para LAP01
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import db, Inventario, PrestamoEquipo
from sqlalchemy import text, or_
from app import app

def debug_lap01():
    """Debug específico para LAP01"""
    
    with app.app_context():
        try:
            print("=== DEBUG ESPECÍFICO LAP01 ===")
            
            # 1. Ver LAP01 en inventario
            print("\n1. LAP01 EN INVENTARIO:")
            lap01 = db.session.query(Inventario).filter(
                Inventario.numero_inventario == 'LAP01'
            ).first()
            
            if lap01:
                print(f"  LAP01 encontrado: {lap01.item}")
                print(f"  Estado: '{lap01.estado}'")
                print(f"  ¿Es 'Disponible'?: {lap01.estado == 'Disponible'}")
            else:
                print("  ❌ LAP01 NO encontrado en inventario")
                return
            
            # 2. Verificar si tiene préstamos activos
            print("\n2. PRÉSTAMOS ACTIVOS DE LAP01:")
            prestamos_activos = db.session.query(PrestamoEquipo).filter(
                PrestamoEquipo.numero_inventario_equipo == 'LAP01',
                PrestamoEquipo.estado == 'Prestado'
            ).all()
            
            print(f"  Total préstamos activos: {len(prestamos_activos)}")
            for prestamo in prestamos_activos:
                print(f"    - Préstamo {prestamo.id_prestamo}: {prestamo.nombre_profesor} ({prestamo.documento_profesor})")
            
            # 3. Simular búsqueda como la hace el sistema
            print("\n3. SIMULACIÓN BÚSQUEDA SISTEMA:")
            query = db.session.query(Inventario).filter(
                Inventario.estado.in_(['Disponible', 'En Préstamo'])
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
            
            # Aplicar ordenamiento
            query = query.order_by(
                db.case(
                    (Inventario.numero_inventario == '1', 1),
                    (Inventario.activo_fijo == '1', 1),
                    else_=2
                ),
                db.func.length(Inventario.numero_inventario),
                Inventario.numero_inventario
            )
            
            results = query.limit(50).all()
            
            print(f"  Resultados búsqueda '1': {len(results)}")
            for i, result in enumerate(results[:5], 1):
                print(f"    {i}. {result.item} - {result.numero_inventario} - Estado: {result.estado}")
                
                # Verificar si tiene préstamo activo
                prestamo_activo = db.session.query(PrestamoEquipo).filter(
                    PrestamoEquipo.numero_inventario_equipo == result.numero_inventario,
                    PrestamoEquipo.estado == 'Prestado'
                ).first()
                
                if prestamo_activo:
                    print(f"       🔴 PRESTADO a: {prestamo_activo.nombre_profesor}")
                    disponible = False
                else:
                    print(f"       ✅ DISPONIBLE")
                    disponible = True
                
                # Verificar si el backend lo marcaría correctamente
                if result.numero_inventario == 'LAP01':
                    print(f"       *** LAP01: ¿Disponible según backend?: {disponible}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.session.close()

if __name__ == "__main__":
    debug_lap01()
