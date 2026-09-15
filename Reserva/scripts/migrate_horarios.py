import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from database import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Attempt to add columns one by one in case they already exist
    queries = [
        "ALTER TABLE horarios_colaboradores ADD COLUMN jornada VARCHAR(50);",
        "ALTER TABLE horarios_colaboradores ADD COLUMN piso_laboratorio VARCHAR(100);",
        "ALTER TABLE horarios_colaboradores ADD COLUMN recurso_movil VARCHAR(100);"
    ]
    
    for q in queries:
        try:
            db.session.execute(text(q))
            db.session.commit()
            print(f"Success: {q}")
        except Exception as e:
            db.session.rollback()
            print(f"Skipped (already exists or error): {e}")

    print("Migration finished.")
