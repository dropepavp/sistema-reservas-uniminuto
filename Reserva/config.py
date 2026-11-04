import os
import secrets
from datetime import time, timedelta
from datetime import date as date_type
from urllib.parse import urlparse, quote_plus


def _build_safe_db_uri(raw_url: str) -> str:
    """Construye una URI de base de datos segura y normaliza esquemas como postgres://."""
    if not raw_url:
        if os.environ.get('VERCEL') or os.path.exists('/tmp'):
            return 'sqlite:////tmp/sistema_reserva.db'
        return 'sqlite:///sistema_reserva.db'

    raw_url = raw_url.strip().strip('"').strip("'")
    if raw_url.startswith('postgres://'):
        raw_url = raw_url.replace('postgres://', 'postgresql://', 1)

    try:
        parsed = urlparse(raw_url)
        if parsed.password is None:
            return raw_url

        safe_pwd = quote_plus(parsed.password)
        netloc = f"{parsed.username}:{safe_pwd}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        query_part = f"?{parsed.query}" if parsed.query else ""
        return f"{parsed.scheme}://{netloc}{parsed.path}{query_part}"
    except Exception:
        return raw_url


class Config:
    """Configuración base de la aplicación."""

    # Clave secreta — soporta FLASK_SECRET_KEY, SECRET_KEY o valor seguro por defecto
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or os.environ.get('SECRET_KEY') or 'dev-fallback-key-uniminuto-reserva-2026'

    # Base de datos — soporta DATABASE_URL o fallback a SQLite en /tmp
    _db_url = os.environ.get('DATABASE_URL')
    if _db_url:
        SQLALCHEMY_DATABASE_URI = _build_safe_db_uri(_db_url)
    else:
        if os.environ.get('VERCEL') or os.path.exists('/tmp'):
            SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/sistema_reserva.db'
        else:
            SQLALCHEMY_DATABASE_URI = 'sqlite:///sistema_reserva.db'

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configuración de logging
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')

    # Configuración de desarrollo
    DEBUG = os.environ.get('FLASK_ENV') == 'development'

    # Entorno Vercel
    VERCEL = bool(os.environ.get('VERCEL'))

    # Flags de seguridad en cookies de sesión y CSRF
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    WTF_CSRF_TIME_LIMIT = None  # No expirar tokens CSRF antes de que finalice la sesión (evita errores 400 por inactividad)

    # Parámetros para envío de correos (alertas, reportes)
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'localhost')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 25))
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'False').lower() in ('true', '1', 'yes')
    SMTP_USER = os.environ.get('SMTP_USER', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    SMTP_SENDER = os.environ.get('SMTP_SENDER', 'no-reply@example.com')
    ADMIN_EMAILS = os.environ.get('ADMIN_EMAILS', '').split(',') if os.environ.get('ADMIN_EMAILS') else []

    SUPERADMIN_DOCUMENTS = set(
        d.strip() for d in os.environ.get('SUPERADMIN_DOCUMENTS', '80140666').split(',') if d.strip()
    )


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    RATELIMIT_ENABLED = False
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False


# Configuraciones disponibles
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


# Constantes del sistema
class SystemConstants:
    """Constantes del sistema de reservas."""

    # Estados
    ESTADO_PRESTADO = 'Prestado'
    ESTADO_DEVUELTO = 'Devuelto'
    ESTADO_ACTIVA = 'Activa'
    ESTADO_CANCELADA = 'Cancelada'
    ESTADO_COMPLETADA = 'Completada'

    # Recursos
    SALONES_PRINCIPAL = [
        "A205","A301","A304","A403","A501","A502","A503","A504","A505","A506","A507","A508","A509","A510",
        "B101","B102","B103","B104","B105","B106","B107","B108","B109","B110",
        "B201","B202","B203","B204","B301","B302","B303","B304","B305","B306","B307","B308","B309","B310",
        "B401","B402","B403","B404","B405","B406","B407","B408","B409","B410","B501","B502","B503","B504","B505","B506",
        "B602","B603","B604","B605","B606","B607",
        "C301","C302","C303","C304","C305","C306","C307","C308","C309","C310","C311","C312",
        "C401","C402","C403","C404","C405","C406","C407","C408","C409","C410","C411","C412",
        "C501","C502","C503","C504","C505","C506","C507","C508","C509","C510",
        "C601","C602","C603","C604","C605","C606","C607","C608","C609",
        "D501","D502","D503","D504","D505","D506",
        "D601","D602","D603","D605","D606","D607"
    ]
    SALONES_PERDOMO_NORMALES = [
        "202", "204", "303", "403", "404", "406", "407", "501", "503", "504",
        "506", "507", "508", "603", "604", "605", "606", "607", "608", "706",
        "707", "708", "806", "807", "808", "903", "904", "905", "906", "907",
        "908", "1003", "1004", "1006", "1007", "1008"
    ]
    SALONES_PERDOMO_COMPUTO = ["801LS4", "803LS2", "804LS3", "703LS5", "704LS1"]
    SALONES_PERDOMO = SALONES_PERDOMO_NORMALES + SALONES_PERDOMO_COMPUTO

    SALONES_PRINCIPAL_COMPUTO = [
        "A207LS12", "A208LS13", "A209LS6", "A210LS14", "A211LS10", "A212LS11", "A213LS15",
        "A305LS5", "A306LS1", "A307LS2", "A308LS3", "A309LS4", "A310LS7", "A311LS9", "A312LS20", "A313LS8",
        "A401LS24", "A402LS25", "A404LS26", "A405LS23", "A406LS27", "A408LS16", "A409LS17", "A410LS18", "A411LS19",
        "A207LS", "A310"
    ]
    SALONES = SALONES_PRINCIPAL + SALONES_PRINCIPAL_COMPUTO + SALONES_PERDOMO
    AULAS = SALONES
    SALON_MARCA = {
        "A205": "S","A301": "P","A304": "S","A403": "S","A501": "P","A502": "P","A503": "P","A504": "P","A505": "S",
        "A506": "P","A507": "P","A508": "P","A509": "P","A510": "P",
        "B101": "P","B102": "P","B103": "P","B104": "P","B105": "P","B106": "S","B107": "P","B108": "P","B109": "P","B110": "S",
        "B201": "P","B202": "LG","B203": "P","B204": "P",
        "B301": "P","B302": "P","B303": "S","B304": "P","B305": "P","B306": "S","B307": "P","B308": "P","B309": "P","B310": "P",
        "B401": "P","B402": "P","B403": "P","B404": "P","B405": "P",
        "B406": "S","B407": "P","B408": "P","B409": "P","B410": "S",
        "B501": "S","B502": "P","B503": "P","B504": "P","B505": "P","B506": "P",
        "B602": "P","B603": "S","B604": "P","B605": "P","B606": "P","B607": "P",
        "C301": "S","C302": "S","C303": "S","C304": "S","C305": "S","C306": "P","C307": "P","C308": "S","C309": "P",
        "C310": "P","C311": "P","C312": "P",
        "C401": "S","C402": "S","C403": "S","C404": "P","C405": "S","C406": "P",
        "C407": "S","C408": "S","C409": "S","C410": "P","C411": "S","C412": "P",
        "C501": "S","C502": "S","C503": "P","C504": "S","C505": "P","C506": "S",
        "C507": "P","C508": "P","C509": "S","C510": "P",
        "C601": "S","C602": "S","C603": "S","C604": "S","C605": "P","C606": "P","C607": "P","C608": "S","C609": "S",
        "D501": "S","D502": "P","D503": "P","D504": "P","D505": "P","D506": "P",
        "D601": "P","D602": "P","D603": "S","D605": "P","D606": "P","D607": "P",
        "801LS4": "P", "803LS2": "P", "804LS3": "P", "703LS5": "P", "704LS1": "P"
    }
    NINERAS = ["Niñera 1 (31 PC)", "Niñera 2 (31 PC)"]

    # Jornadas
    JORNADA_MANANA_INICIO = time(7, 0)
    JORNADA_MANANA_FIN = time(13, 44)
    JORNADA_TARDE_INICIO = time(13, 45)
    JORNADA_TARDE_FIN = time(18, 14)
    JORNADA_NOCHE_INICIO = time(18, 15)
    JORNADA_NOCHE_FIN = time(22, 0)

    # Nombres de hojas Excel
    SHEET_PRESTAMOS = 'Prestamos_Equipos'
    SHEET_RESERVAS = 'Reservas'
    SHEET_PROFESORES = 'Profesores'
    SHEET_FESTIVOS = 'Festivos'
    SHEET_AUXILIARES = 'Auxiliares'
    SHEET_INVENTARIO = 'Inventario'

    # Categorias de inventario
    CATEGORIAS_INVENTARIO = [
        'Equipos Portátiles',
        'Tablets',
        'Proyectores (Video Beam)',
        'Audio/Video (HDMI, Parlantes)',
        'Periféricos (Teclados, Mouse)',
        'Componentes de Salón'
    ]

    # Festivos 2025
    FESTIVOS_2025 = [
        {'fecha': date_type(2025, 1, 1), 'descripcion': 'Año Nuevo'},
        {'fecha': date_type(2025, 1, 6), 'descripcion': 'Día de los Reyes Magos'},
        {'fecha': date_type(2025, 3, 24), 'descripcion': 'Día de San José'},
        {'fecha': date_type(2025, 4, 17), 'descripcion': 'Jueves Santo'},
        {'fecha': date_type(2025, 4, 18), 'descripcion': 'Viernes Santo'},
        {'fecha': date_type(2025, 5, 1), 'descripcion': 'Día del Trabajo'},
        {'fecha': date_type(2025, 6, 2), 'descripcion': 'Día de la Ascensión'},
        {'fecha': date_type(2025, 6, 23), 'descripcion': 'Corpus Christi'},
        {'fecha': date_type(2025, 6, 30), 'descripcion': 'Sagrado Corazón / San Pedro y San Pablo'},
        {'fecha': date_type(2025, 7, 20), 'descripcion': 'Día de la Independencia'},
        {'fecha': date_type(2025, 8, 7), 'descripcion': 'Batalla de Boyacá'},
        {'fecha': date_type(2025, 8, 18), 'descripcion': 'Asunción de la Virgen'},
        {'fecha': date_type(2025, 10, 13), 'descripcion': 'Día de la Raza'},
        {'fecha': date_type(2025, 11, 3), 'descripcion': 'Día de todos los Santos'},
        {'fecha': date_type(2025, 11, 17), 'descripcion': 'Independencia de Cartagena'},
        {'fecha': date_type(2025, 12, 8), 'descripcion': 'Día de la Inmaculada Concepción'},
        {'fecha': date_type(2025, 12, 25), 'descripcion': 'Navidad'}
    ]


# Configuracion por defecto del administrador
class AdminConfig:
    """Configuración del usuario administrador por defecto."""
    DEFAULT_ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
    DEFAULT_ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@sistema.com')
    # En producción, esta contraseña debe cambiarse obligatoriamente
    DEFAULT_ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or secrets.token_urlsafe(16)
