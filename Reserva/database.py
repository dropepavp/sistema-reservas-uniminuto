from sqlalchemy import Integer, String, Text, Date, Time, Enum, ForeignKey, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from datetime import date as date_type, time as time_type
import json
from extensions import db

class Auxiliar(db.Model):
    __tablename__ = 'auxiliares'
    documento: Mapped[str] = mapped_column(String, primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(String, nullable=False)
    correo: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    contraseña: Mapped[str] = mapped_column(String, nullable=False)
    rol: Mapped[str] = mapped_column(String, nullable=False, default='auxiliar')
    sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes.id'), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ultimo_acceso: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sede: Mapped[Optional["Sede"]] = relationship()
    sedes_asignadas: Mapped[list["AuxiliarSede"]] = relationship(
        back_populates="auxiliar", cascade="all, delete-orphan"
    )

class AuxiliarSede(db.Model):
    __tablename__ = 'auxiliar_sedes'
    usuario_documento: Mapped[str] = mapped_column(
        ForeignKey('auxiliares.documento', ondelete='CASCADE'), primary_key=True
    )
    sede_id: Mapped[int] = mapped_column(
        ForeignKey('sedes.id'), primary_key=True
    )
    auxiliar: Mapped["Auxiliar"] = relationship(back_populates="sedes_asignadas")
    sede: Mapped["Sede"] = relationship()

class ProgramaAcademico(db.Model):
    """Catálogo maestro de Programas Académicos UNIMINUTO."""
    __tablename__ = 'programas_academicos'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)  # ej: ADMI, ISUM, ICDI, TINF
    nombre: Mapped[str] = mapped_column(String(200), index=True, nullable=False)  # ej: ADMINISTRACIÓN DE EMPRESAS
    nivel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)  # Pregrado, Posgrado, Técnico Profesional, Departamento Académico
    sub_nivel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)  # Pregrado, Especialización, Maestría, Tecnología, etc.
    periodo: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Semestral, Cuatrimestral
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    profesores: Mapped[list["Profesor"]] = relationship(back_populates="programa_rel")
    estudiantes: Mapped[list["Estudiante"]] = relationship(back_populates="programa_rel")
    reservas: Mapped[list["Reserva"]] = relationship(back_populates="programa_rel")
    clases: Mapped[list["ClaseSalaComputo"]] = relationship(back_populates="programa_rel")


class Estudiante(db.Model):
    """Base de datos de estudiantes de UNIMINUTO."""
    __tablename__ = 'estudiantes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo_banner: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)  # ID Banner / Código estudiante
    documento: Mapped[Optional[str]] = mapped_column(String(30), index=True, nullable=True)
    tipo_documento: Mapped[str] = mapped_column(String(10), default='CC', nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    correo: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    
    # Programa Académico
    atributo_programa: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)  # Código atributo ej: ISUM, ADM
    programa_id: Mapped[Optional[int]] = mapped_column(ForeignKey('programas_academicos.id'), nullable=True, index=True)
    programa_rel: Mapped[Optional["ProgramaAcademico"]] = relationship(back_populates="estudiantes")
    
    # Sede
    descripcion_sede: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)  # ENGATIVA PRESENCIAL, etc.
    sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes.id'), nullable=True, index=True)
    sede: Mapped[Optional["Sede"]] = relationship()

    semestre: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    jornada: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Profesor(db.Model):
    __tablename__ = 'profesores'
    cedula: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(String, nullable=False)
    correo: Mapped[str] = mapped_column(String, nullable=True)
    telefono: Mapped[str] = mapped_column(String, nullable=True)
    programa: Mapped[str] = mapped_column(String, nullable=True)
    programa_id: Mapped[Optional[int]] = mapped_column(ForeignKey('programas_academicos.id'), nullable=True, index=True)
    
    programa_rel: Mapped[Optional["ProgramaAcademico"]] = relationship(back_populates="profesores")
    reservas: Mapped[list["Reserva"]] = relationship(back_populates="profesor")
    prestamos: Mapped[list["PrestamoEquipo"]] = relationship(back_populates="profesor")

