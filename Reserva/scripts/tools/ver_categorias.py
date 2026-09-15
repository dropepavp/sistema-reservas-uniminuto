"""
Script para ver las categorías reales en la base de datos
"""
from database import db, CategoriaInventario, Inventario
from app import app
from sqlalchemy import func

with app.app_context():
    print("=" * 60)
    print("📋 CATEGORÍAS EN LA BASE DE DATOS")
    print("=" * 60)
    
    # Categorías de la tabla CategoriaInventario
    categorias_db = CategoriaInventario.query.all()
    print(f"\n✅ Categorías registradas ({len(categorias_db)}):")
    for cat in categorias_db:
        print(f"   - {cat.nombre}")
    
    # Categorías realmente usadas en el inventario
    print(f"\n📦 Categorías en uso en el inventario:")
    categorias_usadas = db.session.query(
        Inventario.categoria, 
        func.count(Inventario.id).label('count')
    ).group_by(Inventario.categoria).order_by(func.count(Inventario.id).desc()).all()
    
    for cat, count in categorias_usadas:
        print(f"   - {cat}: {count} items")
    
    print("\n" + "=" * 60)
