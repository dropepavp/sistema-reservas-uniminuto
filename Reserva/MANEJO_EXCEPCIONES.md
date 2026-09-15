# 🛡️ Guía de Manejo Robusto de Excepciones

## Problema Actual

```python
# ❌ MALO - Demasiado genérico
try:
    resultado = hacer_algo()
except Exception as e:
    flash('Error interno', 'danger')
    return redirect('/')

# Problema: No sabes qué salió mal
# - ¿Base de datos?
# - ¿Validación?
# - ¿Archivo no encontrado?
# - ¿Error de servidor?
```

---

## Solución: Excepciones Específicas

```python
# ✅ BUENO - Manejo específico y informativo
try:
    usuario = Auxiliar.query.get(documento)
    if not usuario:
        raise ValueError("Usuario no encontrado")
    
    if usuario.documento in BLOCKED_USERS:
        raise PermissionError("Usuario bloqueado")
    
    resultado = procesar(usuario)
    
except ValueError as e:
    current_app.logger.warning(f"Validación: {e}")
    flash(f'Datos inválidos: {e}', 'warning')
    return redirect('/formulario')

except PermissionError as e:
    current_app.logger.warning(f"Acceso denegado: {e}")
    flash('No tienes permiso para esta acción', 'danger')
    return redirect('/')

except SQLAlchemy.exc.IntegrityError as e:
    db.session.rollback()
    current_app.logger.error(f"Registro duplicado: {e}")
    flash('Este registro ya existe', 'danger')
    return redirect('/nuevo')

except Exception as e:
    db.session.rollback()
    current_app.logger.error(f"Error inesperado: {e}", exc_info=True)
    flash('Error interno del servidor. Por favor contacta a administración', 'danger')
    return redirect('/')
```

---

## Jerarquía de Excepciones Recomendada

```python
# Crear excepciones personalizadas
# archivo: exceptions.py

class AppError(Exception):
    """Excepción base para la aplicación."""
    pass

class ValidationError(AppError):
    """Error de validación de datos."""
    pass

class AuthenticationError(AppError):
    """Error de autenticación."""
    pass

class AuthorizationError(AppError):
    """Error de autorización."""
    pass

class ResourceNotFoundError(AppError):
    """Recurso no encontrado."""
    pass

class DuplicateResourceError(AppError):
    """Recurso duplicado."""
    pass

class BusinessLogicError(AppError):
    """Error en lógica de negocio."""
    pass
```

---

## Patrones por Tipo de Operación

### 1. Autenticación y Login

```python
@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """Login seguro con manejo robusto de errores."""
    try:
        documento = request.form.get('usuario', '').strip()
        contraseña = request.form.get('contraseña', '').strip()
        
        # Validación de entrada
        if not documento or not contraseña:
            raise ValidationError("Usuario y contraseña requeridos")
        
        # Buscar usuario
        usuario = Auxiliar.query.get(documento)
        if not usuario:
            current_app.logger.warning(f"Intento de login: usuario {documento} no existe")
            raise AuthenticationError("Credenciales inválidas")
        
        # Verificar contraseña
        if not check_password_hash(usuario.contraseña, contraseña):
            current_app.logger.warning(f"Intento de login fallido: {documento}")
            raise AuthenticationError("Credenciales inválidas")
        
        # Login exitoso
        session['usuario'] = usuario.documento
        current_app.logger.info(f"Login exitoso: {usuario.documento}")
        return redirect('/')
    
    except ValidationError as e:
        flash(f'Error: {e}', 'warning')
        return redirect('/login')
    
    except AuthenticationError as e:
        flash('Correo o contraseña incorrectos', 'danger')
        return redirect('/login')
    
    except Exception as e:
        current_app.logger.error(f"Error en login: {e}", exc_info=True)
        flash('Error al procesar login. Intenta nuevamente', 'danger')
        return redirect('/login')
```

### 2. Crear Recurso