class Sede(db.Model):
    __tablename__ = 'sedes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    
    bodegas: Mapped[list["Bodega"]] = relationship(back_populates="sede", cascade="all, delete-orphan")
    reservas: Mapped[list["Reserva"]] = relationship(back_populates="sede")

class Bodega(db.Model):
    __tablename__ = 'bodegas'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    sede_id: Mapped[int] = mapped_column(ForeignKey('sedes.id'), nullable=False)
    
    sede: Mapped["Sede"] = relationship(back_populates="bodegas")
    items: Mapped[list["Inventario"]] = relationship(back_populates="bodega")

class Ubicacion(db.Model):
    __tablename__ = 'ubicaciones'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False) # e.g. "Bloque A", "Piso 5", "Sede Única"
    sede_id: Mapped[int] = mapped_column(ForeignKey('sedes.id'), nullable=False)
    
    sede: Mapped["Sede"] = relationship(backref="ubicaciones")
    recursos: Mapped[list["Recurso"]] = relationship(back_populates="ubicacion", cascade="all, delete-orphan")

class Recurso(db.Model):
    __tablename__ = 'recursos'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, index=True) # e.g. "A501"
    tipo: Mapped[str] = mapped_column(String, nullable=False, index=True) # "Salón", "Niñera", "Laboratorio"
    marca_tipo: Mapped[str] = mapped_column(String, nullable=True) # "S", "P", "LG" (opcional)
    ubicacion_id: Mapped[int] = mapped_column(ForeignKey('ubicaciones.id'), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    
    ubicacion: Mapped["Ubicacion"] = relationship(back_populates="recursos")

class CategoriaInventario(db.Model):
    __tablename__ = 'categorias_inventario'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, unique=True, nullable=False)

class Inventario(db.Model):
    __tablename__ = 'inventario'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    categoria: Mapped[str] = mapped_column(String, index=True)
    item: Mapped[str] = mapped_column(String, index=True)
    marca_modelo: Mapped[str] = mapped_column(String, nullable=True)
    serial: Mapped[str] = mapped_column(String, nullable=True)
    activo_fijo: Mapped[str] = mapped_column(String, nullable=True)
    numero_inventario: Mapped[str] = mapped_column(String, nullable=True, unique=True, index=True)
    ubicacion_permanente: Mapped[str] = mapped_column(String, nullable=True, index=True)
    estado: Mapped[str] = mapped_column(
        Enum(
            'Disponible',
            'En Préstamo',
            'En Mantenimiento',
            'En Reparación',
            'De Baja',
            name='estado_inventario_enum'
        ),
        default='Disponible',
        index=True
    )
    observaciones: Mapped[str] = mapped_column(Text, nullable=True)

    # === CAMPOS DE GESTIÓN POR CANTIDAD ===
    # Si es True, el item se gestiona por stock (cantidad) en vez de por serial/número individual
    es_por_cantidad: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cantidad_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)      # Stock total registrado
    cantidad_disponible: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Stock disponible ahora

    bodega_id: Mapped[Optional[int]] = mapped_column(ForeignKey('bodegas.id'), nullable=True)
    bodega: Mapped[Optional["Bodega"]] = relationship(back_populates="items")
    
    # Relación para contar veces prestado
    prestamos: Mapped[list["PrestamoEquipo"]] = relationship(back_populates="equipo")

    @property
    def veces_prestado(self):
        # Contamos los grupos de préstamos únicos para este item
        if not self.prestamos:
            return 0
        return len(set(p.id_grupo_prestamo for p in self.prestamos if p.id_grupo_prestamo))

    @property
    def disponible_para_prestamo(self):
        """True si el item puede ser prestado ahora mismo."""
        if self.es_por_cantidad:
            return (self.cantidad_disponible or 0) > 0
        return self.estado == 'Disponible'

