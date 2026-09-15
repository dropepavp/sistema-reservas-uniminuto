# 🎯 Validación Avanzada de Reglas de Negocio

## Estado Actual

```python
# validators.py tiene validación de DATOS
# Pero falta validación de LÓGICA DE NEGOCIO

# ❌ NO DETECTA:
# - Profesor prestando dos equipos a la misma hora
# - Salón reservado en dos franjas horarias simultáneamente
# - Préstamo a profesor bloqueado
# - Inventario negativo
# - Horario fuera de jornadas académicas
```

---

## 1. Conflictos de Reserva

### Problema

```python
# CASO PROBLEMÁTICO:
# Profesor hace 2 reservas simultáneas del mismo salón

# 09:00 - 10:00 Salón A101
# 09:30 - 10:30 Salón A101  ← CONFLICTO no detectado
```

### Solución: Validador de Conflictos

```python
# validators.py - BusinessValidator mejorado

class BusinessValidator:
    """Validación de reglas de negocio."""
    
    @staticmethod
    def validar_conflicto_reserva(
        cedula_profesor: int,
        recurso_nombre: str,
        fecha: date,
        hora_inicio: time,
        hora_fin: time,
        id_reserva_existente: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Verifica si hay conflicto de reserva.
        
        Returns: (es_valido, mensaje_error)
        """
        from database import Reserva
        
        # Consulta: buscar reservas en la misma jornada/salón
        query = Reserva.query.filter(
            Reserva.cedula_profesor == cedula_profesor,
            Reserva.recurso_nombre == recurso_nombre,
            Reserva.fecha == fecha,
            Reserva.estado == 'activa'
        )
        
        # Si es edición, excluir la reserva actual
        if id_reserva_existente:
            query = query.filter(Reserva.id_reserva != id_reserva_existente)
        
        reservas_existentes = query.all()
        
        for reserva_existente in reservas_existentes:
            # Verificar si hay solapamiento de horas
            # Reserva 1: 09:00-10:00
            # Reserva 2: 09:30-10:30  ← OVERLAP
            
            if BusinessValidator._hay_solapamiento_horas(
                hora_inicio, hora_fin,
                reserva_existente.hora_inicio, reserva_existente.hora_fin
            ):
                return False, (
                    f"El {recurso_nombre} ya está reservado entre "
                    f"{reserva_existente.hora_inicio.strftime('%H:%M')} y "
                    f"{reserva_existente.hora_fin.strftime('%H:%M')}"
                )
        
        return True, ""
    
    @staticmethod
    def _hay_solapamiento_horas(
        inicio1: time, fin1: time,
        inicio2: time, fin2: time
    ) -> bool:
        """Detecta solapamiento entre dos rangos horarios."""
        # Convertir a minutos desde medianoche para fácil comparación
        inicio1_min = inicio1.hour * 60 + inicio1.minute
        fin1_min = fin1.hour * 60 + fin1.minute
        inicio2_min = inicio2.hour * 60 + inicio2.minute
        fin2_min = fin2.hour * 60 + fin2.minute
        
        # Hay overlap si: inicio1 < fin2 AND inicio2 < fin1
        return inicio1_min < fin2_min and inicio2_min < fin1_min
```

### Uso en Blueprint

```python
# blueprints/reservas.py

@reservas_bp.route('/crear', methods=['POST'])
@login_required
def crear_reserva():
    """Crea reserva con validación de conflictos."""
    try:
        cedula = request.form.get('cedula_profesor')
        recurso = request.form.get('recurso_nombre')
        fecha_str = request.form.get('fecha')
        hora_inicio_str = request.form.get('hora_inicio')
        hora_fin_str = request.form.get('hora_fin')
        
        # Validar formato
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M').time()
        hora_fin = datetime.strptime(hora_fin_str, '%H:%M').time()
        
        # VALIDAR CONFLICTOS
        es_valido, msg_conflicto = BusinessValidator.validar_conflicto_reserva(
            cedula_profesor=cedula,
            recurso_nombre=recurso,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin
        )
        
        if not es_valido:
            flash(msg_conflicto, 'danger')
            return redirect('/reservas/nueva')
        
        # Si llegó aquí, crear reserva
        reserva = Reserva(...)
        db.session.add(reserva)
        db.session.commit()
        
        flash('Reserva creada exitosamente', 'success')
        return redirect('/reservas')
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error: {e}")
        flash('Error al crear reserva', 'danger')
        return redirect('/reservas/nueva')
```

