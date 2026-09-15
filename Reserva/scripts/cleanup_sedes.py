import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from database import Sede, Estudiante
from sqlalchemy import text

app = create_app('development')

def cleanup():
    with app.app_context():
        # Obtener ID de ENGATIVA SEDE PRINCIPAL
        sede_engativa = Sede.query.filter_by(nombre='ENGATIVA SEDE PRINCIPAL').first()
        if sede_engativa:
            # Reasignar estudiantes a ENGATIVA SEDE PRINCIPAL
            db.session.execute(text(f"UPDATE estudiantes SET sede_id = {sede_engativa.id} WHERE sede_id NOT IN (SELECT id FROM sedes WHERE nombre IN ('PERDOMO', 'ENGATIVA SEDE PRINCIPAL'))"))
            db.session.commit()
            print("Estudiantes reasignados a ENGATIVA SEDE PRINCIPAL.")
        
        # Eliminar sedes que no sean PERDOMO ni ENGATIVA SEDE PRINCIPAL
        db.session.execute(text("DELETE FROM sedes WHERE nombre NOT IN ('PERDOMO', 'ENGATIVA SEDE PRINCIPAL')"))
        db.session.commit()
        print("Sedes adicionales eliminadas.")

        sedes_restantes = Sede.query.all()
        print("Sedes actuales en la base de datos:")
        for s in sedes_restantes:
            print(f" - ID: {s.id}, Nombre: '{s.nombre}'")

if __name__ == '__main__':
    cleanup()