class PrestamoEquipo(db.Model):
    __tablename__ = 'prestamos_equipos'
    id_prestamo: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_grupo_prestamo: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    
    cedula_profesor: Mapped[int] = mapped_column(ForeignKey('profesores.cedula'), index=True)
    profesor: Mapped["Profesor"] = relationship(back_populates="prestamos")
    
    numero_inventario_equipo: Mapped[str] = mapped_column(ForeignKey('inventario.numero_inventario'), index=True)
    equipo: Mapped["Inventario"] = relationship(back_populates="prestamos")
    
    equipo_prestado: Mapped[str] = mapped_column(String) # Denormalizado para reportes
    nombre_profesor: Mapped[str] = mapped_column(String, index=True) # Denormalizado para reportes

    # Cantidad prestada (para ítems gestionados por stock)
    cantidad_prestada: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=1)

    ubicacion_id: Mapped[Optional[int]] = mapped_column(ForeignKey('ubicaciones.id'), nullable=True)
    ubicacion_rel: Mapped[Optional["Ubicacion"]] = relationship()

    recurso_id: Mapped[Optional[int]] = mapped_column(ForeignKey('recursos.id'), nullable=True)
    recurso: Mapped[Optional["Recurso"]] = relationship()

    ubicacion: Mapped[str] = mapped_column(String, nullable=True) # Texto libre o nombre denormalizado
    fecha_prestamo: Mapped[date_type] = mapped_column(Date, index=True)
    jornada: Mapped[str] = mapped_column(String, nullable=True, index=True)
    hora_inicio: Mapped[time_type] = mapped_column(Time)
    hora_fin: Mapped[time_type] = mapped_column(Time)
    horas_academicas: Mapped[float] = mapped_column(db.Float, nullable=True)
    auxiliar_entrega: Mapped[str] = mapped_column(String)
    auxiliar_recibe: Mapped[str] = mapped_column(String, nullable=True)
    hora_devolucion_real: Mapped[time_type] = mapped_column(Time, nullable=True)
    fecha_devolucion: Mapped[date_type] = mapped_column(Date, nullable=True, index=True)
    observaciones: Mapped[str] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(Enum('Prestado', 'Devuelto', name='estado_prestamo_enum'), default='Prestado', index=True)
    sede_id: Mapped[int] = mapped_column(ForeignKey('sedes.id'), nullable=True, index=True)
    sede: Mapped["Sede"] = relationship()
    
    # Índices compuestos para consultas frecuentes
    __table_args__ = (
        Index('ix_prestamo_estado_fecha', 'estado', 'fecha_prestamo'),
        Index('ix_prestamo_profesor_fecha', 'cedula_profesor', 'fecha_prestamo'),
        Index('ix_prestamo_equipo_estado', 'equipo_prestado', 'estado'),
    )

class Reserva(db.Model):
    __tablename__ = 'reservas'
    id_reserva: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    cedula_profesor: Mapped[int] = mapped_column(ForeignKey('profesores.cedula'), index=True)
    profesor: Mapped["Profesor"] = relationship(back_populates="reservas")
    nombre_profesor: Mapped[str] = mapped_column(String, index=True) # Denormalizado para reportes

    sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes.id'), nullable=True)
    sede: Mapped[Optional["Sede"]] = relationship(back_populates="reservas")

    nrc: Mapped[str] = mapped_column(String, nullable=True)
    recurso_id: Mapped[Optional[int]] = mapped_column(ForeignKey('recursos.id'), nullable=True)
    recurso: Mapped[Optional["Recurso"]] = relationship()
    
    # Programa Académico
    programa_id: Mapped[Optional[int]] = mapped_column(ForeignKey('programas_academicos.id'), nullable=True, index=True)
    programa_rel: Mapped[Optional["ProgramaAcademico"]] = relationship(back_populates="reservas")
    programa: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    recurso_tipo: Mapped[str] = mapped_column(String, index=True)
    recurso_nombre: Mapped[str] = mapped_column(String, index=True)
    fecha: Mapped[date_type] = mapped_column(Date, index=True)
    jornada: Mapped[str] = mapped_column(String, nullable=True, index=True)
    hora_inicio: Mapped[time_type] = mapped_column(Time)
    hora_fin: Mapped[time_type] = mapped_column(Time)
    tipo_reserva: Mapped[str] = mapped_column(String, nullable=True)
    estado: Mapped[str] = mapped_column(Enum('Activa', 'Cancelada', 'Completada', name='estado_reserva_enum'), default='Activa', index=True)
    observaciones: Mapped[str] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        Index('ix_reserva_recurso_fecha_estado', 'recurso_nombre', 'fecha', 'estado'),
        Index('ix_reserva_profesor_fecha', 'cedula_profesor', 'fecha'),
        Index('ix_reserva_tipo_fecha', 'recurso_tipo', 'fecha'),
    )

