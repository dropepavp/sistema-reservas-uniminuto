#!/usr/bin/env python3
"""
Script para debug de la ruta de inventario.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['DATABASE_URL'] = 'postgresql://postgres:Allison2023secure@localhost:5432/sistema_reserva'
os.environ['FLASK_ENV'] = 'development'

from app_improved import create_app
from database import db, Inventario, CategoriaInventario, Sede, Bodega

app = create_app('development')

with app.app_context():
    print("=" * 70)
    print("🔍 DEBUG: VERIFICANDO DATOS PARA RUTA /inventario/")
    print("=" * 70)
    
    # Test 1: Items en inventario
    print("\n1️⃣  ITEMS EN INVENTARIO:")
    inventario_list = Inventario.query.all()
    print(f"   Total: {len(inventario_list)}")
    for item in inventario_list[:3]:
        print(f"     • {item.id}: {item.item} ({item.categoria})")
    if len(inventario_list) == 0:
        print("   ❌ NO HAY ITEMS!")
    
    # Test 2: Categorías
    print("\n2️⃣  CATEGORÍAS EN BD:")
    categorias_db = CategoriaInventario.query.all()
    print(f"   Total: {len(categorias_db)}")
    for cat in categorias_db:
        print(f"     • {cat.nombre}")
    if len(categorias_db) == 0:
        print("   ❌ NO HAY CATEGORÍAS!")
    
    # Test 3: Sedes
    print("\n3️⃣  SEDES EN BD:")
    sedes = Sede.query.all()
    print(f"   Total: {len(sedes)}")
    for sede in sedes:
        print(f"     • {sede.nombre}")
    
    # Test 4: Bodegas
    print("\n4️⃣  BODEGAS EN BD:")
    bodegas = Bodega.query.all()
    print(f"   Total: {len(bodegas)}")
    for bodega in bodegas:
        sede_name = bodega.sede.nombre if bodega.sede else "SIN SEDE"
        print(f"     • {bodega.nombre} (Sede: {sede_name})")
    
    # Test 5: Estadísticas
    print("\n5️⃣  ESTADÍSTICAS:")
    try:
        disponibles = Inventario.query.filter(Inventario.estado == 'Disponible').count()
        print(f"   Disponibles: {disponibles}")
    except Exception as e:
        print(f"   Error contando disponibles: {e}")
    
    print("\n" + "=" * 70)
    print("✅ Si todo muestra números > 0, los datos están correctos")
    print("=" * 70)