```python
@prestamos_bp.route('/crear', methods=['POST'])
@login_required
def crear_prestamo():
    """Crear nuevo préstamo con validación exhaustiva."""
    try:
        # Validar entrada
        profesor_cedula = request.form.get('profesor_cedula')
        equipos = request.form.getlist('equipos[]')
        fecha_inicio = request.form.get('fecha_inicio')
        
        if not profesor_cedula:
            raise ValidationError("Cédula del profesor requerida")
        if not equipos:
            raise ValidationError("Debes seleccionar al menos un equipo")
        
        # Buscar profesor
        profesor = Profesor.query.get(int(profesor_cedula))
        if not profesor:
            raise ResourceNotFoundError(f"Profesor {profesor_cedula} no encontrado")
        
        # Validar disponibilidad
        for equipo_id in equipos:
            inventario = Inventario.query.get(int(equipo_id))
            if not inventario:
                raise ResourceNotFoundError(f"Equipo {equipo_id} no existe")
            if inventario.estado != 'Disponible':
                raise BusinessLogicError(
                    f"Equipo {inventario.item} no está disponible"
                )
        
        # Crear préstamo
        prestamo = PrestamoEquipo(
            cedula_profesor=profesor_cedula,
            fecha_inicio=datetime.strptime(fecha_inicio, '%Y-%m-%d'),
            # ... otros campos
        )
        
        db.session.add(prestamo)
        db.session.commit()
        
        # Auditoría
        registrar_auditoria(
            modulo='prestamos',
            entidad_tipo='PrestamoEquipo',
            accion='CREAR',
            usuario_documento=session.get('usuario'),
            datos_despues=prestamo.to_dict()
        )
        
        flash('Préstamo creado exitosamente', 'success')
        return redirect('/prestamos')
    
    except ValidationError as e:
        flash(f'Datos inválidos: {e}', 'warning')
        return redirect('/prestamos/nuevo')
    
    except ResourceNotFoundError as e:
        current_app.logger.warning(f"Recurso no encontrado: {e}")
        flash(f'No encontrado: {e}', 'danger')
        return redirect('/prestamos/nuevo')
    
    except BusinessLogicError as e:
        flash(f'No se pudo procesar: {e}', 'warning')
        return redirect('/prestamos/nuevo')
    
    except ValueError as e:
        flash(f'Formato inválido: {e}', 'warning')
        return redirect('/prestamos/nuevo')
    
    except db.exc.IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"Integridad de BD: {e}")
        flash('Este registro ya existe', 'danger')
        return redirect('/prestamos/nuevo')
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al crear préstamo: {e}", exc_info=True)
        flash('Error interno. Por favor intenta nuevamente', 'danger')
        return redirect('/prestamos/nuevo')
```

### 3. Editar Recurso

```python
@prestamos_bp.route('/editar/<int:prestamo_id>', methods=['GET', 'POST'])
@login_required
@permiso_requerido('prestamos', 'editar')
def editar_prestamo(prestamo_id):
    """Editar préstamo existente."""
    try:
        prestamo = PrestamoEquipo.query.get_or_404(prestamo_id)
        
        if request.method == 'POST':
            # Validar cambios
            estado = request.form.get('estado')
            if estado not in ['Activo', 'Devuelto', 'Cancelado']:
                raise ValidationError(f"Estado inválido: {estado}")
            
            # Guardar datos anteriores para auditoría
            datos_antes = prestamo.to_dict()
            
            # Aplicar cambios
            prestamo.estado = estado
            # ... otros cambios
            
            db.session.commit()
            
            # Auditoría
            registrar_auditoria(
                modulo='prestamos',
                entidad_tipo='PrestamoEquipo',
                accion='EDITAR',
                usuario_documento=session.get('usuario'),
                datos_antes=datos_antes,
                datos_despues=prestamo.to_dict()
            )
            
            flash('Préstamo actualizado', 'success')
            return redirect('/prestamos')
        
        return render_template('editar_prestamo.html', prestamo=prestamo)
    
    except ValidationError as e:
        flash(f'Datos inválidos: {e}', 'warning')
        return redirect(f'/prestamos/editar/{prestamo_id}')
    
    except db.exc.IntegrityError as e:
        db.session.rollback()
        flash('No se pudo guardar los cambios', 'danger')
        return redirect(f'/prestamos/editar/{prestamo_id}')
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al editar: {e}", exc_info=True)
        flash('Error al guardar cambios', 'danger')
        return redirect(f'/prestamos/editar/{prestamo_id}')
```