class ClaseSalaComputo(db.Model):
    __tablename__ = 'clases_salas_computo'
    id_clase: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    fecha: Mapped[date_type] = mapped_column(Date, index=True, nullable=False)
    hora_inicio: Mapped[time_type] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time_type] = mapped_column(Time, nullable=False)
    
    sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes.id'), nullable=True)
    sede: Mapped[Optional["Sede"]] = relationship()
    
    recurso_id: Mapped[Optional[int]] = mapped_column(ForeignKey('recursos.id'), nullable=True)
    recurso: Mapped[Optional["Recurso"]] = relationship()
    
    salon: Mapped[str] = mapped_column(String, index=True, nullable=False)
    
    cedula_profesor: Mapped[Optional[int]] = mapped_column(ForeignKey('profesores.cedula'), nullable=True, index=True)
    profesor: Mapped[Optional["Profesor"]] = relationship()
    nombre_profesor: Mapped[str] = mapped_column(String, nullable=False)
    
    materia: Mapped[str] = mapped_column(String, nullable=False)
    asistencia: Mapped[str] = mapped_column(String, nullable=False, default='No')  # Sí / No
    horas_academicas: Mapped[float] = mapped_column(db.Float, nullable=True)
    jornada: Mapped[str] = mapped_column(String, nullable=True)
    num_estudiantes: Mapped[int] = mapped_column(Integer, nullable=True)
    programa: Mapped[str] = mapped_column(String, nullable=True)
    programa_id: Mapped[Optional[int]] = mapped_column(ForeignKey('programas_academicos.id'), nullable=True, index=True)
    programa_rel: Mapped[Optional["ProgramaAcademico"]] = relationship(back_populates="clases")
    modalidad: Mapped[str] = mapped_column(String, nullable=True) # Presencial / Distancia

    estado: Mapped[str] = mapped_column(Enum('Programada', 'Realizada', 'Cancelada', name='estado_clase_enum'), default='Programada', index=True)
    observaciones: Mapped[str] = mapped_column(Text, nullable=True)


class UserPermission(db.Model):
    __tablename__ = 'permisos_usuarios'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_documento: Mapped[str] = mapped_column(ForeignKey('auxiliares.documento'), index=True)
    modulo: Mapped[str] = mapped_column(String, index=True)  # prestamos, reservas, inventario, profesores, salas_computo, etc.
    puede_ver: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    puede_crear: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    puede_editar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    puede_eliminar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    usuario: Mapped["Auxiliar"] = relationship(backref="permisos")


class AuditLog(db.Model):
    __tablename__ = 'auditorias'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    modulo: Mapped[str] = mapped_column(String, index=True)  # prestamos, reservas, inventario, profesores, usuarios
    entidad_tipo: Mapped[str] = mapped_column(String)        # Modelo afectado
    entidad_id: Mapped[str] = mapped_column(String)          # ID de la entidad como string
    accion: Mapped[str] = mapped_column(String)              # CREAR, EDITAR, ELIMINAR, DEVOLVER, CANCELAR, etc.
    usuario_documento: Mapped[str] = mapped_column(String, index=True)
    usuario_nombre: Mapped[str] = mapped_column(String, nullable=True)
    fecha: Mapped[date_type] = mapped_column(Date, index=True)
    hora: Mapped[time_type] = mapped_column(Time, index=True)
    descripcion: Mapped[str] = mapped_column(Text, nullable=True)
    datos_antes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON serializado
    datos_despues: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # JSON serializado

