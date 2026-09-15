"""
Módulo de validación de datos para el sistema de reservas.
Contiene validadores robustos para diferentes tipos de datos.
"""
import re
from datetime import datetime, date, time
from typing import Optional, Tuple, Union

class ValidationError(Exception):
    """Excepción personalizada para errores de validación."""
    pass

class DataValidator:
    """Clase con métodos estáticos para validar diferentes tipos de datos."""
    
    @staticmethod
    def validate_cedula(cedula: Union[str, int]) -> Tuple[bool, Optional[Union[int,str]], str]:
        """
        Valida el identificador de usuario/cédula.
        
        Originalmente se usaba para cédulas numéricas, pero ahora también admite
        valores alfanuméricos (por ejemplo correos o nombres de usuario).
        
        Args:
            cedula: Texto o número que identifica al usuario.
            
        Returns:
            Tuple con (es_valido, valor_procesado, mensaje_error).
            `valor_procesado` será `int` si el identificador era sólo dígitos,
            o `str` en caso contrario.
        """
        if not cedula:
            return False, None, "El identificador es requerido"
        
        cedula_str = str(cedula).strip()
        # comprobar longitud razonable
        if len(cedula_str) < 3 or len(cedula_str) > 254:
            return False, None, "El identificador debe tener entre 3 y 254 caracteres"
        
        # número negativo
        if re.match(r'^-\d+$', cedula_str):
            return False, None, "El identificador debe ser un número positivo"

        # sólo dígitos -> se convierte a entero
        if cedula_str.isdigit():
            try:
                cedula_int = int(cedula_str)
                if cedula_int <= 0:
                    return False, None, "El identificador debe ser un número positivo"
                return True, cedula_int, ""
            except (ValueError, TypeError):
                return False, None, "El identificador numérico no es válido"
        
        # en caso de contener letras/caracteres, sólo permitir un conjunto seguro
        # permitimos caracteres típicos de correos y nombres de usuario
        if not re.match(r'^[A-Za-z0-9@._\-]+$', cedula_str):
            return False, None, "El usuario sólo puede contener letras, números y @ . _ -"
        
        return True, cedula_str, ""
    
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, str]:
        """
        Valida un email.
        
        Args:
            email: Email a validar
            
        Returns:
            Tuple con (es_valido, mensaje_error)
        """
        if not email:
            return False, "El email es requerido"
        
        email = email.strip()
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(pattern, email):
            return False, "Formato de email inválido"
        
        if len(email) > 254:
            return False, "Email demasiado largo"
            
        return True, ""
    
    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        """
        Valida una contraseña.
        
        Args:
            password: Contraseña a validar
            
        Returns:
            Tuple con (es_valido, mensaje_error)
        """
        if not password:
            return False, "La contraseña es requerida"
        
        if len(password) < 8:
            return False, "La contraseña debe tener al menos 8 caracteres"
        
        if len(password) > 128:
            return False, "La contraseña es demasiado larga"
        
        # Verificar que tenga al menos un número y una letra
        has_digit = any(c.isdigit() for c in password)
        has_letter = any(c.isalpha() for c in password)
        
        if not (has_digit and has_letter):
            return False, "La contraseña debe contener al menos una letra y un número"
            
        return True, ""
    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, str]:
        """
        Valida un número de teléfono.
        
        Args:
            phone: Teléfono a validar
            
        Returns:
            Tuple con (es_valido, mensaje_error)
        """
        if not phone:
            return True, ""  # Teléfono es opcional
        
        phone = phone.strip()
        # Remover espacios, guiones y paréntesis
        clean_phone = re.sub(r'[\s\-\(\)]+', '', phone)
        
        if not clean_phone.isdigit():
            return False, "El teléfono debe contener solo números"
        
        if len(clean_phone) < 7 or len(clean_phone) > 15:
            return False, "El teléfono debe tener entre 7 y 15 dígitos"
            
        return True, ""
    
    @staticmethod
    def validate_date(date_str: str, format_str: str = '%Y-%m-%d') -> Tuple[bool, Optional[date], str]:
        """
        Valida una fecha.
        
        Args:
            date_str: Fecha como string
            format_str: Formato esperado de la fecha
            
        Returns:
            Tuple con (es_valido, fecha_obj, mensaje_error)
        """
        if not date_str:
            return False, None, "La fecha es requerida"
        
        try:
            date_obj = datetime.strptime(date_str.strip(), format_str).date()
            return True, date_obj, ""
        except ValueError:
            return False, None, f"Formato de fecha inválido. Use {format_str}"
    
    @staticmethod
    def validate_time(time_str: str, format_str: str = '%H:%M') -> Tuple[bool, Optional[time], str]:
        """
        Valida una hora.
        
        Args:
            time_str: Hora como string
            format_str: Formato esperado de la hora
            
        Returns:
            Tuple con (es_valido, hora_obj, mensaje_error)
        """
        if not time_str:
            return False, None, "La hora es requerida"
        
        try:
            time_obj = datetime.strptime(time_str.strip(), format_str).time()
            return True, time_obj, ""
        except ValueError:
            return False, None, f"Formato de hora inválido. Use {format_str}"
    
    @staticmethod
    def validate_time_range(start_time: time, end_time: time) -> Tuple[bool, str]:
        """
        Valida que un rango de tiempo sea válido.
        
        Args:
            start_time: Hora de inicio
            end_time: Hora de fin
            
        Returns:
            Tuple con (es_valido, mensaje_error)
        """
        if start_time >= end_time:
            return False, "La hora de fin debe ser posterior a la hora de inicio"
        
        # Verificar que el rango no sea demasiado largo (más de 12 horas)
        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute
        
        # Manejar el caso donde la hora de fin es al día siguiente
        if end_minutes < start_minutes:
            end_minutes += 24 * 60
        
        duration_minutes = end_minutes - start_minutes
        
        if duration_minutes > 12 * 60:  # 12 horas
            return False, "El rango de tiempo no puede ser mayor a 12 horas"
            
        return True, ""
    
    @staticmethod
    def validate_string_field(value: str, field_name: str, min_length: int = 1, max_length: int = 255, required: bool = True) -> Tuple[bool, str]:
        """
        Valida un campo de texto.
        
        Args:
            value: Valor a validar
            field_name: Nombre del campo (para mensajes de error)
            min_length: Longitud mínima
            max_length: Longitud máxima
            required: Si el campo es requerido
            
        Returns:
            Tuple con (es_valido, mensaje_error)
        """
        if not value or not value.strip():
            if required:
                return False, f"{field_name} es requerido"
            return True, ""
        
        value = value.strip()
        
        if len(value) < min_length:
            return False, f"{field_name} debe tener al menos {min_length} caracteres (mínimo {min_length})"
        
        if len(value) > max_length:
            return False, f"{field_name} no puede tener más de {max_length} caracteres (máximo {max_length})"
        
        # Verificar caracteres especiales peligrosos
        dangerous_chars = ['<', '>', '"', "'", '&', '\0']
        if any(char in value for char in dangerous_chars):
            return False, f"{field_name} contiene caracteres no permitidos"
            
        return True, ""
    
    @staticmethod
    def validate_inventory_number(inv_number: str) -> Tuple[bool, str]:
        """
        Valida un número de inventario.
        
        Args:
            inv_number: Número de inventario
            
        Returns:
            Tuple con (es_valido, mensaje_error)
        """
        if not inv_number:
            return False, "El número de inventario es requerido"
        
        inv_number = inv_number.strip()
        
        # Debe contener solo letras, números y guiones
        if not re.match(r'^[a-zA-Z0-9\-]+$', inv_number):
            return False, "El número de inventario solo puede contener letras, números y guiones"
        
        if len(inv_number) < 3 or len(inv_number) > 20:
            return False, "El número de inventario debe tener entre 3 y 20 caracteres"
            
        return True, ""

