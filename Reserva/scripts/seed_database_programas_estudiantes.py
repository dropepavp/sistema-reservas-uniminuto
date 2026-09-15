import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from database import ProgramaAcademico, Estudiante, Sede, Profesor
from data.programas_academicos_seed import PROGRAMAS_ACADEMICOS_SEED, ALIAS_PROGRAMAS
from sqlalchemy import text
import re

app = create_app('development')

def seed_data():
    with app.app_context():
        print("1. Creando tablas en la base de datos...")
        db.create_all()

        print("1.1. Verificando y agregando columnas nuevas a tablas existentes...")
        alter_statements = [
            "ALTER TABLE profesores ADD COLUMN IF NOT EXISTS programa_id INTEGER REFERENCES programas_academicos(id);",
            "ALTER TABLE reservas ADD COLUMN IF NOT EXISTS programa_id INTEGER REFERENCES programas_academicos(id);",
            "ALTER TABLE reservas ADD COLUMN IF NOT EXISTS programa VARCHAR(200);",
            "ALTER TABLE clases_salas_computo ADD COLUMN IF NOT EXISTS programa_id INTEGER REFERENCES programas_academicos(id);"
        ]
        for stmt in alter_statements:
            try:
                db.session.execute(text(stmt))
            except Exception as ex:
                print(f"   Nota al ejecutar alter: {ex}")
        db.session.commit()

        print("2. Poblando Sedes...")
        sedes_data = [
            'PERDOMO',
            'ENGATIVA SEDE PRINCIPAL'
        ]
        sedes_map = {}
        for s_nombre in sedes_data:
            s = Sede.query.filter_by(nombre=s_nombre).first()
            if not s:
                s = Sede(nombre=s_nombre)
                db.session.add(s)
                db.session.flush()
            sedes_map[s_nombre] = s.id
        db.session.commit()

        print("3. Poblando Programas Académicos...")
        programas_map = {} # codigo: id
        for p in PROGRAMAS_ACADEMICOS_SEED:
            prog = ProgramaAcademico.query.filter_by(codigo=p['codigo']).first()
            if not prog:
                prog = ProgramaAcademico(
                    codigo=p['codigo'],
                    nombre=p['nombre'],
                    nivel=p.get('nivel'),
                    sub_nivel=p.get('sub_nivel'),
                    periodo=p.get('periodo'),
                    activo=True
                )
                db.session.add(prog)
                db.session.flush()
            programas_map[prog.codigo] = prog.id
            # También mapear por nombre en mayúsculas
            programas_map[prog.nombre.upper()] = prog.id
        db.session.commit()

        print(f"   -> {len(PROGRAMAS_ACADEMICOS_SEED)} Programas Académicos verificados/creados.")

        # Vincular profesores existentes a programas_academicos si es posible
        print("4. Vinculando Profesores con Programas Académicos...")
        profesores = Profesor.query.all()
        vinculados_profes = 0
        for prof in profesores:
            if prof.programa and not prof.programa_id:
                prog_clean = prof.programa.strip().upper()
                # Buscar por código directo
                if prog_clean in programas_map:
                    prof.programa_id = programas_map[prog_clean]
                    vinculados_profes += 1
                else:
                    # Buscar coincidencia parcial
                    for p_seed in PROGRAMAS_ACADEMICOS_SEED:
                        if p_seed['nombre'] in prog_clean or prog_clean in p_seed['nombre']:
                            prof.programa_id = p_seed.get('id') or programas_map.get(p_seed['codigo'])
                            vinculados_profes += 1
                            break
        db.session.commit()
        print(f"   -> {vinculados_profes} Profesores vinculados a Programas Académicos.")

        print("5. Base de datos actualizada con éxito.")

if __name__ == '__main__':
    seed_data()
