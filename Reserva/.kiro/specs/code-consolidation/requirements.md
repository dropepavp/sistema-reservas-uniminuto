# Documento de Requerimientos

## Introducción

Este feature consolida el código duplicado existente en la aplicación Flask de gestión de préstamos de equipos, reservas de salones y niñeras de la universidad. Existen dos pares de archivos duplicados: `blueprints/prestamos.py` / `blueprints/prestamos_mejorado.py` y `app.py` / `app_improved.py`. El objetivo es unificar cada par en un único archivo que combine las funcionalidades más completas de ambas versiones, sin romper la aplicación ni las plantillas existentes.

## Glosario

- **Sistema**: La aplicación Flask de gestión de préstamos y reservas universitarias.
- **Blueprint_Prestamos**: El módulo `blueprints/prestamos.py` que gestiona todas las rutas del blueprint `prestamos_bp`.
- **App_Principal**: El archivo `app.py` que inicializa y ejecuta la aplicación Flask.
- **DataValidator**: Clase de validación definida en `validators.py` que expone métodos como `validate_string_field`, `validate_time`, `validate_time_range` y `validate_date`.
- **registrar_auditoria**: Función importada desde `database` que registra acciones de auditoría con los campos `usuario_documento` y `usuario_nombre`.
- **AlertService**: Servicio importado desde `services.alert_service` que verifica préstamos vencidos y reservas próximas.
- **PrestamoService**: Servicio importado desde `services.prestamo_service` que encapsula la lógica de negocio de préstamos.
- **obtener_disponibles**: Función auxiliar que centraliza el conteo de equipos disponibles por tipo a partir de una query base de inventario.
- **inject_module_access**: Context processor que consulta `UserPermission` en la base de datos para exponer permisos de módulo a las plantillas.
- **create_app**: Función de fábrica (factory function) que crea y configura la instancia de la aplicación Flask.
- **id_grupo_prestamo**: Identificador que agrupa todos los registros de un mismo préstamo dividido por jornadas.

---

## Requerimientos

### Requerimiento 1: Consolidar el Blueprint de Préstamos

**User Story:** Como desarrollador, quiero un único archivo `blueprints/prestamos.py` que combine las rutas completas de la versión activa con las mejoras de validación y auditoría de la versión mejorada, para eliminar la duplicación y tener un único punto de mantenimiento.

#### Criterios de Aceptación

1. THE Blueprint_Prestamos SHALL importar los decoradores `login_required` y `permiso_requerido` exclusivamente desde el módulo `auth`.
2. THE Blueprint_Prestamos SHALL definir la función auxiliar `extraer_numero_corto` localmente, sin importarla desde `services`.
3. THE Blueprint_Prestamos SHALL incluir la función auxiliar `obtener_disponibles(query_inv)` que centraliza el conteo de equipos disponibles por tipo (portátiles, cargadores, hdmi, controles, teclados).
4. WHEN la función `agrupar_prestamos` procesa una lista de préstamos, THE Blueprint_Prestamos SHALL incluir el campo `id_prestamo` dentro de cada objeto `equipo_info` para permitir la edición individual de ítems.
5. THE Blueprint_Prestamos SHALL exponer las rutas: `GET /prestamos/`, `POST /prestamos/nuevo`, `POST /prestamos/devolver/<id>`, `POST /prestamos/renovar/<id_grupo>`, `GET /prestamos/detalles/<id_grupo>`, `GET|PUT /prestamos/editar/<id_prestamo>`, `GET /prestamos/buscar`, `GET /prestamos/exportar/<formato>`, `GET /prestamos/historial`, `GET /prestamos/historial/exportar` y `GET /prestamos/buscar-equipos`.
6. WHEN la ruta `PUT /prestamos/editar/<id_prestamo>` recibe datos, THE Blueprint_Prestamos SHALL validar la ubicación, las observaciones, la hora de inicio y la hora de fin usando `DataValidator` antes de persistir los cambios.
7. WHEN la ruta `PUT /prestamos/editar/<id_prestamo>` recibe el campo `items`, THE Blueprint_Prestamos SHALL actualizar el `numero_inventario_equipo` de cada ítem individual identificado por `id_prestamo`.
8. WHEN la ruta `PUT /prestamos/editar/<id_prestamo>` actualiza un grupo, THE Blueprint_Prestamos SHALL aplicar los cambios de `ubicacion`, `hora_inicio`, `hora_fin` y `observaciones` a todos los registros del grupo.
9. WHEN cualquier ruta llama a `registrar_auditoria`, THE Blueprint_Prestamos SHALL incluir los parámetros `usuario_documento=session.get('usuario', '')` y `usuario_nombre=session.get('nombre_completo', '')` en todas las llamadas.
10. IF una operación de base de datos falla, THEN THE Blueprint_Prestamos SHALL retornar un mensaje de error amigable al usuario sin exponer detalles técnicos internos.

---

### Requerimiento 2: Consolidar la Aplicación Principal

**User Story:** Como desarrollador, quiero que `app.py` use el patrón factory function `create_app()`, tenga un context processor robusto basado en base de datos y un `index()` con soporte de sede, para eliminar la duplicación con `app_improved.py` y mejorar la arquitectura.

#### Criterios de Aceptación

