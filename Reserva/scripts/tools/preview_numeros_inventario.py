"""
Script para previsualizar cómo quedarían los números de inventario actualizados.
NO hace cambios en la base de datos, solo muestra una vista previa.
"""
from database import db, Inventario
from app import app
import re

def preview_actualizacion():
    """Muestra una vista previa de cómo quedarían los números actualizados."""
    
    with app.app_context():
        # Obtener todos los items que NO son gestionados por cantidad
        items = Inventario.query.filter(
            db.or_(
                Inventario.es_por_cantidad == False,
                Inventario.es_por_cantidad.is_(None)
            )
        ).order_by(Inventario.item, Inventario.id).all()
        
        print(f"\n📦 Total de items a actualizar: {len(items)}")
        
        # Items gestionados por cantidad (NO se actualizarán)
        items_cantidad = Inventario.query.filter_by(es_por_cantidad=True).all()
        print(f"📦 Items por cantidad (NO se modificarán): {len(items_cantidad)}")
        
        if items_cantidad:
            print("\n🔒 Items que NO se modificarán (gestionados por cantidad):")
            for item in items_cantidad[:10]:  # Mostrar solo los primeros 10
                print(f"   - {item.numero_inventario}: {item.item} (Cantidad: {item.cantidad_total})")
            if len(items_cantidad) > 10:
                print(f"   ... y {len(items_cantidad) - 10} más")
        
        # Agrupar por las 3 primeras letras del item
        grupos = {}
        
        for item in items:
            nombre_limpio = re.sub(r'[^A-Za-z0-9]+', '', item.item.upper())
            prefijo = nombre_limpio[:3] if len(nombre_limpio) >= 3 else nombre_limpio.ljust(3, 'X')
            
            if prefijo not in grupos:
                grupos[prefijo] = []
            grupos[prefijo].append(item)
        
        print(f"\n📊 Grupos encontrados: {len(grupos)}")
        print("\n" + "=" * 80)
        print("VISTA PREVIA DE CAMBIOS")
        print("=" * 80)
        
        total_cambios = 0
        conflictos = 0
        
        # Mostrar vista previa de cada grupo
        for prefijo, items_grupo in sorted(grupos.items()):
            print(f"\n🔤 Grupo: {prefijo} ({len(items_grupo)} items)")
            print("-" * 80)
            
            for idx, item in enumerate(items_grupo, start=1):
                nuevo_numero = f"{prefijo}{idx:02d}"
                numero_anterior = item.numero_inventario
                
                # Verificar conflictos
                existe = Inventario.query.filter(
                    Inventario.numero_inventario == nuevo_numero,
                    Inventario.id != item.id
                ).first()
                
                if existe:
                    print(f"  ⚠️  {numero_anterior:20s} -> {nuevo_numero:10s} | {item.item:30s} [CONFLICTO]")
                    conflictos += 1
                else:
                    cambio = "✓" if numero_anterior != nuevo_numero else "="
                    print(f"  {cambio}  {numero_anterior:20s} -> {nuevo_numero:10s} | {item.item}")
                    if numero_anterior != nuevo_numero:
                        total_cambios += 1
        
        print("\n" + "=" * 80)
        print("RESUMEN")
        print("=" * 80)
        print(f"✅ Items que se actualizarán: {total_cambios}")
        print(f"⚠️  Conflictos detectados: {conflictos}")
        print(f"📦 Items sin cambios: {len(items) - total_cambios - conflictos}")
        print(f"🔒 Items por cantidad (no afectados): {len(items_cantidad)}")
        
        if conflictos > 0:
            print("\n⚠️  ADVERTENCIA: Hay conflictos que deben resolverse antes de aplicar cambios.")
        
        return total_cambios, conflictos

if __name__ == '__main__':
    print("=" * 80)
    print("👁️  VISTA PREVIA - ACTUALIZACIÓN DE NÚMEROS DE INVENTARIO")
    print("=" * 80)
    print("\nEste script SOLO muestra una vista previa, NO hace cambios.")
    print("\n" + "=" * 80)
    
    preview_actualizacion()
    
    print("\n" + "=" * 80)
    print("\n💡 Para aplicar los cambios, ejecuta: python actualizar_numeros_inventario.py")
