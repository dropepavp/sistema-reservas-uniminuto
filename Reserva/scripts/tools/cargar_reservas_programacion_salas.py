#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para cargar la programación de salas de cómputo en la tabla de Reservas.
Incluye:
- Alta de salones 704LS1, 804LS3, 803LS2, 801LS4, 703LS5 en Recurso para Sede Perdomo.
- Alta o actualización de los 25 profesores implicados en la tabla Profesor.
- Inserción de las 97 reservas semanales en la tabla Reserva para la semana activa.
- Generación de la planilla Excel con la programación completa en data/.
"""
import os
import sys
from datetime import datetime, date, time, timedelta

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Asegurar path al proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pandas as pd
from app import create_app
from database import db, Sede, Ubicacion, Recurso, Profesor, Reserva, ProgramaAcademico

RAW_DATA = """SALON	DIA	JORNADA	HORA_INICIO	HORA_FIN	IDENTIFICACION	NOMBRE_DOCENTE	NRC	TITULO
704LS1	Lunes	Mañana	07:00	08:29	79716853	NARANJO PIÑEROS FERNANDO ANDRES	89315	Dibujo
804LS3	Lunes	Mañana	07:00	08:29	1018408191	LOPEZ URBINA JOHANNA PATRICIA	79331	Research In Education
803LS2	Lunes	Mañana	08:30	09:59	52494786	ULLOA BRAVO INGRID CAROLINA	95839	Intro a la Ciencia Datos e IA
804LS3	Lunes	Mañana	08:30	09:59	79571556	GONZALEZ BARRERA RUBEN DARIO	87947	Intro a la Ciencia Datos e IA
804LS3	Lunes	Tarde	13:45	15:14	79184798	ROMERO ROMERO HELMER JULIAN	89498	Sistemas Operativos
804LS3	Lunes	Tarde	15:15	16:44	79184798	ROMERO ROMERO HELMER JULIAN	90548	Sistemas Operativos
801LS4	Lunes	Tarde	15:15	16:45	79962064	RAMIREZ RIVERA EDILBERTO 	89497	Estructura de datos
704LS1	Lunes	Tarde	16:45	18:14	79962064	RAMIREZ RIVERA EDILBERTO 	90547	Estructura de datos
803LS2	Lunes	Tarde	16:45	18:14	80151598	ACEVEDO MENDOZA GIOVANNY ALEXANDER	90537	Bases de Datos
804LS3	Lunes	Tarde	16:45	18:14	52116201	MARTINEZ BEJARANO YAZMIN 	89493	Programación Orientada a Objet
703LS5	Lunes	Noche	18:15	19:44	79962064	RAMIREZ RIVERA EDILBERTO 	89497	Estructura de datos
704LS1	Lunes	Noche	18:15	19:44	79184798	ROMERO ROMERO HELMER JULIAN	89768	Introducción a la Ingeniería
801LS4	Lunes	Noche	18:15	19:44	80235883	RODRIGUEZ FORERO MARTIN EMILIO	90532	Bases de Datos
803LS2	Lunes	Noche	18:15	19:44	39679626	MEDINA LINARES MARIBEL 	89516	Estructura de datos
804LS3	Lunes	Noche	18:15	19:44	79990854	CAÑON MOZO EDWIN PARMENIO	85948	Programación Web
703LS5	Lunes	Noche	20:30	21:59	79609497	MARTINEZ SANTA RICARDO 	89517	Sistemas Operativos
704LS1	Lunes	Noche	20:30	21:59	79606781	CUELLAR GAITAN RAUL ALBEIRO	77446	Programación Básica
801LS4	Lunes	Noche	20:30	21:59	79962064	RAMIREZ RIVERA EDILBERTO 	89483	Sistemas Distribuidos
803LS2	Lunes	Noche	20:30	21:59	79990854	CAÑON MOZO EDWIN PARMENIO	85947	Programación Web
804LS3	Lunes	Noche	20:30	21:59	39679626	MEDINA LINARES MARIBEL 	89520	Estructura de datos
804LS3	Martes	Mañana	07:00	08:29	1018408191	LOPEZ URBINA JOHANNA PATRICIA	79332	Research In Education
704LS1	Martes	Mañana	08:30	09:59	52110008	MUÑOZ SANCHEZ ALEJANDRA DEL PILAR	95840	Soluciones de Ingeniería
803LS2	Martes	Mañana	09:15	10:44	1030699910	PAEZ BERNAL DANIEL SANTIAGO	89295	Matemática Financiera
804LS3	Martes	Mañana	10:00	11:29	52110008	MUÑOZ SANCHEZ ALEJANDRA DEL PILAR	87957	Soluciones de Ingeniería
803LS2	Martes	Mañana	10:45	13:44	80015183	GARCIA GARCIA JOSE ALEXANDER	90578	Fundamentos de Investigación
704LS1	Martes	Tarde	13:45	15:14	79184798	ROMERO ROMERO HELMER JULIAN	90548	Sistemas Operativos
804LS3	Martes	Tarde	13:45	15:14	52116201	MARTINEZ BEJARANO YAZMIN 	89489	Programación Orientada a Objet
704LS1	Martes	Tarde	15:15	16:44	79184798	ROMERO ROMERO HELMER JULIAN	90538	Redes de Computadores
803LS2	Martes	Tarde	15:15	16:44	52116201	MARTINEZ BEJARANO YAZMIN 	89493	Programación Orientada a Objet
703LS5	Martes	Noche	18:15	19:44	86063771	LADINO TORRES HECTOR ANDRES	80979	Funda Estructuras de Datos
704LS1	Martes	Noche	18:15	19:44	79609497	MARTINEZ SANTA RICARDO 	90531	Redes de Computadores
801LS4	Martes	Noche	18:15	19:44	52116201	MARTINEZ BEJARANO YAZMIN 	90549	Programación Orientada a Objet
803LS2	Martes	Noche	18:15	19:44	80235883	RODRIGUEZ FORERO MARTIN EMILIO	85952	Ingeniería de Software
804LS3	Martes	Noche	18:15	19:44	79606781	CUELLAR GAITAN RAUL ALBEIRO	77447	Programación Básica
703LS5	Martes	Noche	20:30	21:59	79990854	CAÑON MOZO EDWIN PARMENIO	89522	Sistemas Transaccionales
704LS1	Martes	Noche	20:30	21:59	79962064	RAMIREZ RIVERA EDILBERTO 	89473	Sistemas Distribuidos
801LS4	Martes	Noche	20:30	21:59	79738414	MONTENEGRO PEREZ CARLOS MIGUEL	89317	Dibujo
803LS2	Martes	Noche	20:30	21:59	80235883	RODRIGUEZ FORERO MARTIN EMILIO	85951	Ingeniería de Software
804LS3	Martes	Noche	20:30	21:59	80151598	ACEVEDO MENDOZA GIOVANNY ALEXANDER	80865	Bases de Datos
804LS3	Miércoles	Mañana	08:30	10:44	79571556	GONZALEZ BARRERA RUBEN DARIO	89464	Programación Orientada a Objet
704LS1	Miércoles	Tarde	15:15	16:44	52116201	MARTINEZ BEJARANO YAZMIN 	89489	Programación Orientada a Objet
803LS2	Miércoles	Tarde	15:15	16:44	79885072	CARRILLO WALTEROS JOHN FREDY	75299	Programación Básica
804LS3	Miércoles	Tarde	15:15	16:44	79184798	ROMERO ROMERO HELMER JULIAN	89498	Sistemas Operativos
803LS2	Miércoles	Tarde	16:45	18:14	52116201	MARTINEZ BEJARANO YAZMIN 	90550	Programación Orientada a Objet
804LS3	Miércoles	Tarde	16:45	18:14	79885072	CARRILLO WALTEROS JOHN FREDY	82336	Programación Básica
703LS5	Miércoles	Noche	18:15	19:44	52116201	MARTINEZ BEJARANO YAZMIN 	90472	Introducción a la Ingeniería
704LS1	Miércoles	Noche	18:15	19:44	39679626	MEDINA LINARES MARIBEL 	89516	Estructura de datos
801LS4	Miércoles	Noche	18:15	19:44	80235883	RODRIGUEZ FORERO MARTIN EMILIO	90532	Bases de Datos
803LS2	Miércoles	Noche	18:15	19:44	79609497	MARTINEZ SANTA RICARDO 	89521	Sistemas Operativos
804LS3	Miércoles	Noche	18:15	19:44	52857770	HERNANDEZ LOPEZ CAROLINA 	85953	Interconectividad
703LS5	Miércoles	Noche	20:30	21:59	80904714	ORTEGA ACUÑA OSCAR JAMIR	89479	Desarrollo Basado en Plataform
704LS1	Miércoles	Noche	20:30	21:59	79606781	CUELLAR GAITAN RAUL ALBEIRO	89506	Programación Orientada a Objet
801LS4	Miércoles	Noche	20:30	21:59	86063771	LADINO TORRES HECTOR ANDRES	89343	Programación Orientada a Objet
803LS2	Miércoles	Noche	20:30	21:59	39679626	MEDINA LINARES MARIBEL 	89520	Estructura de datos
804LS3	Miércoles	Noche	20:30	21:59	79609497	MARTINEZ SANTA RICARDO 	89517	Sistemas Operativos
804LS3	Jueves	Mañana	07:45	09:59	79860376	SANTANA CARDENAS JOSE MIGUEL	89463	Estructura de datos
803LS2	Jueves	Mañana	10:00	12:14	86063771	LADINO TORRES HECTOR ANDRES	95838	Algoritmia y programación
804LS3	Jueves	Mañana	10:00	12:14	79860376	SANTANA CARDENAS JOSE MIGUEL	87960	Algoritmia y programación
704LS1	Jueves	Tarde	13:45	15:14	79962064	RAMIREZ RIVERA EDILBERTO 	90547	Estructura de datos
803LS2	Jueves	Tarde	13:45	15:14	79184798	ROMERO ROMERO HELMER JULIAN	90538	Redes de Computadores
803LS2	Jueves	Tarde	15:15	16:44	80151598	ACEVEDO MENDOZA GIOVANNY ALEXANDER	90537	Bases de Datos
804LS3	Jueves	Tarde	15:15	16:44	80255753	DIAZ ZAMUDIO JASSON 	89762	Introducción a la Ingeniería
804LS3	Jueves	Tarde	16:45	18:14	80151598	ACEVEDO MENDOZA GIOVANNY ALEXANDER	89765	Introducción a la Ingeniería
703LS5	Jueves	Noche	18:15	19:44	79962064	RAMIREZ RIVERA EDILBERTO 	89473	Sistemas Distribuidos
704LS1	Jueves	Noche	18:15	19:44	80904714	ORTEGA ACUÑA OSCAR JAMIR	89481	Diseño de Algoritmos
801LS4	Jueves	Noche	18:15	19:44	52116201	MARTINEZ BEJARANO YAZMIN 	90549	Programación Orientada a Objet
803LS2	Jueves	Noche	18:15	19:44	52857770	HERNANDEZ LOPEZ CAROLINA 	85954	Interconectividad
804LS3	Jueves	Noche	18:15	19:44	79606781	CUELLAR GAITAN RAUL ALBEIRO	89501	Programación Orientada a Objet
703LS5	Jueves	Noche	20:30	21:59	79962064	RAMIREZ RIVERA EDILBERTO 	89483	Sistemas Distribuidos
704LS1	Jueves	Noche	20:30	21:59	52857770	HERNANDEZ LOPEZ CAROLINA 	85953	Interconectividad
803LS2	Jueves	Noche	20:30	21:59	1031127610	CARDENAS JIMENEZ YESICA PAOLA	80989	Fundamentos de Programacio Web
804LS3	Jueves	Noche	20:30	21:59	80904714	ORTEGA ACUÑA OSCAR JAMIR	89471	Diseño de Algoritmos
704LS1	Viernes	Mañana	07:00	08:29	79716853	NARANJO PIÑEROS FERNANDO ANDRES	89315	Dibujo
804LS3	Viernes	Mañana	08:30	10:44	52494786	ULLOA BRAVO INGRID CAROLINA	89466	Bases de Datos
803LS2	Viernes	Mañana	09:15	10:44	1030699910	PAEZ BERNAL DANIEL SANTIAGO	89295	Matemática Financiera
804LS3	Viernes	Tarde	13:45	15:14	52116201	MARTINEZ BEJARANO YAZMIN 	90550	Programación Orientada a Objet
804LS3	Viernes	Tarde	15:15	16:44	79885072	CARRILLO WALTEROS JOHN FREDY	75299	Programación Básica
804LS3	Viernes	Tarde	16:45	18:14	79885072	CARRILLO WALTEROS JOHN FREDY	82336	Programación Básica
703LS5	Viernes	Noche	18:15	19:44	80904714	ORTEGA ACUÑA OSCAR JAMIR	89479	Desarrollo Basado en Plataform
704LS1	Viernes	Noche	18:15	19:44	79990854	CAÑON MOZO EDWIN PARMENIO	89523	Sistemas Transaccionales
801LS4	Viernes	Noche	18:15	19:44	86063771	LADINO TORRES HECTOR ANDRES	89343	Programación Orientada a Objet
803LS2	Viernes	Noche	18:15	19:44	52857770	HERNANDEZ LOPEZ CAROLINA 	80862	Redes de Computadores
804LS3	Viernes	Noche	18:15	19:44	80151598	ACEVEDO MENDOZA GIOVANNY ALEXANDER	80866	Bases de Datos
703LS5	Viernes	Noche	20:30	21:59	80235883	RODRIGUEZ FORERO MARTIN EMILIO	85951	Ingeniería de Software
704LS1	Viernes	Noche	20:30	21:59	79990854	CAÑON MOZO EDWIN PARMENIO	89522	Sistemas Transaccionales
801LS4	Viernes	Noche	20:30	21:59	80904714	ORTEGA ACUÑA OSCAR JAMIR	89468	Desarrollo Basado en Plataform
803LS2	Viernes	Noche	20:30	21:59	80151598	ACEVEDO MENDOZA GIOVANNY ALEXANDER	80865	Bases de Datos
804LS3	Viernes	Noche	20:30	21:59	52857770	HERNANDEZ LOPEZ CAROLINA 	80864	Redes de Computadores
704LS1	Sábado	Mañana	07:00	08:29	79609497	MARTINEZ SANTA RICARDO 	90541	Sistemas Operativos
803LS2	Sábado	Mañana	07:00	08:29	80904714	ORTEGA ACUÑA OSCAR JAMIR	89471	Diseño de Algoritmos
804LS3	Sábado	Mañana	07:00	08:29	79990854	CAÑON MOZO EDWIN PARMENIO	85948	Programación Web
704LS1	Sábado	Mañana	08:30	09:59	79962064	RAMIREZ RIVERA EDILBERTO 	89476	Arquitectura de Datos
803LS2	Sábado	Mañana	08:30	09:59	91490655	GUERRA VARGAS OSCAR ENRIQUE	80990	Bases de Datos
804LS3	Sábado	Mañana	08:30	09:59	79990854	CAÑON MOZO EDWIN PARMENIO	85947	Programación Web
704LS1	Sábado	Mañana	10:00	11:29	80904714	ORTEGA ACUÑA OSCAR JAMIR	89481	Diseño de Algoritmos
803LS2	Sábado	Mañana	10:00	11:29	1031127610	CARDENAS JIMENEZ YESICA PAOLA	80989	Fundamentos de Programacio Web
803LS2	Sábado	Mañana	11:30	12:59	79962064	RAMIREZ RIVERA EDILBERTO 	89485	Arquitectura de Datos"""

DIAS_SEMANA_OFFSET = {
    'lunes': 0,
    'martes': 1,
    'miércoles': 2,
    'miercoles': 2,
    'jueves': 3,
    'viernes': 4,
    'sábado': 5,
    'sabado': 5,
}

def ejecutar_carga():
    app = create_app()
    with app.app_context():
        print("🚀 Iniciando carga de programación de salas en Reservas...")

        # 1. Obtener Sede Perdomo
        sede_perdomo = Sede.query.filter(Sede.nombre.ilike('%PERDOMO%')).first()
        if not sede_perdomo:
            sede_perdomo = Sede(nombre="PERDOMO")
            db.session.add(sede_perdomo)
            db.session.flush()
        print(f"📍 Sede Perdomo ID: {sede_perdomo.id}")

        # Ubicación para Perdomo
        ubicacion_perdomo = Ubicacion.query.filter_by(sede_id=sede_perdomo.id).first()
        if not ubicacion_perdomo:
            ubicacion_perdomo = Ubicacion(
                nombre="Salas de Cómputo Perdomo",
                sede_id=sede_perdomo.id,
                tipo="Salón"
            )
            db.session.add(ubicacion_perdomo)
            db.session.flush()

        # 2. Registrar Recursos de Salones en Sede Perdomo
        salones_lista = ['704LS1', '804LS3', '803LS2', '801LS4', '703LS5']
        recursos_map = {}
        for s_nom in salones_lista:
            rec = Recurso.query.filter_by(nombre=s_nom).first()
            if not rec:
                rec = Recurso(
                    nombre=s_nom,
                    tipo='Salón',
                    ubicacion_id=ubicacion_perdomo.id,
                    activo=True
                )
                db.session.add(rec)
                db.session.flush()
                print(f"  ✨ Salón registrado como Recurso: {s_nom}")
            recursos_map[s_nom] = rec

        # También asegurar que LS1, LS2, LS3, LS4, LS5 existan
        for ls_base in ['LS1', 'LS2', 'LS3', 'LS4', 'LS5']:
            rec_base = Recurso.query.filter_by(nombre=ls_base).first()
            if not rec_base:
                rec_base = Recurso(
                    nombre=ls_base,
                    tipo='Salón',
                    ubicacion_id=ubicacion_perdomo.id,
                    activo=True
                )
                db.session.add(rec_base)
                db.session.flush()

        # 3. Parsear líneas del horario
        lineas = [l.strip().split('\t') for l in RAW_DATA.strip().split('\n')[1:] if l.strip()]
        print(f"📋 Registros a procesar: {len(lineas)}")

        # Fecha base para la semana activa (Semana del lunes 26 de octubre de 2026)
        hoy = date.today()
        lunes_activo = hoy - timedelta(days=hoy.weekday())
        print(f"📅 Semana base para reservas: Lunes {lunes_activo} a Sábado {lunes_activo + timedelta(days=5)}")

        # 4. Profesores y Reservas
        profesores_creados = 0
        reservas_creadas = 0
        reservas_actualizadas = 0

        # Lista para generar Excel
        excel_rows = []

        for r in lineas:
            salon = r[0].strip()
            dia_str = r[1].strip()
            jornada_str = r[2].strip().upper()
            h_ini_str = r[3].strip()
            h_fin_str = r[4].strip()
            cedula = int(r[5].strip())
            docente_nom = r[6].strip()
            nrc = r[7].strip()
            titulo = r[8].strip()

            # Asegurar Docente
            prof = Profesor.query.get(cedula)
            if not prof:
                prof = Profesor(
                    cedula=cedula,
                    nombre_completo=docente_nom,
                    correo=f"{docente_nom.lower().replace(' ', '.')[:18]}@uniminuto.edu.co",
                    programa="Ingeniería de Sistemas",
                    telefono="3000000000"
                )
                db.session.add(prof)
                db.session.flush()
                profesores_creados += 1

            # Calcular fecha exacta del día
            offset = DIAS_SEMANA_OFFSET.get(dia_str.lower(), 0)
            fecha_reserva = lunes_activo + timedelta(days=offset)

            # Horas
            h_ini = datetime.strptime(h_ini_str, '%H:%M').time()
            h_fin = datetime.strptime(h_fin_str, '%H:%M').time()

            # Recurso ID
            rec_obj = recursos_map.get(salon)
            rec_id = rec_obj.id if rec_obj else None

            # Verificar si ya existe exactamente esta reserva para evitar duplicar
            res_existente = Reserva.query.filter_by(
                cedula_profesor=cedula,
                recurso_nombre=salon,
                fecha=fecha_reserva,
                hora_inicio=h_ini
            ).first()

            if res_existente:
                res_existente.hora_fin = h_fin
                res_existente.nrc = nrc
                res_existente.observaciones = titulo
                res_existente.jornada = jornada_str
                res_existente.estado = 'Activa'
                reservas_actualizadas += 1
            else:
                nueva_res = Reserva(
                    cedula_profesor=cedula,
                    nombre_profesor=docente_nom,
                    sede_id=sede_perdomo.id,
                    nrc=nrc,
                    recurso_id=rec_id,
                    recurso_tipo='Salón',
                    recurso_nombre=salon,
                    fecha=fecha_reserva,
                    jornada=jornada_str,
                    hora_inicio=h_ini,
                    hora_fin=h_fin,
                    tipo_reserva='Clase',
                    estado='Activa',
                    observaciones=titulo
                )
                db.session.add(nueva_res)
                reservas_creadas += 1

            # Guardar para Excel
            excel_rows.append({
                'cedula_profesor': cedula,
                'nombre_profesor': docente_nom,
                'recurso_tipo': 'Salón',
                'recurso_nombre': salon,
                'fecha': str(fecha_reserva),
                'dia': dia_str,
                'hora_inicio': h_ini_str,
                'hora_fin': h_fin_str,
                'jornada': jornada_str,
                'nrc': nrc,
                'programa': 'Ingeniería de Sistemas',
                'sede': 'PERDOMO',
                'tipo_reserva': 'Clase',
                'observaciones': titulo
            })

        db.session.commit()

        print(f"✅ Docentes nuevos registrados: {profesores_creados}")
        print(f"✅ Reservas insertadas en base de datos: {reservas_creadas}")
        print(f"🔄 Reservas actualizadas: {reservas_actualizadas}")

        # 5. Generar archivo Excel en data/
        os.makedirs(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data')), exist_ok=True)
        excel_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'Plantilla_Reservas_Salas_Computo_Perdomo.xlsx'))

        df_excel = pd.DataFrame(excel_rows)
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df_excel.to_excel(writer, sheet_name='Reservas', index=False)

        print(f"📊 Archivo Excel guardado exitosamente en: {excel_path}")


if __name__ == '__main__':
    ejecutar_carga()