---

## 2. Validación de Disponibilidad de Equipos

### Problema

```python
# ❌ CASO PROBLEMÁTICO:
# Prestar equipo que NO está disponible

prestamo = PrestamoEquipo(
    inventario_id=1,  # Laptop con estado 'En Préstamo'
    cedula_profesor=123
)
# Sin validación, se permite duplicar
```

### Solución

```python
# validators.py

class BusinessValidator:
    
    @staticmethod
    def validar_disponibilidad_equipo(
        inventario_id: int
    ) -> Tuple[bool, str]:
        """Verifica si equipo está disponible para préstamo."""
        from database import Inventario
        
        inventario = Inventario.query.get(inventario_id)
        
        if not inventario:
            return False, "Equipo no existe"
        
        if inventario.estado != 'Disponible':
            estado_actual = inventario.estado
            return False, (
                f"Equipo no está disponible. "
                f"Estado actual: {estado_actual}"
            )
        
        if inventario.es_por_cantidad:
            if (inventario.cantidad_disponible or 0) <= 0:
                return False, "No hay cantidad disponible de este equipo"
        
        return True, ""
    
    @staticmethod
    def validar_disponibilidad_multiples_equipos(
        equipos_ids: List[int]
    ) -> Tuple[bool, List[str]]:
        """Valida múltiples equipos."""
        errores = []
        
        for equipo_id in equipos_ids:
            es_valido, error = BusinessValidator.validar_disponibilidad_equipo(equipo_id)
            if not es_valido:
                errores.append(error)
        
        return len(errores) == 0, errores
```

### Uso

```python
# blueprints/prestamos.py

@prestamos_bp.route('/crear', methods=['POST'])
def crear_prestamo():
    """Crea préstamo con validación de disponibilidad."""
    try:
        equipos_ids = request.form.getlist('equipos[]')
        
        # VALIDAR DISPONIBILIDAD
        es_disponible, errores = BusinessValidator.validar_disponibilidad_multiples_equipos(
            equipos_ids
        )
        
        if not es_disponible:
            for error in errores:
                flash(error, 'danger')
            return redirect('/prestamos/nuevo')
        
        # Crear préstamo
        prestamo = PrestamoEquipo(...)
        db.session.add(prestamo)
        db.session.commit()
        
        flash('Préstamo creado', 'success')
        return redirect('/prestamos')
```

---

## 3. Validación de Profesor Activo

### Problema

```python
# ❌ Profesor inactivo/bloqueado sigue pudiendo pedir prestamos
profesor = Profesor.query.get(123)
# Sin validación de estado
```

### Solución

```python
# database.py - Agregar estado a Profesor

class Profesor(db.Model):
    __tablename__ = 'profesores'
    
    cedula: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(String, nullable=False)
    estado: Mapped[str] = mapped_column(
        String,
        default='activo',
        nullable=False
        # Valores: 'activo', 'inactivo', 'bloqueado'
    )
    # ... resto de campos


# validators.py

class BusinessValidator:
    
    @staticmethod
    def validar_profesor_activo(cedula: int) -> Tuple[bool, str]:
        """Verifica que profesor esté activo."""
        from database import Profesor
        
        profesor = Profesor.query.get(cedula)
        
        if not profesor:
            return False, "Profesor no encontrado"
        
        if profesor.estado == 'bloqueado':
            return False, f"Profesor {profesor.nombre_completo} está bloqueado"
        
        if profesor.estado == 'inactivo':
            return False, f"Profesor {profesor.nombre_completo} está inactivo"
        
        return True, ""
```

---

## 4. Validación de Horarios (Jornadas Académicas)

### Problema

```python
# ❌ Préstamo de 07:00-08:00 (fuera de jornada académica)
# ❌ Reserva de 23:00-00:00 (fuera de horario)
```

### Solución