class Festivo(db.Model):
    __tablename__ = 'festivos'
    fecha: Mapped[date_type] = mapped_column(Date, primary_key=True)
    descripcion: Mapped[str] = mapped_column(String)


def registrar_auditoria(
    modulo: str,
    entidad_tipo: str,
    entidad_id: str,
    accion: str,
    usuario_documento: str,
    usuario_nombre: str = "",
    descripcion: str = "",
    datos_antes=None,
    datos_despues=None,
):
    """Registra una entrada de auditoría genérica."""
    from datetime import datetime

    try:
        now = datetime.now()

        def _to_json(data):
            if data is None:
                return None
            if isinstance(data, str):
                return data
            try:
                return json.dumps(data, ensure_ascii=False)
            except Exception:
                return None

        log = AuditLog(
            modulo=modulo,
            entidad_tipo=entidad_tipo,
            entidad_id=str(entidad_id),
            accion=accion.upper(),
            usuario_documento=str(usuario_documento),
            usuario_nombre=usuario_nombre or "",
            fecha=now.date(),
            hora=now.time(),
            descripcion=descripcion or "",
            datos_antes=_to_json(datos_antes),
            datos_despues=_to_json(datos_despues),
        )
        db.session.add(log)
    except Exception as e:
        # No interrumpe la operación principal si falla la auditoría
        try:
            from flask import current_app
            current_app.logger.warning("Error al registrar auditoría: %s", e)
        except Exception:
            pass

def init_db(app):
    """Inicializa la base de datos y crea las tablas si no existen."""
    with app.app_context():
        db.create_all()

        # Migración segura de columnas nuevas en PostgreSQL
        from sqlalchemy import text
        for stmt in [
            "ALTER TABLE profesores ADD COLUMN IF NOT EXISTS programa_id INTEGER REFERENCES programas_academicos(id);",
            "ALTER TABLE reservas ADD COLUMN IF NOT EXISTS programa_id INTEGER REFERENCES programas_academicos(id);",
            "ALTER TABLE reservas ADD COLUMN IF NOT EXISTS programa VARCHAR(200);",
            "ALTER TABLE clases_salas_computo ADD COLUMN IF NOT EXISTS programa_id INTEGER REFERENCES programas_academicos(id);"
        ]:
            try:
                db.session.execute(text(stmt))
            except Exception:
                pass
        db.session.commit()

        # Poblar Sedes si la tabla está vacía
        if not Sede.query.first():
            sedes = ['PERDOMO', 'ENGATIVA SEDE PRINCIPAL']
            for s in sedes:
                db.session.add(Sede(nombre=s))
            db.session.commit()

        # Poblar Categorías si la tabla está vacía
        if not CategoriaInventario.query.first():
            from config import SystemConstants
            for cat_name in SystemConstants.CATEGORIAS_INVENTARIO:
                db.session.add(CategoriaInventario(nombre=cat_name))
            db.session.commit()

        # Poblar festivos si la tabla está vacía (una sola fuente: config)
        if not Festivo.query.first():
            from config import SystemConstants
            for f in SystemConstants.FESTIVOS_2025:
                db.session.add(Festivo(fecha=f['fecha'], descripcion=f['descripcion']))
            db.session.commit()

        # Poblar Ubicaciones y Recursos (Salones y Niñeras) si la tabla está vacía
        if not Recurso.query.first():
            from config import SystemConstants
            
            # Obtener sedes
            sede_principal = Sede.query.filter_by(nombre='ENGATIVA SEDE PRINCIPAL').first()
            sede_perdomo = Sede.query.filter_by(nombre='PERDOMO').first()
            
            if sede_principal:
                # Crear una ubicación genérica para salones si no se conoce el detalle
                # O intentar deducir del nombre del salón (e.g. A205 -> Bloque A)
                bloques = {} # nombre: objeto_ubicacion
                
                for s_nombre in SystemConstants.SALONES_PRINCIPAL:
                    bloque_letra = s_nombre[0] if s_nombre[0].isalpha() else "Genérico"
                    bloque_nombre = f"Bloque {bloque_letra}" if bloque_letra != "Genérico" else "Ubicación Principal"
                    
                    if bloque_nombre not in bloques:
                        ub = Ubicacion(nombre=bloque_nombre, sede_id=sede_principal.id)
                        db.session.add(ub)
                        db.session.flush() # Para obtener el ID
                        bloques[bloque_nombre] = ub
                    
                    marca = SystemConstants.SALON_MARCA.get(s_nombre, "")
                    recurso = Recurso(
                        nombre=s_nombre, 
                        tipo='Salón', 
                        marca_tipo=marca, 
                        ubicacion_id=bloques[bloque_nombre].id
                    )
                    db.session.add(recurso)
                
                # Niñeras en Sede Principal
                ub_nineras = Ubicacion(nombre="Área de Préstamos", sede_id=sede_principal.id)
                db.session.add(ub_nineras)
                db.session.flush()
                for n_nombre in SystemConstants.NINERAS:
                    db.session.add(Recurso(nombre=n_nombre, tipo='Niñera', ubicacion_id=ub_nineras.id))

            if sede_perdomo:
                ub_perdomo = Ubicacion(nombre="Sede Perdomo", sede_id=sede_perdomo.id)
                db.session.add(ub_perdomo)
                db.session.flush()
                
                for s_nombre in SystemConstants.SALONES_PERDOMO:
                    db.session.add(Recurso(nombre=s_nombre, tipo='Salón', ubicacion_id=ub_perdomo.id))
            
            db.session.commit()

        # Poblar Programas Académicos si la tabla está vacía
        if not ProgramaAcademico.query.first():
            from data.programas_academicos_seed import PROGRAMAS_ACADEMICOS_SEED
            for p in PROGRAMAS_ACADEMICOS_SEED:
                prog = ProgramaAcademico(
                    codigo=p['codigo'],
                    nombre=p['nombre'],
                    nivel=p.get('nivel'),
                    sub_nivel=p.get('sub_nivel'),
                    periodo=p.get('periodo'),
                    activo=True
                )
                db.session.add(prog)
            db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO COLABORADORES
