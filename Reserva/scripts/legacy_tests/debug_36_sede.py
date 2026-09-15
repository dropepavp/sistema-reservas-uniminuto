
from app import app
from database import db, Inventario, Bodega

with app.app_context():
    items = Inventario.query.filter(Inventario.numero_inventario.ilike('%36%')).all()
    for i in items:
        sede_name = i.bodega.sede.nombre if i.bodega and i.bodega.sede else 'N/A'
        print(f"| {i.item:<20} | {i.numero_inventario:<10} | {i.estado:<15} | Sede: {sede_name}")
