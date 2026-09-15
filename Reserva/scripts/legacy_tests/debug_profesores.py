from app_improved import create_app
from database import db, Profesor

app = create_app()
with app.app_context():
    count = Profesor.query.count()
    print(f"Total profesores: {count}")
    if count > 0:
        print("Muestra de profesores:")
        for p in Profesor.query.limit(5).all():
            print(f"- {p.cedula}: {p.nombre_completo}")