# ─────────────────────────────────────────────────────────────────────────────

class Colaborador(db.Model):
    """Colaborador / auxiliar operativo con horario semanal y tareas."""
    __tablename__ = 'colaboradores'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre_completo: Mapped[str] = mapped_column(String(200), nullable=False)
    cargo: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    documento: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, unique=True)
    correo: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes.id'), nullable=True)
    total_horas_semana: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=42)
    fecha_inicio_horario: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    horario_texto: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # descripción libre
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    sede: Mapped[Optional["Sede"]] = relationship()
    horarios: Mapped[list["HorarioColaborador"]] = relationship(
        back_populates="colaborador", cascade="all, delete-orphan"
    )
    tareas: Mapped[list["TareaColaborador"]] = relationship(
        back_populates="colaborador", cascade="all, delete-orphan"
    )
    permisos: Mapped[list["PermisoColaborador"]] = relationship(
        back_populates="colaborador", cascade="all, delete-orphan"
    )

    @property
    def mapa_horarios(self) -> dict[str, "HorarioColaborador"]:
        """Retorna un diccionario {dia: HorarioColaborador} para acceso rápido."""
        return {h.dia: h for h in self.horarios}

    @property
    def horas_programadas_total(self) -> float:
        """Suma de horas_dia registradas en los horarios."""
        return sum(h.horas_dia or 0.0 for h in self.horarios)



