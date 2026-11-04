#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para:
1. Crear la tabla `programacion_banner` en PostgreSQL (BD activa del proyecto).
2. Crear la base de datos SQLite `instance/programacion_banner.db` con el modelo completo.
3. Crear la base de datos SQLite `instance/programacion_faltante.db` con lo que NO estaba en las bases de datos.
4. Generar el archivo Excel `data/Programacion_Academica_Validacion_Completa.xlsx`.
"""
import os
import sys
import csv
import io
import re
from datetime import datetime, date
import sqlite3

# Configurar path al proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from check_csv_data import CSV_DATA
from app import create_app
from database import db, ProgramacionBanner, Profesor, Sede, Recurso, Reserva

def limpiar_texto(texto):
    if not texto:
        return ""
    t = texto.strip()
    # Corrección de codificación común en Banner/Génesis
    reemplazos = [
        ('Observacin', 'Observación'),
        ('Educacin', 'Educación'),
        ('Investigacin', 'Investigación'),
        ('Fsico', 'Físico'),
        ('Msica', 'Música'),
        ('Prctica', 'Práctica'),
        ('Pblicos', 'Públicos'),
        ('Qumicos', 'Químicos'),
        ('Tecnolgico', 'Tecnológico'),
        ('Epistemologa', 'Epistemología'),
        ('Mtodos', 'Métodos'),
        ('PATIO', 'PATIÑO'),
        ('Anlisis', 'Análisis'),
        ('Direccin', 'Dirección'),
        ('Auditora', 'Auditoría'),
        ('Administracin', 'Administración'),
        ('Estratgica', 'Estratégica'),
        ('mecnicos', 'mecánicos'),
        ('elctrico', 'eléctrico'),
        ('Gestin', 'Gestión'),
        ('Ergonoma', 'Ergonomía'),
        ('Vicerrectora', 'Vicerrectoría'),
        ('Acadmica', 'Académica'),
        ('Estadstica', 'Estadística'),
        ('Matemticas', 'Matemáticas'),
        ('teora', 'teoría'),
        ('contab', 'contable'),
        ('Fsica', 'Física'),
        ('Electrnica', 'Electrónica'),
        ('Pedag', 'Pedagógica'),
        ('Profundizacin', 'Profundización'),
        ('Mecnica', 'Mecánica'),
        ('Planeacin', 'Planeación'),
        ('Organizacin', 'Organización'),
        ('Epidemiologa', 'Epidemiología'),
        ('Ingeniera', 'Ingeniería'),
        ('Indu', 'Industrial'),
        ('Pensamiento Econmico', 'Pensamiento Económico'),
        ('Econmico', 'Económico'),
        ('Lingistics', 'Linguistics'),
        ('Lgica', 'Lógica'),
        ('Programacin', 'Programación'),
        ('Introduccin', 'Introducción'),
        ('Ftbol', 'Fútbol'),
        ('Natacin', 'Natación'),
        ('Sociopol', 'Sociopolítica'),
        ('Poltica', 'Política'),
        ('Pblica', 'Pública'),
        ('Formulacin', 'Formulación'),
        ('Evaluac', 'Evaluación'),
        ('Diagnstico', 'Diagnóstico'),
        ('ORDOEZ', 'ORDÓÑEZ'),
        ('BOLAOS', 'BOLAÑOS'),
        ('PEA', 'PEÑA'),
        ('PIEROS', 'PIÑEROS'),
        ('Opcin', 'Opción'),
        ('Pedaggicos', 'Pedagógicos'),
        ('Teoras', 'Teorías'),
        ('Diseo', 'Diseño'),
        ('Cognicin', 'Cognición'),
        ('Polticas', 'Políticas'),
        ('Pblicas', 'Públicas'),
        ('Clculo', 'Cálculo'),
        ('lgebra', 'Álgebra'),
        ('Economa', 'Economía'),
        ('Psicologa', 'Psicología')
    ]
    for orig, dest in reemplazos:
        t = t.replace(orig, dest)
    return t

def parse_fecha(f_str):
    if not f_str or not f_str.strip():
        return None
    try:
        return datetime.strptime(f_str.strip(), '%d/%m/%Y').date()
    except Exception:
        return None

def parse_float(val):
    if not val or not val.strip():
        return None
    try:
        return float(val.strip().replace(',', '.'))
    except Exception:
        return None

def parse_int(val):
    if not val or not val.strip():
        return None
    try:
        return int(val.strip())
    except Exception:
        return None

def obtener_dias_semana(row):
    dias = []
    if row.get('L') and row['L'].strip(): dias.append('Lunes')
    if row.get('M') and row['M'].strip(): dias.append('Martes')
    if row.get('I') and row['I'].strip(): dias.append('Miércoles')
    if row.get('J') and row['J'].strip(): dias.append('Jueves')
    if row.get('V') and row['V'].strip(): dias.append('Viernes')
    if row.get('S') and row['S'].strip(): dias.append('Sábado')
    return ", ".join(dias) if dias else "Virtual / Sin Día"

def main():
    app = create_app()
    with app.app_context():
        print("1. Creando tablas en PostgreSQL...")
        db.create_all()

        # Parsear filas de CSV
        reader = csv.DictReader(io.StringIO(CSV_DATA.strip()), delimiter=';')
        raw_rows = [r for r in reader if r.get('NRC') and r.get('NRC').strip()]
        print(f"Total registros en archivo CSV: {len(raw_rows)}")

        # Consultar lo que YA está en la BD para validación
        profesores_existentes = {p.cedula: p.nombre_completo for p in Profesor.query.all()}
        sedes_existentes = {s.nombre.upper(): s.id for s in Sede.query.all()}
        recursos_existentes = {r.nombre.upper(): r.id for r in Recurso.query.all()}
        reservas_nrcs = set(r.nrc.strip() for r in Reserva.query.filter(Reserva.nrc != None).all())

        print(f"Base de datos actual:")
        print(f"  - Profesores: {len(profesores_existentes)}")
        print(f"  - Sedes: {list(sedes_existentes.keys())}")
        print(f"  - Recursos / Salones: {len(recursos_existentes)}")
        print(f"  - Reservas con NRC: {len(reservas_nrcs)}")

        # Limpiar registros previos en programacion_banner si existieran para evitar duplicados
        num_borrados = ProgramacionBanner.query.delete()
        if num_borrados > 0:
            print(f"Limpiados {num_borrados} registros previos de programacion_banner.")
        db.session.commit()

        # Insertar registros en PostgreSQL
        objetos_banner = []
        faltantes_registros = []
        docentes_nuevos = {}
        salones_nuevos = set()
        sedes_nuevas = set()

        for r in raw_rows:
            nrc = r['NRC'].strip()
            periodo = r.get('PERIODO', '').strip()
            titulo = limpiar_texto(r.get('TITULO', ''))
            docente_nom = limpiar_texto(r.get('NOMBRE_DOCENTE', ''))
            salon = r.get('SALON', '').strip()
            edificio = r.get('EDIFICIO', '').strip()
            desc_sede = r.get('DESC_SEDE', '').strip()
            cedula_str = r.get('IDENTIFICACION', '').strip()
            cedula_int = int(cedula_str) if cedula_str.isdigit() else None
            
            es_lab = ('LS' in salon.upper()) or ('LAB' in salon.upper())
            dias = obtener_dias_semana(r)

            # Validar faltantes
            ya_estaba_en_reserva = nrc in reservas_nrcs
            if not ya_estaba_en_reserva:
                faltantes_registros.append(r)

            if cedula_int and cedula_int not in profesores_existentes:
                docentes_nuevos[cedula_int] = docente_nom

            if salon and salon.upper() not in recursos_existentes:
                salones_nuevos.add(salon)

            if desc_sede and desc_sede.upper() not in sedes_existentes:
                sedes_nuevas.add(desc_sede)

            obj = ProgramacionBanner(
                periodo=periodo,
                nrc=nrc,
                modo_calificar=r.get('MODO_CALIFICAR', '').strip() or None,
                secuencia=r.get('SECUENCIA', '').strip() or None,
                lista_cruzada=r.get('LISTA_CRUZADA', '').strip() or None,
                alfa=r.get('ALFA', '').strip() or None,
                num=r.get('NUM', '').strip() or None,
                estado_nrc=r.get('ESTADO_NRC', '').strip() or None,
                titulo=titulo,
                horas_minimas=parse_float(r.get('HORAS_MINIMAS')),
                horas_maximas=parse_float(r.get('HORAS_MAXIMAS')),
                conector=r.get('CONECTOR', '').strip() or None,
                horas_creditos_sede=parse_float(r.get('HORAS_CREDITOS_SEDE')),
                intensidad_horaria=parse_float(r.get('INTENSIDAD_HORARIA')),
                rectoria=r.get('RECTORIA', '').strip() or None,
                desc_rectoria=r.get('DESC_RECTORIA', '').strip() or None,
                sede=r.get('SEDE', '').strip() or None,
                desc_sede=desc_sede or None,
                facultad_responsable=limpiar_texto(r.get('FACULTAD_RESPONSABLE')),
                departamento_responsable=limpiar_texto(r.get('DEPARTAMENTO_RESPONSABLE')),
                cupo=parse_int(r.get('CUPO')),
                inscritos=parse_int(r.get('INSCRITOS')),
                saldo=parse_int(r.get('SALDO')),
                id_docente=r.get('ID_DOCENTE', '').strip() or None,
                identificacion=cedula_str or None,
                nombre_docente=docente_nom or None,
                parte_periodo=r.get('PARTE_PERIODO', '').strip() or None,
                edificio=edificio or None,
                salon=salon or None,
                fecha_inicial_1=parse_fecha(r.get('FECHA_INICIAL_1')),
                fecha_final_1=parse_fecha(r.get('FECHA_FINAL_1')),
                hi=r.get('HI', '').strip() or None,
                hf=r.get('HF', '').strip() or None,
                l=r.get('L', '').strip() or None,
                m=r.get('M', '').strip() or None,
                i=r.get('I', '').strip() or None,
                j=r.get('J', '').strip() or None,
                v=r.get('V', '').strip() or None,
                s=r.get('S', '').strip() or None,
                es_sala_computo=es_lab,
                dias_semana=dias
            )
            objetos_banner.append(obj)

        db.session.add_all(objetos_banner)
        db.session.commit()
        print(f"Insertados exitosamente {len(objetos_banner)} registros en `programacion_banner` (PostgreSQL).")

        # -----------------------------------------------------------------
        # 2. CREAR BASE SQLITE COMPLETA: instance/programacion_banner.db
        # -----------------------------------------------------------------
        os.makedirs('instance', exist_ok=True)
        sqlite_completa_path = os.path.join('instance', 'programacion_banner.db')
        if os.path.exists(sqlite_completa_path):
            os.remove(sqlite_completa_path)

        conn_sqlite = sqlite3.connect(sqlite_completa_path)
        cur_sqlite = conn_sqlite.cursor()

        cur_sqlite.execute("""
        CREATE TABLE programacion_banner (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo TEXT,
            nrc TEXT,
            modo_calificar TEXT,
            secuencia TEXT,
            lista_cruzada TEXT,
            alfa TEXT,
            num TEXT,
            estado_nrc TEXT,
            titulo TEXT,
            horas_minimas REAL,
            horas_maximas REAL,
            conector TEXT,
            horas_creditos_sede REAL,
            intensidad_horaria REAL,
            rectoria TEXT,
            desc_rectoria TEXT,
            sede TEXT,
            desc_sede TEXT,
            facultad_responsable TEXT,
            departamento_responsable TEXT,
            cupo INTEGER,
            inscritos INTEGER,
            saldo INTEGER,
            id_docente TEXT,
            identificacion TEXT,
            nombre_docente TEXT,
            parte_periodo TEXT,
            edificio TEXT,
            salon TEXT,
            fecha_inicial_1 TEXT,
            fecha_final_1 TEXT,
            hi TEXT,
            hf TEXT,
            l TEXT,
            m TEXT,
            i TEXT,
            j TEXT,
            v TEXT,
            s TEXT,
            es_sala_computo INTEGER,
            dias_semana TEXT,
            created_at TEXT
        );
        """)

        for o in objetos_banner:
            cur_sqlite.execute("""
            INSERT INTO programacion_banner (
                periodo, nrc, modo_calificar, secuencia, lista_cruzada, alfa, num, estado_nrc, titulo,
                horas_minimas, horas_maximas, conector, horas_creditos_sede, intensidad_horaria,
                rectoria, desc_rectoria, sede, desc_sede, facultad_responsable, departamento_responsable,
                cupo, inscritos, saldo, id_docente, identificacion, nombre_docente, parte_periodo,
                edificio, salon, fecha_inicial_1, fecha_final_1, hi, hf, l, m, i, j, v, s,
                es_sala_computo, dias_semana, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                o.periodo, o.nrc, o.modo_calificar, o.secuencia, o.lista_cruzada, o.alfa, o.num, o.estado_nrc, o.titulo,
                o.horas_minimas, o.horas_maximas, o.conector, o.horas_creditos_sede, o.intensidad_horaria,
                o.rectoria, o.desc_rectoria, o.sede, o.desc_sede, o.facultad_responsable, o.departamento_responsable,
                o.cupo, o.inscritos, o.saldo, o.id_docente, o.identificacion, o.nombre_docente, o.parte_periodo,
                o.edificio, o.salon, o.fecha_inicial_1.isoformat() if o.fecha_inicial_1 else None,
                o.fecha_final_1.isoformat() if o.fecha_final_1 else None, o.hi, o.hf, o.l, o.m, o.i, o.j, o.v, o.s,
                1 if o.es_sala_computo else 0, o.dias_semana, datetime.now().isoformat()
            ))

        conn_sqlite.commit()
        conn_sqlite.close()
        print(f"Creada base de datos SQLite completa: {sqlite_completa_path}")

        # -----------------------------------------------------------------
        # 3. CREAR BASE SQLITE CON LO QUE NO ESTABA: instance/programacion_faltante.db
        # -----------------------------------------------------------------
        sqlite_faltante_path = os.path.join('instance', 'programacion_faltante.db')
        if os.path.exists(sqlite_faltante_path):
            os.remove(sqlite_faltante_path)

        conn_faltante = sqlite3.connect(sqlite_faltante_path)
        cur_faltante = conn_faltante.cursor()

        # Tabla con los registros de horarios que NO estaban en reservas
        cur_faltante.execute("""
        CREATE TABLE horarios_no_registrados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo TEXT,
            nrc TEXT,
            modo_calificar TEXT,
            secuencia TEXT,
            lista_cruzada TEXT,
            alfa TEXT,
            num TEXT,
            estado_nrc TEXT,
            titulo TEXT,
            horas_minimas REAL,
            horas_maximas REAL,
            conector TEXT,
            horas_creditos_sede REAL,
            intensidad_horaria REAL,
            rectoria TEXT,
            desc_rectoria TEXT,
            sede TEXT,
            desc_sede TEXT,
            facultad_responsable TEXT,
            departamento_responsable TEXT,
            cupo INTEGER,
            inscritos INTEGER,
            saldo INTEGER,
            id_docente TEXT,
            identificacion TEXT,
            nombre_docente TEXT,
            parte_periodo TEXT,
            edificio TEXT,
            salon TEXT,
            fecha_inicial_1 TEXT,
            fecha_final_1 TEXT,
            hi TEXT,
            hf TEXT,
            l TEXT,
            m TEXT,
            i TEXT,
            j TEXT,
            v TEXT,
            s TEXT,
            es_sala_computo INTEGER,
            dias_semana TEXT
        );
        """)

        for r in faltantes_registros:
            f_ini = parse_fecha(r.get('FECHA_INICIAL_1'))
            f_fin = parse_fecha(r.get('FECHA_FINAL_1'))
            salon_val = r.get('SALON', '').strip()
            es_lab_val = 1 if (('LS' in salon_val.upper()) or ('LAB' in salon_val.upper())) else 0
            cur_faltante.execute("""
            INSERT INTO horarios_no_registrados (
                periodo, nrc, modo_calificar, secuencia, lista_cruzada, alfa, num, estado_nrc, titulo,
                horas_minimas, horas_maximas, conector, horas_creditos_sede, intensidad_horaria,
                rectoria, desc_rectoria, sede, desc_sede, facultad_responsable, departamento_responsable,
                cupo, inscritos, saldo, id_docente, identificacion, nombre_docente, parte_periodo,
                edificio, salon, fecha_inicial_1, fecha_final_1, hi, hf, l, m, i, j, v, s,
                es_sala_computo, dias_semana
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                r.get('PERIODO'), r.get('NRC'), r.get('MODO_CALIFICAR'), r.get('SECUENCIA'), r.get('LISTA_CRUZADA'),
                r.get('ALFA'), r.get('NUM'), r.get('ESTADO_NRC'), limpiar_texto(r.get('TITULO')),
                parse_float(r.get('HORAS_MINIMAS')), parse_float(r.get('HORAS_MAXIMAS')), r.get('CONECTOR'),
                parse_float(r.get('HORAS_CREDITOS_SEDE')), parse_float(r.get('INTENSIDAD_HORARIA')),
                r.get('RECTORIA'), r.get('DESC_RECTORIA'), r.get('SEDE'), r.get('DESC_SEDE'),
                limpiar_texto(r.get('FACULTAD_RESPONSABLE')), limpiar_texto(r.get('DEPARTAMENTO_RESPONSABLE')),
                parse_int(r.get('CUPO')), parse_int(r.get('INSCRITOS')), parse_int(r.get('SALDO')),
                r.get('ID_DOCENTE'), r.get('IDENTIFICACION'), limpiar_texto(r.get('NOMBRE_DOCENTE')),
                r.get('PARTE_PERIODO'), r.get('EDIFICIO'), salon_val,
                f_ini.isoformat() if f_ini else None, f_fin.isoformat() if f_fin else None,
                r.get('HI'), r.get('HF'), r.get('L'), r.get('M'), r.get('I'), r.get('J'), r.get('V'), r.get('S'),
                es_lab_val, obtener_dias_semana(r)
            ))

        # Tabla con los Docentes Nuevos
        cur_faltante.execute("""
        CREATE TABLE docentes_nuevos (
            cedula INTEGER PRIMARY KEY,
            nombre_completo TEXT
        );
        """)
        for ced, nom in sorted(docentes_nuevos.items()):
            cur_faltante.execute("INSERT INTO docentes_nuevos (cedula, nombre_completo) VALUES (?, ?);", (ced, nom))

        # Tabla con los Salones Nuevos
        cur_faltante.execute("""
        CREATE TABLE salones_nuevos (
            nombre_salon TEXT PRIMARY KEY,
            es_sala_computo INTEGER
        );
        """)
        for s_nom in sorted(list(salones_nuevos)):
            es_lab_val = 1 if (('LS' in s_nom.upper()) or ('LAB' in s_nom.upper())) else 0
            cur_faltante.execute("INSERT INTO salones_nuevos (nombre_salon, es_sala_computo) VALUES (?, ?);", (s_nom, es_lab_val))

        # Tabla con las Sedes Nuevas
        cur_faltante.execute("""
        CREATE TABLE sedes_nuevas (
            nombre_sede TEXT PRIMARY KEY
        );
        """)
        for sede_nom in sorted(list(sedes_nuevas)):
            cur_faltante.execute("INSERT INTO sedes_nuevas (nombre_sede) VALUES (?);", (sede_nom,))

        conn_faltante.commit()
        conn_faltante.close()
        print(f"Creada base de datos SQLite faltante: {sqlite_faltante_path}")

        # -----------------------------------------------------------------
        # 4. EXPORTAR EXCEL CONSOLIDADO DE VALIDACIÓN
        # -----------------------------------------------------------------
        import pandas as pd
        excel_path = os.path.join('data', 'Programacion_Academica_Validacion_Completa.xlsx')

        # DataFrame Malla Completa
        df_completo = pd.DataFrame([o.to_dict() for o in objetos_banner])

        # DataFrame Faltantes
        df_faltantes = pd.DataFrame([
            {
                'NRC': r.get('NRC'),
                'PERIODO': r.get('PERIODO'),
                'ASIGNATURA': limpiar_texto(r.get('TITULO')),
                'DOCENTE': limpiar_texto(r.get('NOMBRE_DOCENTE')),
                'CEDULA': r.get('IDENTIFICACION'),
                'SALON': r.get('SALON'),
                'EDIFICIO': r.get('EDIFICIO'),
                'SEDE': r.get('DESC_SEDE'),
                'HORA_INICIO': r.get('HI'),
                'HORA_FIN': r.get('HF'),
                'DIAS': obtener_dias_semana(r),
                'FECHA_INICIO': r.get('FECHA_INICIAL_1'),
                'FECHA_FIN': r.get('FECHA_FINAL_1'),
                'ES_SALA_COMPUTO': 'Sí' if ('LS' in (r.get('SALON') or '').upper()) else 'No'
            }
            for r in faltantes_registros
        ])

        # DataFrame Docentes Nuevos
        df_docentes = pd.DataFrame([
            {'CEDULA': ced, 'NOMBRE_DOCENTE': nom, 'ESTADO_EN_BD': 'NUEVO (Por Registrar)'}
            for ced, nom in sorted(docentes_nuevos.items())
        ])

        # DataFrame Salones Nuevos
        df_salones = pd.DataFrame([
            {
                'SALON': s_nom,
                'TIPO_ESPACIO': 'Laboratorio / Sala de Cómputo (LS)' if 'LS' in s_nom.upper() else ('Espacio Abierto/Deportivo' if 'CANCHA' in s_nom.upper() else ('Virtual/Sincrónico' if s_nom in ('SINCR', 'VIRTU', 'EXT') else 'Salón Teórico')),
                'ESTADO_EN_BD': 'NUEVO (Por Registrar)'
            }
            for s_nom in sorted(list(salones_nuevos))
        ])

        # Recopilar todos los docentes únicos del CSV
        docentes_csv_todos = {}
        for r in raw_rows:
            ced = r.get('IDENTIFICACION', '').strip()
            nom = limpiar_texto(r.get('NOMBRE_DOCENTE', ''))
            if ced and ced.isdigit():
                docentes_csv_todos[int(ced)] = nom

        docentes_en_bd_encontrados = {c: n for c, n in docentes_csv_todos.items() if c in profesores_existentes}

        # DataFrame Resumen
        df_resumen = pd.DataFrame([
            {'MÉTRICA': 'Total Registros en Archivo Banner', 'CANTIDAD': len(raw_rows)},
            {'MÉTRICA': 'Total NRCs Únicos en Archivo', 'CANTIDAD': len(set(r['NRC'].strip() for r in raw_rows))},
            {'MÉTRICA': 'NRCs que YA existían en tabla Reservas', 'CANTIDAD': len(reservas_nrcs.intersection(set(r['NRC'].strip() for r in raw_rows)))},
            {'MÉTRICA': 'NRCs NUEVOS (No existían en Reservas)', 'CANTIDAD': len(faltantes_registros)},
            {'MÉTRICA': 'Total Docentes Únicos en Archivo', 'CANTIDAD': len(docentes_csv_todos)},
            {'MÉTRICA': 'Docentes que YA existían en BD Profesores', 'CANTIDAD': len(docentes_en_bd_encontrados)},
            {'MÉTRICA': 'Docentes NUEVOS (No existían en BD Profesores)', 'CANTIDAD': len(docentes_nuevos)},
            {'MÉTRICA': 'Salones / Espacios Totales en Archivo', 'CANTIDAD': len(set(r.get('SALON', '').strip() for r in raw_rows if r.get('SALON')))},
            {'MÉTRICA': 'Salones que YA existían en Recursos', 'CANTIDAD': len(set(r.get('SALON', '').strip().upper() for r in raw_rows if r.get('SALON')).intersection(set(recursos_existentes.keys())))},
            {'MÉTRICA': 'Salones / Espacios NUEVOS', 'CANTIDAD': len(salones_nuevos)},
            {'MÉTRICA': 'Sedes Nuevas detectadas', 'CANTIDAD': len(sedes_nuevas)}
        ])

        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df_resumen.to_excel(writer, sheet_name='Resumen_Validacion', index=False)
            df_faltantes.to_excel(writer, sheet_name='Horarios_No_En_BD', index=False)
            df_docentes.to_excel(writer, sheet_name='Docentes_Nuevos', index=False)
            df_salones.to_excel(writer, sheet_name='Salones_Nuevos', index=False)
            df_completo.to_excel(writer, sheet_name='Malla_Completa_Banner', index=False)

        print(f"Archivo Excel generado con éxito: {excel_path}")
        print("\n=== PROCESO COMPLETADO EXITOSAMENTE ===")

if __name__ == '__main__':
    main()
