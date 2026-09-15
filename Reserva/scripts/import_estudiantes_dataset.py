import os
import sys
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from database import Estudiante, ProgramaAcademico, Sede
from data.programas_academicos_seed import ALIAS_PROGRAMAS

app = create_app('development')

def import_students():
    with app.app_context():
        print("Importando lote de estudiantes...")

        # Mapear programas académicos {codigo: id}
        programas_map = {p.codigo.upper(): p.id for p in ProgramaAcademico.query.all()}
        # Mapear sedes {nombre: id}
        sedes_map = {s.nombre.upper(): s.id for s in Sede.query.all()}

        # Cargar archivo de datos si existe o procesar lote
        data_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'estudiantes_raw.txt')
        if not os.path.exists(data_file):
            print(f"Archivo {data_file} no encontrado.")
            return

        with open(data_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        total = 0
        insertados = 0
        actualizados = 0

        for line in lines:
            line = line.strip()
            if not line or line.startswith('NOMBRES;') or line.startswith('NOMBRES\t'):
                continue

            parts = line.split(';')
            if len(parts) < 4:
                parts = line.split('\t')
            if len(parts) < 4:
                continue

            nombre_raw = re.sub(r'\s+', ' ', parts[0].strip()).upper()
            codigo_banner = parts[1].strip()
            sede_raw = parts[2].strip().upper()
            atributo_raw = parts[3].strip().upper()

            if not codigo_banner or not nombre_raw:
                continue

            total += 1

            # Normalizar atributo y encontrar programa_id
            atributo_clean = ALIAS_PROGRAMAS.get(atributo_raw, atributo_raw)
            programa_id = programas_map.get(atributo_clean)
            if not programa_id and atributo_clean != 'SIN ATRIBUTO':
                # Intentar buscar por alias o aproximación
                for cod, pid in programas_map.items():
                    if cod.startswith(atributo_clean) or atributo_clean.startswith(cod):
                        programa_id = pid
                        break

            # Sede ID (Sedes operativas en el sistema)
            sede_id = None
            if 'ENGATIVA' in sede_raw or 'BOLIVAR' in sede_raw:
                sede_id = sedes_map.get('ENGATIVA SEDE PRINCIPAL')
            elif 'PERDOMO' in sede_raw:
                sede_id = sedes_map.get('PERDOMO')

            # Buscar si ya existe por codigo_banner
            est = Estudiante.query.filter_by(codigo_banner=codigo_banner).first()
            if not est:
                est = Estudiante(
                    codigo_banner=codigo_banner,
                    documento=codigo_banner,
                    tipo_documento='Banner',
                    nombre_completo=nombre_raw,
                    descripcion_sede=sede_raw,
                    sede_id=sede_id,
                    atributo_programa=atributo_raw,
                    programa_id=programa_id,
                    activo=True
                )
                db.session.add(est)
                insertados += 1
            else:
                est.nombre_completo = nombre_raw
                est.descripcion_sede = sede_raw
                est.sede_id = sede_id
                est.atributo_programa = atributo_raw
                if programa_id:
                    est.programa_id = programa_id
                actualizados += 1

            if total % 100 == 0:
                db.session.commit()
                print(f"Procesados {total} estudiantes...")

        db.session.commit()
        print(f"✅ Proceso completado: Total={total}, Nuevos={insertados}, Actualizados={actualizados}")

if __name__ == '__main__':
    import_students()
