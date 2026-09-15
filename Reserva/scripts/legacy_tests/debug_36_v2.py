
from app import app
from database import db, Inventario

with app.app_context():
    items = Inventario.query.filter(Inventario.numero_inventario.ilike('%36%')).all()
    print(f"Total found: {len(items)}")
    for i in items:
        sede = i.bodega.sede.nombre if i.bodega and i.bodega.sede else 'N/A'
        print(f"ITEM: {i.item}")
        print(f"NUM: {i.numero_inventario}")
        print(f"SEDE: {sede}")
        print("-" * 20)
