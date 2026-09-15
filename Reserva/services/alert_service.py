"""Servicio para generar alertas y enviar correos automáticos.

Incluye comprobaciones de préstamos vencidos y reservas próximas, así como
un pequeño helper de envío de email que utiliza la configuración de
`config.Config`.
"""
from datetime import date, timedelta
import smtplib
from email.message import EmailMessage

from database import PrestamoEquipo, Reserva
from config import config


class AlertService:
    @staticmethod
    def check_overdue_prestamos(sede_id=None):
        """Devuelve lista de préstamos cuyo día de préstamo es anterior a hoy.

        Si *sede_id* se proporciona se filtra por dicha sede. La función no
        modifica estado alguno, sólo devuelve los objetos.
        """
        hoy = date.today()
        query = PrestamoEquipo.query.filter(PrestamoEquipo.estado == 'Prestado')
        if sede_id:
            query = query.filter_by(sede_id=sede_id)
        return query.filter(PrestamoEquipo.fecha_prestamo < hoy).all()

    @staticmethod
    def check_upcoming_reservas(days=2, sede_id=None):
        """Devuelve reservas activas cuyo día está en el rango [hoy, hoy+days]."""
        hoy = date.today()
        hasta = hoy + timedelta(days=days)
        query = Reserva.query.filter(
            Reserva.estado == 'Activa',
            Reserva.fecha.between(hoy, hasta)
        )
        if sede_id:
            query = query.filter_by(sede_id=sede_id)
        return query.all()

    @staticmethod
    def send_email(subject, body, to_addresses, attachments=None):
        """Envía un correo simple.

        *to_addresses* puede ser una lista o un solo string. *attachments* debe
        ser una lista de tuplas (filename, bytes) si se desea adjuntar archivos.
        """
        cfg = config['default']
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = cfg.SMTP_SENDER
        if isinstance(to_addresses, (list, tuple)):
            msg['To'] = ', '.join(to_addresses)
        else:
            msg['To'] = to_addresses
        msg.set_content(body)

        if attachments:
            for fname, data in attachments:
                msg.add_attachment(data, maintype='application', subtype='octet-stream', filename=fname)

        with smtplib.SMTP(cfg.SMTP_SERVER, cfg.SMTP_PORT) as smtp:
            if cfg.SMTP_USE_TLS:
                smtp.starttls()
            if cfg.SMTP_USER and cfg.SMTP_PASSWORD:
                smtp.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
            smtp.send_message(msg)
