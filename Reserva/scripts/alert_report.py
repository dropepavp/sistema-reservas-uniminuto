"""Generación y envío de informes periódicos de bitácora.

Este script puede ser programado por cron o tarea de Windows para ejecutar
cada día/semana y mandar un reporte de auditoría a los administradores.
"""
import io
from datetime import datetime

from app_improved import create_app
from database import AuditLog
import pandas as pd
from services.alert_service import AlertService


def generar_reporte_bitacora():
    app = create_app()
    with app.app_context():
        registros = AuditLog.query.order_by(AuditLog.fecha.desc(), AuditLog.hora.desc()).all()
        if not registros:
            return None
        data = []
        for log in registros:
            data.append({
                'Fecha': log.fecha.strftime('%Y-%m-%d') if log.fecha else '',
                'Hora': log.hora.strftime('%H:%M:%S') if log.hora else '',
                'Modulo': log.modulo,
                'Accion': log.accion,
                'Usuario': log.usuario_nombre or log.usuario_documento,
                'Descripcion': log.descripcion,
            })
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Bitacora')
        output.seek(0)
        return output.getvalue()


def main():
    contenido = generar_reporte_bitacora()
    if contenido:
        subject = f"Informe de bitácora {datetime.now().strftime('%Y-%m-%d')}"
        body = "Adjunto se encuentra el archivo con el historial completo de la bitácora."
        app = create_app()
        with app.app_context():
            to_list = app.config.get('ADMIN_EMAILS', [])
            if to_list:
                try:
                    AlertService.send_email(subject, body, to_list, attachments=[('bitacora.xlsx', contenido)])
                except Exception as e:
                    print(f"Error enviando correo: {e}")
            else:
                print("No hay destinatarios ADMIN_EMAILS configurados.")
    else:
        print("No se generó ningún contenido para la bitácora")

if __name__ == '__main__':
    main()
