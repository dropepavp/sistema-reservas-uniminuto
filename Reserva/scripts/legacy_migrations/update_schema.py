from app_improved import create_app
from database import db, init_db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # 1. Agregar columnas faltantes a tablas existentes (PostgreSQL) primero
    # Esto evita errores cuando SQLAlchemy intenta reflejar las tablas
    
    queries = [
        "ALTER TABLE inventario ADD COLUMN IF NOT EXISTS bodega_id INTEGER REFERENCES bodegas(id)",
        "ALTER TABLE reservas ADD COLUMN IF NOT EXISTS sede_id INTEGER REFERENCES sedes(id)",
        "ALTER TABLE prestamos_equipos ADD COLUMN IF NOT EXISTS sede_id INTEGER REFERENCES sedes(id)",
        "ALTER TABLE auxiliares ADD COLUMN IF NOT EXISTS sede_id INTEGER REFERENCES sedes(id)"
    ]
    
    for query in queries:
        try:
            db.session.execute(text(query))
            db.session.commit()
            print(f"✅ Ejecutado: {query}")
        except Exception as e:
            db.session.rollback()
            print(f"⚠️ Nota o Error: {e}")

    # 2. Crear las nuevas tablas (después de ajustar las existentes)
    db.create_all()
    print("✅ Tablas nuevas creadas (si no existían).")

    # 3. Poblar Sedes iniciales
    from database import Sede
    if not Sede.query.first():
        sedes = ['PERDOMO', 'ENGATIVA SEDE PRINCIPAL']
        for s in sedes:
            db.session.add(Sede(nombre=s))
        db.session.commit()
        print("✅ Sedes iniciales creadas.")
    else:
        print("ℹ️ Las sedes ya existen.")

    print("\n🚀 Actualización de base de datos completada.")