```python
# config.py

class SystemConstants:
    """Horarios académicos."""
    
    JORNADA_MANANA_INICIO = time(6, 0)
    JORNADA_MANANA_FIN = time(12, 30)
    
    JORNADA_TARDE_INICIO = time(12, 30)
    JORNADA_TARDE_FIN = time(19, 0)
    
    JORNADA_NOCHE_INICIO = time(19, 0)
    JORNADA_NOCHE_FIN = time(22, 0)
    
    @classmethod
    def es_hora_valida(cls, hora: time) -> bool:
        """Verifica si hora está en jornadas académicas."""
        jornadas = [
            (cls.JORNADA_MANANA_INICIO, cls.JORNADA_MANANA_FIN),
            (cls.JORNADA_TARDE_INICIO, cls.JORNADA_TARDE_FIN),
            (cls.JORNADA_NOCHE_INICIO, cls.JORNADA_NOCHE_FIN),
        ]
        
        for inicio, fin in jornadas:
            if inicio <= hora <= fin:
                return True
        
        return False


# validators.py

class BusinessValidator:
    
    @staticmethod
    def validar_horario_academico(
        hora_inicio: time,
        hora_fin: time
    ) -> Tuple[bool, str]:
        """Verifica que horario esté dentro de jornadas académicas."""
        from config import SystemConstants
        
        if not SystemConstants.es_hora_valida(hora_inicio):
            return False, f"Hora inicio {hora_inicio.strftime('%H:%M')} está fuera de jornadas académicas"
        
        if not SystemConstants.es_hora_valida(hora_fin):
            return False, f"Hora fin {hora_fin.strftime('%H:%M')} está fuera de jornadas académicas"
        
        if hora_inicio >= hora_fin:
            return False, "Hora inicio debe ser menor que hora fin"
        
        return True, ""
```

---

## 5. Validación de Duración Máxima

### Problema

```python
# ❌ Préstamo de 15 horas (muy largo)
# ❌ Reserva de 8 horas (muy larga)
```

### Solución

```python
# validators.py

class BusinessValidator:
    
    MAX_DURACION_PRESTAMO = 4  # horas
    MAX_DURACION_RESERVA = 2   # horas
    
    @staticmethod
    def validar_duracion_prestamo(
        hora_inicio: time,
        hora_fin: time
    ) -> Tuple[bool, str]:
        """Verifica que duración sea válida."""
        from datetime import datetime, timedelta
        
        # Calcular duración
        inicio = datetime.combine(date.today(), hora_inicio)
        fin = datetime.combine(date.today(), hora_fin)
        duracion_horas = (fin - inicio).total_seconds() / 3600
        
        if duracion_horas > BusinessValidator.MAX_DURACION_PRESTAMO:
            return False, (
                f"Duración máxima de préstamo es "
                f"{BusinessValidator.MAX_DURACION_PRESTAMO}h"
            )
        
        if duracion_horas <= 0:
            return False, "Duración debe ser positiva"
        
        return True, ""
    
    @staticmethod
    def validar_duracion_reserva(
        hora_inicio: time,
        hora_fin: time
    ) -> Tuple[bool, str]:
        """Verifica que duración de reserva sea válida."""
        from datetime import datetime
        
        inicio = datetime.combine(date.today(), hora_inicio)
        fin = datetime.combine(date.today(), hora_fin)
        duracion_horas = (fin - inicio).total_seconds() / 3600
        
        if duracion_horas > BusinessValidator.MAX_DURACION_RESERVA:
            return False, (
                f"Duración máxima de reserva es "
                f"{BusinessValidator.MAX_DURACION_RESERVA}h"
            )
        
        return True, ""
```

---

## 6. Validación de Fecha Futura

### Problema

```python
# ❌ Crear reserva para hace 5 días
# ❌ Crear préstamo para hace 1 mes
```

### Solución