class HorarioColaborador(db.Model):
    """Horario diario de un colaborador para un período específico."""
    __tablename__ = 'horarios_colaboradores'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    colaborador_id: Mapped[int] = mapped_column(ForeignKey('colaboradores.id', ondelete='CASCADE'), nullable=False)
    dia: Mapped[str] = mapped_column(String(20), nullable=False)  # Lunes, Martes, etc.
    jornada: Mapped[Optional[str]] = mapped_column(String(50), nullable=True) # Mañana, Tarde, Noche, etc.
    hora_entrada: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # HH:MM
    hora_salida: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)   # HH:MM
    piso_laboratorio: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    recurso_movil: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    horas_dia: Mapped[Optional[float]] = mapped_column(db.Float, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    colaborador: Mapped["Colaborador"] = relationship(back_populates="horarios")


class TareaColaborador(db.Model):
    """Tarea asignada a un colaborador."""
    __tablename__ = 'tareas_colaboradores'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    colaborador_id: Mapped[int] = mapped_column(ForeignKey('colaboradores.id', ondelete='CASCADE'), nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(String(30), nullable=False, default='pendiente')  # pendiente, en_progreso, completada
    prioridad: Mapped[str] = mapped_column(String(20), nullable=False, default='normal')  # baja, normal, alta
    fecha_asignacion: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    fecha_vencimiento: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    colaborador: Mapped["Colaborador"] = relationship(back_populates="tareas")


class PermisoColaborador(db.Model):
    """Permisos de acceso de un colaborador a módulos del sistema."""
    __tablename__ = 'permisos_colaboradores'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    colaborador_id: Mapped[int] = mapped_column(ForeignKey('colaboradores.id', ondelete='CASCADE'), nullable=False)
    modulo: Mapped[str] = mapped_column(String(60), nullable=False)
    puede_ver: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    puede_crear: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    puede_editar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    puede_eliminar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    colaborador: Mapped["Colaborador"] = relationship(back_populates="permisos")


# =========================================================================
# MODELOS PARA SALAS DE CÓMPUTO, PUESTOS, SOFTWARE Y NOVEDADES TÉCNICAS
# =========================================================================

class PuestoComputo(db.Model):
    """Puesto o equipo de cómputo individual dentro de una sala o laboratorio."""
    __tablename__ = 'puestos_computo'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recurso_id: Mapped[int] = mapped_column(ForeignKey('recursos.id', ondelete='CASCADE'), nullable=False, index=True)
    numero_puesto: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3...
    nombre_equipo: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # ej: PC-S301-01
    serial_activo: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    estado: Mapped[str] = mapped_column(String(30), default='Operativo', nullable=False, index=True)  # Operativo, Falla Leve, Fuera de Servicio, Mantenimiento
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recurso: Mapped["Recurso"] = relationship(backref="puestos")
    novedades: Mapped[list["NovedadTecnicaSala"]] = relationship(back_populates="puesto", cascade="all, delete-orphan")


class SoftwareSala(db.Model):
    """Catálogo de programas y aplicaciones instaladas en las salas."""
    __tablename__ = 'software_salas'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False, index=True)  # AutoCAD, SPSS, Python, etc.
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)      # 2024, 29.0, 3.11
    categoria: Mapped[str] = mapped_column(String(60), default='General', nullable=False)  # Diseño, Programación, Estadística, Ofimática, etc.
    licencia: Mapped[str] = mapped_column(String(60), default='Institucional', nullable=False)  # Institucional, Libre / Open Source, Gratuita, Educativa
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icono: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)       # bi-code-slash, bi-palette, bi-calculator...
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    asignaciones: Mapped[list["SoftwareAsignadoSala"]] = relationship(back_populates="software", cascade="all, delete-orphan")


class SoftwareAsignadoSala(db.Model):
    """Relación entre software y sala/recurso de cómputo."""
    __tablename__ = 'software_asignado_salas'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    software_id: Mapped[int] = mapped_column(ForeignKey('software_salas.id', ondelete='CASCADE'), nullable=False, index=True)
    recurso_id: Mapped[int] = mapped_column(ForeignKey('recursos.id', ondelete='CASCADE'), nullable=False, index=True)
    observaciones: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    software: Mapped["SoftwareSala"] = relationship(back_populates="asignaciones")
    recurso: Mapped["Recurso"] = relationship(backref="software_asignado")