1. THE App_Principal SHALL definir una función `create_app(config_name=None)` que inicialice la aplicación Flask, configure las extensiones y registre todos los blueprints.
2. WHEN `create_app` es invocada, THE App_Principal SHALL registrar los blueprints: `auth_bp`, `estadisticas_bp`, `api_bp`, `prestamos_bp`, `reservas_bp`, `inventario_bp`, `admin_bp`, `profesores_bp`, `bitacora_bp` y `salas_computo_bp`.
3. THE App_Principal SHALL definir el context processor `inject_module_access` que consulta `UserPermission` en la base de datos para determinar los módulos accesibles por el usuario autenticado.
4. WHEN el usuario autenticado tiene rol `admin` o `superadmin`, THE App_Principal SHALL retornar acceso `True` a todos los módulos sin consultar la base de datos.
5. WHEN el usuario no está autenticado, THE App_Principal SHALL retornar acceso `False` a todos los módulos sin consultar la base de datos.
6. WHEN la ruta `GET /` es accedida por un usuario con `sede_id` en sesión y rol distinto de `admin`/`superadmin`, THE App_Principal SHALL filtrar las estadísticas de préstamos y reservas por ese `sede_id`.
7. WHEN la ruta `GET /` detecta préstamos vencidos mediante `AlertService`, THE App_Principal SHALL mostrar un mensaje flash de advertencia con el conteo de préstamos vencidos.
8. WHEN la ruta `GET /` detecta reservas próximas mediante `AlertService`, THE App_Principal SHALL mostrar un mensaje flash informativo con el conteo de reservas en los próximos 2 días.
9. IF `AlertService` lanza una excepción, THEN THE App_Principal SHALL registrar la advertencia en el log y continuar renderizando el dashboard sin interrumpir la respuesta.
10. WHEN `app.py` es ejecutado directamente con `python app.py`, THE App_Principal SHALL crear la aplicación mediante `create_app()` e iniciar el servidor en el puerto 5000.

---

### Requerimiento 3: Eliminar Rutas Duplicadas de app.py

**User Story:** Como desarrollador, quiero eliminar de `app.py` las rutas que ya están implementadas en los blueprints, para evitar conflictos de registro y mantener una única fuente de verdad por funcionalidad.

#### Criterios de Aceptación

1. THE App_Principal SHALL NOT definir las rutas `/prestamos_equipos`, `/nuevo_prestamo`, `/devolver_prestamo/<id>` ni `/prestamos/exportar/<formato>` dado que estas rutas ya existen en `Blueprint_Prestamos`.
2. THE App_Principal SHALL NOT definir las funciones `calcular_jornada_desde_hora`, `calcular_jornadas_completas`, `obtener_jornadas_grupo_prestamo` ni `calcular_horas_academicas` dado que estas ya están implementadas en `services/prestamo_service.py`.
3. WHEN la aplicación inicia, THE App_Principal SHALL registrar cada ruta exactamente una vez, sin duplicados entre `app.py` y los blueprints registrados.
4. IF una plantilla existente referencia una ruta eliminada de `app.py`, THEN THE App_Principal SHALL garantizar que la ruta equivalente en el blueprint correspondiente responde con los mismos nombres de variables de contexto.

---

### Requerimiento 4: Limpieza de Archivos Obsoletos

**User Story:** Como desarrollador, quiero eliminar los archivos duplicados una vez completada la consolidación, para mantener el repositorio limpio y evitar confusión sobre cuál versión es la activa.

#### Criterios de Aceptación

1. WHEN la consolidación de `blueprints/prestamos.py` esté completa y verificada, THE Sistema SHALL eliminar el archivo `blueprints/prestamos_mejorado.py`.
2. WHEN la consolidación de `app.py` esté completa y verificada, THE Sistema SHALL eliminar el archivo `app_improved.py`.
3. WHILE los archivos obsoletos existan en el repositorio, THE Sistema SHALL mantener la aplicación funcional usando únicamente los archivos consolidados (`app.py` y `blueprints/prestamos.py`).
4. WHEN los archivos obsoletos sean eliminados, THE Sistema SHALL seguir iniciando correctamente con `python app.py` desde el directorio `Reserva/`.

---

### Requerimiento 5: Preservar Compatibilidad con Plantillas

**User Story:** Como desarrollador, quiero que las plantillas HTML existentes sigan funcionando sin modificaciones después de la consolidación, para no introducir regresiones visuales ni errores de renderizado.

#### Criterios de Aceptación

1. WHEN la ruta `GET /prestamos/` renderiza `prestamos_equipos_mejorado.html`, THE Blueprint_Prestamos SHALL pasar las variables: `prestamos_activos`, `prestamos_devueltos`, `prestamos_vencidos`, `total_activos`, `total_devueltos`, `total_vencidos`, `total_realizados`, `disponibles` y `sedes`.
2. WHEN la ruta `GET /prestamos/historial` renderiza `prestamos_historial.html`, THE Blueprint_Prestamos SHALL pasar la variable `historial` con la lista de préstamos históricos.
3. WHEN la ruta `GET /` renderiza `index.html`, THE App_Principal SHALL pasar las variables `stats`, `top_equipo` y `top_profesor` con la misma estructura que la versión actual.
4. THE App_Principal SHALL exponer la variable `mod_access` en el contexto de todas las plantillas mediante el context processor `inject_module_access`.
5. IF una ruta falla al cargar datos, THEN THE Sistema SHALL renderizar la plantilla correspondiente con valores vacíos o nulos en lugar de retornar un error HTTP 500.
