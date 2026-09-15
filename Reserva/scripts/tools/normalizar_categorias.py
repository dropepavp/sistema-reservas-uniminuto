"""
Script para normalizar las categorías del inventario
"""
from database import db, Inventario, CategoriaInventario
from app import app

# Mapeo de categorías antiguas a nuevas
MAPEO_CATEGORIAS = {
    'PORTATIL': 'Equipos Portátiles',
    'portatil': 'Equipos Portátiles',
    'laptop': 'Equipos Portátiles',
    'laptops': 'Equipos Portátiles',
    
    'PERIFERICOS': 'Periféricos (Teclados, Mouse)',
    'perifericos': 'Periféricos (Teclados, Mouse)',
    'periferico': 'Periféricos (Teclados, Mouse)',
    
    'adaptadores de corriente': 'Adaptadores de corriente',
    'ADAPTADORES': 'Adaptadores de corriente',
    'adaptador': 'Adaptadores de corriente',
}

with app.app_context():
    print("=" * 60)
    print("🔄 NORMALIZACIÓN DE CATEGORÍAS")
    print("=" * 60)
    
    actualizados = 0
    
    for categoria_vieja, categoria_nueva in MAPEO_CATEGORIAS.items():
        items = Inventario.query.filter_by(categoria=categoria_vieja).all()
        
        if items:
            print(f"\n📝 {categoria_vieja} → {categoria_nueva}")
            print(f"   Items a actualizar: {len(items)}")
            
            for item in items:
                item.categoria = categoria_nueva
                actualizados += 1
            
            db.session.commit()
    
    print(f"\n✅ Total actualizado: {actualizados} items")
    
    # Mostrar resumen final
    print("\n" + "=" * 60)
    print("📊 CATEGORÍAS DESPUÉS DE LA NORMALIZACIÓN")
    print("=" * 60)
    
    from sqlalchemy import func
    categorias_usadas = db.session.query(
        Inventario.categoria, 
        func.count(Inventario.id).label('count')
    ).group_by(Inventario.categoria).order_by(func.count(Inventario.id).desc()).all()
    
    for cat, count in categorias_usadas:
        print(f"   - {cat}: {count} items")
    
    print("\n" + "=" * 60)
