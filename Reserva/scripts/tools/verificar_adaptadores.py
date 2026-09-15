#!/usr/bin/env python3
"""
Script para verificar que existen adaptadores disponibles en el inventario
"""

from app import app, db
from database import Inventario

def verificar_adaptadores():
    with app.app_context():
        print("=" * 60)
        print("🔍 VERIFICACIÓN DE ADAPTADORES EN INVENTARIO")
        print("=" * 60)
        
        # Buscar todos los adaptadores/cargadores
        adaptadores = Inventario.query.filter(
            db.or_(
                Inventario.item.ilike('%cargador%'),
                Inventario.item.ilike('%adaptador%')
            )
        ).all()
        
        print(f"\n📊 Total de adaptadores/cargadores encontrados: {len(adaptadores)}")
        
        if not adaptadores:
            print("❌ No se encontraron adaptadores en el inventario")
            return
        
        # Agrupar por estado
        disponibles = [a for a in adaptadores if a.estado == 'Disponible']
        prestados = [a for a in adaptadores if a.estado == 'Prestado']
        otros = [a for a in adaptadores if a.estado not in ('Disponible', 'Prestado')]
        
        print(f"\n✅ Disponibles: {len(disponibles)}")
        print(f"🔄 Prestados: {len(prestados)}")
        print(f"⚠️  Otros estados: {len(otros)}")
        
        # Mostrar adaptadores disponibles
        if disponibles:
            print("\n" + "=" * 60)
            print("📋 ADAPTADORES DISPONIBLES:")
            print("=" * 60)
            for i, adap in enumerate(disponibles[:10], 1):  # Mostrar máximo 10
                print(f"\n{i}. {adap.item}")
                print(f"   Número Inventario: {adap.numero_inventario}")
                print(f"   Activo Fijo: {adap.activo_fijo or 'N/A'}")
                print(f"   Marca: {adap.marca_modelo or 'N/A'}")
                print(f"   Serial: {adap.serial or 'N/A'}")
                print(f"   Bodega: {adap.bodega.nombre if adap.bodega else 'N/A'}")
                print(f"   Sede: {adap.bodega.sede.nombre if adap.bodega and adap.bodega.sede else 'N/A'}")
                print(f"   Estado: {adap.estado}")
            
            if len(disponibles) > 10:
                print(f"\n... y {len(disponibles) - 10} más")
        
        # Mostrar algunos prestados para referencia
        if prestados:
            print("\n" + "=" * 60)
            print("📋 ADAPTADORES PRESTADOS (primeros 5):")
            print("=" * 60)
            for i, adap in enumerate(prestados[:5], 1):
                print(f"\n{i}. {adap.item}")
                print(f"   Número Inventario: {adap.numero_inventario}")
                print(f"   Estado: {adap.estado}")
        
        # Verificar si hay teclados (para comparar)
        print("\n" + "=" * 60)
        print("🔍 COMPARACIÓN CON TECLADOS:")
        print("=" * 60)
        
        teclados = Inventario.query.filter(
            Inventario.item.ilike('%teclado%')
        ).all()
        
        teclados_disponibles = [t for t in teclados if t.estado == 'Disponible']
        
        print(f"⌨️  Total teclados: {len(teclados)}")
        print(f"✅ Teclados disponibles: {len(teclados_disponibles)}")
        
        if teclados_disponibles:
            print("\nPrimeros 3 teclados disponibles:")
            for i, tec in enumerate(teclados_disponibles[:3], 1):
                print(f"  {i}. {tec.item} - {tec.numero_inventario}")
        
        print("\n" + "=" * 60)
        print("✅ VERIFICACIÓN COMPLETADA")
        print("=" * 60)
        
        # Resumen
        print("\n📊 RESUMEN:")
        print(f"   • Adaptadores disponibles: {len(disponibles)}")
        print(f"   • Teclados disponibles: {len(teclados_disponibles)}")
        print(f"\n💡 Si el botón 'Cargador' muestra teclados, es problema de caché del navegador")
        print(f"   El backend tiene {len(disponibles)} adaptadores listos para mostrar")

if __name__ == '__main__':
    verificar_adaptadores()