class NovedadTecnicaSala(db.Model):
    """Registro de novedades, fallas técnicas o mantenimientos en salas de cómputo."""
    __tablename__ = 'novedades_tecnicas_salas'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recurso_id: Mapped[int] = mapped_column(ForeignKey('recursos.id', ondelete='CASCADE'), nullable=False, index=True)
    puesto_id: Mapped[Optional[int]] = mapped_column(ForeignKey('puestos_computo.id', ondelete='SET NULL'), nullable=True, index=True)
    
    tipo_falla: Mapped[str] = mapped_column(String(60), nullable=False)  # Hardware, Software, Red, Periféricos, Proyector/Audio, Eléctrico, Otro
    prioridad: Mapped[str] = mapped_column(String(20), default='Media', nullable=False)  # Baja, Media, Alta, Crítica
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(30), default='Pendiente', nullable=False, index=True)  # Pendiente, En Revisión, Solucionada
    
    auxiliar_reporta: Mapped[str] = mapped_column(String(150), nullable=False)
    fecha_reporte: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    hora_reporte: Mapped[time_type] = mapped_column(Time, nullable=False)
    
    auxiliar_soluciona: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    fecha_solucion: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)
    hora_solucion: Mapped[Optional[time_type]] = mapped_column(Time, nullable=True)
    solucion_aplicada: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recurso: Mapped["Recurso"] = relationship(backref="novedades_tecnicas")
    puesto: Mapped[Optional["PuestoComputo"]] = relationship(back_populates="novedades")


# =========================================================================
# MODELO PARA MANTENIMIENTO Y HOJA DE VIDA DE EQUIPOS DE INVENTARIO
# =========================================================================

class MantenimientoInventario(db.Model):
    """Historial de mantenimientos preventivos y correctivos de equipos."""
    __tablename__ = 'mantenimientos_inventario'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inventario_id: Mapped[int] = mapped_column(ForeignKey('inventario.id', ondelete='CASCADE'), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(50), default='Correctivo', nullable=False)  # Preventivo, Correctivo, Calibración, Garantía
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    proveedor_tecnico: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)  # Técnico UNIMINUTO o Proveedor Externo
    costo: Mapped[Optional[float]] = mapped_column(db.Float, nullable=True)
    
    fecha_envio: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    fecha_estimada_retorno: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)
    fecha_retorno_real: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)
    
    estado: Mapped[str] = mapped_column(String(30), default='En Proceso', nullable=False, index=True)  # En Proceso, Finalizado, No Reparable
    diagnostico_solucion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auxiliar_responsable: Mapped[str] = mapped_column(String(150), nullable=False)

    equipo: Mapped["Inventario"] = relationship(backref="mantenimientos")


# =========================================================================
# MODELO PARA PRÁCTICA LIBRE ESTUDIANTIL EN SALAS / LABORATORIOS
# =========================================================================

class PracticaLibre(db.Model):
    """Registro y control de acceso de estudiantes para práctica libre en salas de cómputo."""
    __tablename__ = 'practicas_libres'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    estudiante_id: Mapped[Optional[int]] = mapped_column(ForeignKey('estudiantes.id', ondelete='SET NULL'), nullable=True, index=True)
    codigo_banner: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    nombre_estudiante: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    programa_estudiante: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sedes.id'), nullable=True, index=True)
    sede_nombre: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    recurso_id: Mapped[Optional[int]] = mapped_column(ForeignKey('recursos.id'), nullable=True, index=True)
    salon: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    numero_puesto: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    fecha: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    hora_inicio: Mapped[time_type] = mapped_column(Time, nullable=False)
    hora_fin_estimada: Mapped[Optional[time_type]] = mapped_column(Time, nullable=True)
    hora_salida_real: Mapped[Optional[time_type]] = mapped_column(Time, nullable=True)
    
    estado: Mapped[str] = mapped_column(
        Enum('En Curso', 'Finalizada', 'Cancelada', name='estado_practica_libre_enum'),
        default='En Curso',
        nullable=False,
        index=True
    )
    auxiliar_registro: Mapped[str] = mapped_column(String(150), nullable=False)
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    estudiante: Mapped[Optional["Estudiante"]] = relationship()
    recurso: Mapped[Optional["Recurso"]] = relationship()
    sede: Mapped[Optional["Sede"]] = relationship()


