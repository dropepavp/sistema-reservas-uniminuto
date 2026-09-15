from app import app
from database import db, Inventario

with app.app_context():
    items = Inventario.query.limit(20).all()
    for eq in items:
        print(f"NumInv: {eq.numero_inventario}, ActivoFijo: {eq.activo_fijo}, Item: {eq.item}")