class BusinessValidator:
    """Validaciones específicas de las reglas de negocio."""
    
    @staticmethod
    def validate_working_hours(hour: time) -> Tuple[bool, str]:
        """
        Valida que una hora esté dentro del horario laboral.
        
        Args:
            hour: Hora a validar
            
        Returns:
            Tuple con (es_valido, mensaje_error)
        """
        from config import SystemConstants
        
        if hour < SystemConstants.JORNADA_MANANA_INICIO or hour > SystemConstants.JORNADA_NOCHE_FIN:
            return False, f"La hora debe estar entre {SystemConstants.JORNADA_MANANA_INICIO.strftime('%H:%M')} y {SystemConstants.JORNADA_NOCHE_FIN.strftime('%H:%M')}"
        
        return True, ""
    
    @staticmethod
    def validate_future_date(date_obj: date) -> Tuple[bool, str]:
        """
        Valida que una fecha sea futura o actual.
        
        Args:
            date_obj: Fecha a validar
            
        Returns:
            Tuple con (es_valido, mensaje_error)
        """
        today = date.today()
        
        if date_obj < today:
            return False, "No se pueden crear reservas para fechas pasadas"
        
        # Limitar reservas a un año en el futuro
        max_future_days = 365
        if (date_obj - today).days > max_future_days:
            return False, f"No se pueden crear reservas con más de {max_future_days} días de anticipación"
            
        return True, ""