### 4. Eliminar Recurso

```python
@prestamos_bp.route('/eliminar/<int:prestamo_id>', methods=['POST'])
@login_required
@permiso_requerido('prestamos', 'eliminar')
def eliminar_prestamo(prestamo_id):
    """Eliminar préstamo con validaciones."""
    try:
        prestamo = PrestamoEquipo.query.get_or_404(prestamo_id)
        
        # Validar que se pueda eliminar
        if prestamo.estado == 'Devuelto':
            raise BusinessLogicError("No se puede eliminar préstamos devueltos")
        
        if prestamo.fecha_inicio < date.today():
            raise BusinessLogicError("No se pueden eliminar préstamos pasados")
        
        # Eliminar
        datos_eliminados = prestamo.to_dict()
        db.session.delete(prestamo)
        db.session.commit()
        
        # Auditoría
        registrar_auditoria(
            modulo='prestamos',
            entidad_tipo='PrestamoEquipo',
            accion='ELIMINAR',
            usuario_documento=session.get('usuario'),
            datos_antes=datos_eliminados,
            descripcion=f"Eliminado préstamo {prestamo_id}"
        )
        
        flash('Préstamo eliminado', 'success')
        return redirect('/prestamos')
    
    except BusinessLogicError as e:
        flash(f'No se puede eliminar: {e}', 'warning')
        return redirect('/prestamos')
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al eliminar: {e}", exc_info=True)
        flash('Error al eliminar', 'danger')
        return redirect('/prestamos')
```

---

## Logging Estructurado

```python
import logging

# Crear logger
logger = logging.getLogger(__name__)

# Configurar formato
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Usar en excepciones
try:
    algo()
except ValidationError as e:
    logger.warning(f"Validación fallida: {e}", extra={
        'usuario': session.get('usuario'),
        'modulo': 'prestamos',
        'accion': 'crear'
    })
except Exception as e:
    logger.error(f"Error inesperado: {e}", exc_info=True, extra={
        'usuario': session.get('usuario'),
        'endpoint': request.endpoint,
        'metodo': request.method
    })
```

---

## Error Pages Personalizadas

```python
# app.py

@app.errorhandler(404)
def error_404(error):
    """Página personalizada para 404."""
    return render_template('errors/404.html'), 404

@app.errorhandler(403)
def error_403(error):
    """Página personalizada para 403 Forbidden."""
    return render_template('errors/403.html'), 403

@app.errorhandler(500)
def error_500(error):
    """Página personalizada para 500 Error Interno."""
    current_app.logger.error(f"Error 500: {error}", exc_info=True)
    return render_template('errors/500.html'), 500
```

---

## ✅ Checklist de Implementación

- [ ] Crear archivo `exceptions.py` con excepciones personalizadas
- [ ] Reemplazar try/except genéricos por específicos
- [ ] Agregar logging detallado en cada excepción
- [ ] Implementar error pages (404, 500)
- [ ] Probar flujos de error
- [ ] Documentar excepciones en servicios
- [ ] Validar mensajes de error en producción
- [ ] Revisar logs regularmente

---

## Resumen de Cambios

| Problema | Solución | Beneficio |
|----------|----------|----------|
| Excepciones genéricas | Excepciones específicas | Debugging fácil |
| Sin logging | Logging estructurado | Auditoría completa |
| Mensajes vagos | Mensajes claros | Mejor UX |
| No registra errores | Excepciones capturadas | Trazabilidad |
| Error pages por defecto | Páginas personalizadas | Mejor experiencia |

---

**Guía de Manejo de Excepciones - Sistema de Reservas**  
Implementación típica: 1-2 horas para refactorizar blueprints críticos
