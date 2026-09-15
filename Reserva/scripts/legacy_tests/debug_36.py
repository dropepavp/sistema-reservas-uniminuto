
from app import app
from database import db, Inventario

with app.app_context():
    items = Inventario.query.filter(Inventario.numero_inventario.ilike('%36%')).all()
    for i in items:
        print(f"| {i.item:<20} | {i.numero_inventario:<10} | {i.estado:<15} |")
