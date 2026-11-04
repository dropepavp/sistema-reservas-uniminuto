import os
import sys
from datetime import datetime, date, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from database import db, Reserva, ClaseSalaComputo, Recurso, Ubicacion, Sede, Profesor

def sincronizar_reservas_a_clases(sede_id=None):
    """
    Sincroniza las reservas hacia clases_salas_computo para permitir
    el control de clases y el registro de asistencia docente.
    """
    app = create_app()
    with app.app_context():
        # Mapeo de alias oficiales para salas de Perdomo
        alias_map = {
            'LS1': '704LS1',
            'LS2': '803LS2',
            'LS3': '804LS3',
            'LS4': '801LS4',
            'LS5': '703LS5'
        }
        
        sede_perdomo = Sede.query.filter(Sede.nombre.ilike('%perdomo%')).first()
        perdomo_id = sede_perdomo.id if sede_perdomo else 1
        
        sede_engativa = Sede.query.filter(Sede.nombre.ilike('%engativ%')).first()
        engativa_id = sede_engativa.id if sede_engativa else 2

        # Cache de recursos
        recursos = Recurso.query.join(Ubicacion).all()
        rec_map = {}
        for r in recursos:
            s_id = r.ubicacion.sede_id if r.ubicacion else None
            rec_map[(r.nombre.upper(), s_id)] = r
            if (r.nombre.upper(), None) not in rec_map:
                rec_map[(r.nombre.upper(), None)] = r

        query_res = Reserva.query
        if sede_id:
            query_res = query_res.filter(Reserva.sede_id == int(sede_id))
            
        reservas = query_res.order_by(Reserva.fecha.asc(), Reserva.hora_inicio.asc()).all()
        print(f"Total reservas a sincronizar: {len(reservas)}")
        
        creados = 0
        actualizados = 0
        
        for r in reservas:
            nombre_salon = (r.recurso_nombre or 'Salón').strip()
            if nombre_salon in alias_map:
                nombre_salon = alias_map[nombre_salon]

            # Determinar sede_id
            s_id = r.sede_id
            if not s_id:
                if nombre_salon in ['704LS1', '803LS2', '804LS3', '801LS4', '703LS5']:
                    s_id = perdomo_id
                elif nombre_salon.startswith(('A', 'B', 'C', 'D')) or 'Niñera' in nombre_salon:
                    s_id = engativa_id
                else:
                    s_id = perdomo_id

            # Determinar recurso_id
            rec_id = r.recurso_id
            if not rec_id or not Recurso.query.get(rec_id):
                match_rec = rec_map.get((nombre_salon.upper(), s_id)) or rec_map.get((nombre_salon.upper(), None))
                if match_rec:
                    rec_id = match_rec.id

            # Materia
            obs = (r.observaciones or '').strip()
            if obs and not obs.lower().startswith('reserva generada') and obs.lower() not in ['prueba automática', 'ok', 'prueba']:
                materia = obs
            elif r.nrc:
                materia = f"Clase NRC {r.nrc}"
            else:
                materia = r.programa or "Clase Académica"

            # Horas académicas
            if r.hora_inicio and r.hora_fin:
                dt_ini = datetime.combine(date.min, r.hora_inicio)
                dt_fin = datetime.combine(date.min, r.hora_fin)
                duracion_seg = (dt_fin - dt_ini).total_seconds()
                horas_acad = round(duracion_seg / 3600.0, 2)
            else:
                horas_acad = 1.5

            # Jornada
            jornada = r.jornada
            if not jornada and r.hora_inicio:
                if r.hora_inicio < time(13, 45):
                    jornada = 'MAÑANA'
                elif r.hora_inicio < time(18, 15):
                    jornada = 'TARDE'
                else:
                    jornada = 'NOCHE'
            elif jornada:
                jornada = jornada.upper()

            # Asistencia y Estado
            asistencia = 'Sí' if r.estado == 'Completada' else 'No'
            if r.estado == 'Cancelada':
                estado = 'Cancelada'
            elif r.estado == 'Completada':
                estado = 'Realizada'
            else:
                estado = 'Programada'

            obs_final = f"NRC: {r.nrc} | {r.observaciones or ''}".strip(' |')

            # Verificar si ya existe una clase exactamente en la misma fecha, hora y salón
            clase_existente = ClaseSalaComputo.query.filter(
                ClaseSalaComputo.fecha == r.fecha,
                ClaseSalaComputo.salon == nombre_salon,
                ClaseSalaComputo.hora_inicio == r.hora_inicio
            ).first()

            if clase_existente:
                # Actualizar campos informativos respetando si ya se tomó asistencia
                clase_existente.sede_id = s_id
                clase_existente.recurso_id = rec_id
                clase_existente.cedula_profesor = r.cedula_profesor
                clase_existente.nombre_profesor = r.nombre_profesor
                clase_existente.materia = materia
                clase_existente.horas_academicas = horas_acad
                clase_existente.jornada = jornada
                clase_existente.programa = r.programa
                clase_existente.programa_id = r.programa_id
                if not clase_existente.observaciones:
                    clase_existente.observaciones = obs_final
                actualizados += 1
            else:
                nueva_clase = ClaseSalaComputo(
                    fecha=r.fecha,
                    hora_inicio=r.hora_inicio,
                    hora_fin=r.hora_fin,
                    sede_id=s_id,
                    recurso_id=rec_id,
                    salon=nombre_salon,
                    cedula_profesor=r.cedula_profesor,
                    nombre_profesor=r.nombre_profesor,
                    materia=materia,
                    asistencia=asistencia,
                    horas_academicas=horas_acad,
                    jornada=jornada,
                    num_estudiantes=None,
                    programa=r.programa,
                    programa_id=r.programa_id,
                    modalidad='Presencial',
                    estado=estado,
                    observaciones=obs_final
                )
                db.session.add(nueva_clase)
                creados += 1

        db.session.commit()
        print(f"\nSincronización completada con éxito.")
        print(f"  Clases creadas: {creados}")
        print(f"  Clases actualizadas: {actualizados}")
        print(f"  Total clases en BD: {ClaseSalaComputo.query.count()}")

if __name__ == '__main__':
    sincronizar_reservas_a_clases()