```python
# validators.py

class BusinessValidator:
    
    MIN_DIAS_ADELANTO_RESERVA = 1  # Mínimo 1 día adelante
    MAX_DIAS_ADELANTO_RESERVA = 30  # Máximo 30 días adelante
    
    @staticmethod
    def validar_fecha_reserva(fecha_reserva: date) -> Tuple[bool, str]:
        """Verifica que fecha sea válida."""
        hoy = date.today()
        dias_diferencia = (fecha_reserva - hoy).days
        
        if dias_diferencia < BusinessValidator.MIN_DIAS_ADELANTO_RESERVA:
            return False, (
                f"Reserva debe ser con mínimo "
                f"{BusinessValidator.MIN_DIAS_ADELANTO_RESERVA} día(s) adelante"
            )
        
        if dias_diferencia > BusinessValidator.MAX_DIAS_ADELANTO_RESERVA:
            return False, (
                f"Reserva no puede ser más de "
                f"{BusinessValidator.MAX_DIAS_ADELANTO_RESERVA} días adelante"
            )
        
        return True, ""
```

---

## 7. Integración en Blueprint

```python
# blueprints/reservas.py - Validación completa

@reservas_bp.route('/crear', methods=['POST'])
@login_required
def crear_reserva():
    """Crea reserva con todas las validaciones."""
    try:
        # Obtener datos
        cedula = request.form.get('cedula_profesor')
        recurso = request.form.get('recurso_nombre')
        fecha_str = request.form.get('fecha')
        hora_inicio_str = request.form.get('hora_inicio')
        hora_fin_str = request.form.get('hora_fin')
        
        # Parsear
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M').time()
        hora_fin = datetime.strptime(hora_fin_str, '%H:%M').time()
        
        # VALIDAR 1: Profesor activo
        es_activo, msg = BusinessValidator.validar_profesor_activo(cedula)
        if not es_activo:
            flash(msg, 'danger')
            return redirect('/reservas/nueva')
        
        # VALIDAR 2: Horario académico
        es_horario_ok, msg = BusinessValidator.validar_horario_academico(
            hora_inicio, hora_fin
        )
        if not es_horario_ok:
            flash(msg, 'danger')
            return redirect('/reservas/nueva')
        
        # VALIDAR 3: Duración
        es_duracion_ok, msg = BusinessValidator.validar_duracion_reserva(
            hora_inicio, hora_fin
        )
        if not es_duracion_ok:
            flash(msg, 'danger')
            return redirect('/reservas/nueva')
        
        # VALIDAR 4: Fecha futura
        es_fecha_ok, msg = BusinessValidator.validar_fecha_reserva(fecha)
        if not es_fecha_ok:
            flash(msg, 'danger')
            return redirect('/reservas/nueva')
        
        # VALIDAR 5: Conflictos
        es_conflicto_ok, msg = BusinessValidator.validar_conflicto_reserva(
            cedula, recurso, fecha, hora_inicio, hora_fin
        )
        if not es_conflicto_ok:
            flash(msg, 'danger')
            return redirect('/reservas/nueva')
        
        # ✅ TODO VALIDADO - Crear reserva
        reserva = Reserva(
            cedula_profesor=cedula,
            recurso_nombre=recurso,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            estado='activa'
        )
        
        db.session.add(reserva)
        db.session.commit()
        
        # Auditoría
        registrar_auditoria(
            modulo='reservas',
            entidad_tipo='Reserva',
            accion='CREAR',
            usuario_documento=session.get('usuario'),
            datos_despues=reserva.to_dict()
        )
        
        flash('Reserva creada exitosamente', 'success')
        return redirect('/reservas')
    
    except ValueError as e:
        flash(f'Datos inválidos: {e}', 'warning')
        return redirect('/reservas/nueva')
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error: {e}", exc_info=True)
        flash('Error al crear reserva', 'danger')
        return redirect('/reservas/nueva')
```

---

## ✅ Checklist de Validación de Negocio

```
Conflictos:
- [x] Detectar solapamiento de horas
- [x] Validar no duplicación de reservas
- [x] Validar no duplicación de préstamos

Disponibilidad:
- [x] Verificar estado de equipo
- [x] Validar cantidad disponible
- [x] Validar estado de profesor

Horarios:
- [x] Validar jornadas académicas
- [x] Validar duración máxima
- [x] Validar fecha futura

Reglas de Negocio:
- [x] Profesor activo
- [x] Equipo disponible
- [x] Horario válido
- [x] Duración dentro de límites
- [x] Fecha futura
- [x] Sin conflictos
```

---

**Guía de Validación Avanzada de Negocio**  
ROI: Muy Alto | Complejidad: Media | Impacto: Integridad de datos
