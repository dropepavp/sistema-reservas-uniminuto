import os
import sys

# Agregar la carpeta padre (Reserva) al PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from database import db, Colaborador, HorarioColaborador
from extensions import db

app = create_app()

def parse_hora(h):
    if not h or h == ' ' or h.strip() == '':
        return None
    h = h.strip()
    if len(h) == 3: # ej: "630" -> "06:30"
        return f"0{h[0]}:{h[1:]}"
    elif len(h) == 4: # ej: "0630" -> "06:30" or "1315" -> "13:15" or "900" -> "09:00" (but 900 is 3 chars)
        if ':' in h:
            return h
        return f"{h[:2]}:{h[2:]}"
    return h


def get_horas(horas_rango):
    if not horas_rango or horas_rango == ' ' or horas_rango.strip() == '':
        return None, None
    partes = horas_rango.split('-')
    if len(partes) != 2:
        return None, None
    return parse_hora(partes[0]), parse_hora(partes[1])


data = [
    {
        "nombre": "OMAR MORALES HERNANDEZ",
        "horario_texto": "Lunes 6:30 am a 2:00 pm, Martes a viernes de 6:30 am a 1:15 pm y Sabado de 6:30 am a 2:00 pm.",
        "semana": {
            "Lunes": {"rango": "0630-1400", "horas": 7.5},
            "Martes": {"rango": "0630-1315", "horas": 6.75},
            "Miercoles": {"rango": "0630-1315", "horas": 6.75},
            "Jueves": {"rango": "0630-1315", "horas": 6.75},
            "Viernes": {"rango": "0630-1315", "horas": 6.75},
            "Sabado": {"rango": "0630-1400", "horas": 7.5},
        }
    },
    {
        "nombre": "DILAN FELIPE PAEZ CAMELO",
        "horario_texto": "Lunes a jueves de 6:30 am a 1:15 pm, Viernes de 6:30 am a 2:00 pm y Sabado de 6:30 am a 2:00 pm.",
        "semana": {
            "Lunes": {"rango": "0630-1315", "horas": 6.75},
            "Martes": {"rango": "0630-1315", "horas": 6.75},
            "Miercoles": {"rango": "0630-1315", "horas": 6.75},
            "Jueves": {"rango": "0630-1315", "horas": 6.75},
            "Viernes": {"rango": "0630-1400", "horas": 7.5},
            "Sabado": {"rango": "0630-1400", "horas": 7.5},
        }
    },
    {
        "nombre": "DELDRAHIR VERGEL CORONEL",
        "horario_texto": "Lunes, Martes, Miercoles 6:45 am a 1:45 pm, jueves y Viernes de 6:45 am a 1:30 y Sabado de 6:30 am a 2:00 pm.",
        "semana": {
            "Lunes": {"rango": "0640-1334", "horas": 6.9},
            "Martes": {"rango": "0640-1334", "horas": 6.9},
            "Miercoles": {"rango": "0640-1334", "horas": 6.9},
            "Jueves": {"rango": "0640-1334", "horas": 6.9},
            "Viernes": {"rango": "0640-1334", "horas": 6.9},
            "Sabado": {"rango": "0630-1400", "horas": 7.5},
        }
    },
    {
        "nombre": "CARLOS ANDRES MELENJE SANTACRUZ",
        "horario_texto": "Lunes, Martes, Miercoles 6:45 am a 1:45 pm, jueves y Viernes de 6:45 am a 1:30 y Sabado de 6:30 am a 2:00 pm.",
        "semana": {
            "Lunes": {"rango": "0640-1325", "horas": 6.75},
            "Martes": {"rango": "0640-1340", "horas": 7.0},
            "Miercoles": {"rango": "0640-1325", "horas": 6.75},
            "Jueves": {"rango": "0640-1325", "horas": 6.75},
            "Viernes": {"rango": "0640-1325", "horas": 6.75},
            "Sabado": {"rango": "1400-2200", "horas": 8.0},
        }
    },
    {
        "nombre": "VACANTE",
        "horario_texto": "",
        "semana": {
            "Lunes": {"rango": "0900-1700", "horas": 7.0},
            "Martes": {"rango": "0900-1700", "horas": 7.0},
            "Miercoles": {"rango": "0900-1700", "horas": 7.0},
            "Jueves": {"rango": "0930-1700", "horas": 6.5},
            "Viernes": {"rango": "0930-1700", "horas": 6.5},
            "Sabado": {"rango": "1400-2200", "horas": 8.0},
        }
    },
    {
        "nombre": "JULIAN DAVID DUEÑAS MARTINEZ",
        "horario_texto": "Lunes, martes 7:30 am a 2:15, miércoles, jueves, viernes 7:15 am a 2:15 pm y Sábado de 6:30 am a 2:00 pm.",
        "semana": {
            "Lunes": {"rango": "0800-1500", "horas": 7.0},
            "Martes": {"rango": "0830-1500", "horas": 6.5},
            "Miercoles": {"rango": "0800-1500", "horas": 7.0},
            "Jueves": {"rango": "0800-1500", "horas": 7.0},
            "Viernes": {"rango": "0800-1500", "horas": 7.0},
            "Sabado": {"rango": "0630-1400", "horas": 7.5},
        }
    },
    {
        "nombre": "LUIS ALEJANDRO CEDIEL CAMELO",
        "horario_texto": "Lunes, Martes, Jueves y Viernes de 3:30 pm a 10:15 pm, miercoles: 3:15 pm a 10:15 pm Sabado de 2:00 pm a 10:00 pm.",
        "semana": {
            "Lunes": {"rango": "1530-2215", "horas": 6.75},
            "Martes": {"rango": "1530-2215", "horas": 6.75},
            "Miercoles": {"rango": "1515-2215", "horas": 7.0},
            "Jueves": {"rango": "1530-2215", "horas": 6.75},
            "Viernes": {"rango": "1530-2215", "horas": 6.75},
            "Sabado": {"rango": "1400-2200", "horas": 8.0},
        }
    },
    {
        "nombre": "OSCAR JAVIER RODRIGUEZ OREJUELA",
        "horario_texto": "Lunes, Martes, Miercoles y Viernes de 3:30 pm a 10:15 pm, Jueves de 2:45 pm a 10:15 pm y Sabado de 6:30 am a 2:00 pm.",
        "semana": {
            "Lunes": {"rango": "1430-2215", "horas": 7.75},
            "Martes": {"rango": "1430-2215", "horas": 7.75},
            "Miercoles": {"rango": "1430-2215", "horas": 7.75},
            "Jueves": {"rango": "1445-2215", "horas": 7.5},
            "Viernes": {"rango": "1430-2215", "horas": 7.75},
            "Sabado": {"rango": "0630-1000", "horas": 3.5},
        }
    },
    {
        "nombre": "OSCAR GIOVANNY CACHOPE CACERES",
        "horario_texto": "Lunes, martes, miercoles, jueves y viernes 1:50 pm a 10:14 pm",
        "semana": {
            "Lunes": {"rango": "1351-2215", "horas": 8.4},
            "Martes": {"rango": "1351-2215", "horas": 8.4},
            "Miercoles": {"rango": "1351-2215", "horas": 8.4},
            "Jueves": {"rango": "1351-2215", "horas": 8.4},
            "Viernes": {"rango": "1351-2215", "horas": 8.4},
        }
    },
    {
        "nombre": "PITER SUAREZ VERGARA",
        "horario_texto": "Lunes, martes, miercoles, jueves y viernes 1:50 pm a 10:14 pm",
        "semana": {
            "Lunes": {"rango": "1351-2215", "horas": 8.4},
            "Martes": {"rango": "1351-2215", "horas": 8.4},
            "Miercoles": {"rango": "1351-2215", "horas": 8.4},
            "Jueves": {"rango": "1351-2215", "horas": 8.4},
            "Viernes": {"rango": "1351-2215", "horas": 8.4},
        }
    },
    {
        "nombre": "JHON FREDY PENAGOS VERGARA",
        "horario_texto": "Lunes, Martes, Miercoles, Jueves de 3:30 pm a 10:15 pm, viernes 3:00 pm a 10:15 pm y Sabado de 6:30 am a 2:15 pm.",
        "semana": {
            "Lunes": {"rango": "1515-2215", "horas": 7.0},
            "Martes": {"rango": "1530-2215", "horas": 6.75},
            "Miercoles": {"rango": "1530-2215", "horas": 6.75},
            "Jueves": {"rango": "1530-2215", "horas": 6.75},
            "Viernes": {"rango": "1500-2215", "horas": 7.25},
            "Sabado": {"rango": "0630-1400", "horas": 7.5},
        }
    },
    {
        "nombre": "PEDRO ALEJANDRO VARELA PINZON",
        "horario_texto": "Lunes, Martes, Miercoles y Viernes de 3:00 pm a 10:15 pm, Jueves de 3:15 pm a 10:15 pm y Sabado de 2:00 pm a 8:00 pm.",
        "semana": {
            "Lunes": {"rango": "1500-2215", "horas": 7.25},
            "Martes": {"rango": "1500-2215", "horas": 7.25},
            "Miercoles": {"rango": "1500-2215", "horas": 7.25},
            "Jueves": {"rango": "1515-2215", "horas": 7.0},
            "Viernes": {"rango": "1500-2215", "horas": 7.25},
            "Sabado": {"rango": "1400-2000", "horas": 6.0},
        }
    },
    {
        "nombre": "HUGO FERNEY PALACIO GOMEZ",
        "horario_texto": "Lunes, Martes, miércoles, Jueves, viernes de 3:15 pm a 10:15 pm y Sabado de 1:00 pm a 8:00 pm.",
        "semana": {
            "Lunes": {"rango": "1515-2215", "horas": 7.0},
            "Martes": {"rango": "1515-2215", "horas": 7.0},
            "Miercoles": {"rango": "1515-2215", "horas": 7.0},
            "Jueves": {"rango": "1515-2215", "horas": 7.0},
            "Viernes": {"rango": "1515-2215", "horas": 7.0},
            "Sabado": {"rango": "1300-2000", "horas": 7.0},
        }
    },
    {
        "nombre": "JAIDER STIVEN RODRIGUEZ SIERRA",
        "horario_texto": "Lunes 7:00 am a 2:00 pm, Martes, Miercoles, Jueves y viernes 7:00 am a 2:15 pm y Sabado de 7:00 am a 1:00 pm.",
        "semana": {
            "Lunes": {"rango": "0700-1400", "horas": 7.0},
            "Martes": {"rango": "0700-1415", "horas": 7.25},
            "Miercoles": {"rango": "0700-1415", "horas": 7.25},
            "Jueves": {"rango": "0700-1415", "horas": 7.25},
            "Viernes": {"rango": "0700-1415", "horas": 7.25},
            "Sabado": {"rango": "0700-1300", "horas": 6.0},
        }
    },
    {
        "nombre": "ANNY HERRERA TEJADA",
        "horario_texto": "Lunes, martes 2:00 pm a 10:00 pm, Miercoles, Jueves y Viernes de 3:00 pm a 10:00 pm y Sabado de 10:00 am a 3:00 pm.",
        "semana": {
            "Lunes": {"rango": "1400-2200", "horas": 8.0},
            "Martes": {"rango": "1400-2200", "horas": 8.0},
            "Miercoles": {"rango": "1500-2200", "horas": 7.0},
            "Jueves": {"rango": "1500-2200", "horas": 7.0},
            "Viernes": {"rango": "1500-2200", "horas": 7.0},
            "Sabado": {"rango": "1000-1500", "horas": 5.0},
        }
    },
    {
        "nombre": "EDUARD ANDRES TALERO",
        "horario_texto": "Lunes, Martes, jueves, viernes 8:00 am a 5:30 pm, miércoles 8:00 am a 5:00 pm.",
        "semana": {
            "Lunes": {"rango": "0800-1730", "horas": 8.5},
            "Martes": {"rango": "0800-1730", "horas": 8.5},
            "Miercoles": {"rango": "0800-1700", "horas": 8.0},
            "Jueves": {"rango": "0800-1730", "horas": 8.5},
            "Viernes": {"rango": "0800-1730", "horas": 8.5},
        }
    },
    {
        "nombre": "ELIZABETH CEBALLOS VILLALOBOS",
        "horario_texto": "Lunes, miercoles, viernes 8:00 am a 5:30 pm, martes, jueves 8:00 am a 5:15 pm.",
        "semana": {
            "Lunes": {"rango": "0800-1730", "horas": 8.5},
            "Martes": {"rango": "0800-1700", "horas": 8.0},
            "Miercoles": {"rango": "0800-1730", "horas": 8.5},
            "Jueves": {"rango": "0800-1730", "horas": 8.5},
            "Viernes": {"rango": "0800-1730", "horas": 8.5},
        }
    }
]

with app.app_context():
    for d in data:
        colab = Colaborador.query.filter_by(nombre_completo=d['nombre']).first()
        if not colab:
            colab = Colaborador(
                nombre_completo=d['nombre'],
                total_horas_semana=42,
                fecha_inicio_horario="15 de julio 2026",
                horario_texto=d['horario_texto'],
                activo=True
            )
            db.session.add(colab)
            db.session.flush()

            # Agregar horarios
            for dia in ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']:
                info_dia = d['semana'].get(dia)
                horario = HorarioColaborador(colaborador_id=colab.id, dia=dia)
                if info_dia:
                    entrada, salida = get_horas(info_dia['rango'])
                    horario.hora_entrada = entrada
                    horario.hora_salida = salida
                    horario.horas_dia = info_dia['horas']
                db.session.add(horario)
    
    db.session.commit()
    print("Colaboradores y horarios importados correctamente!")
