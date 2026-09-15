# Plan de Implementación: Consolidación de Código

## Visión General

Fusionar los pares de archivos duplicados (`app.py`/`app_improved.py` y `blueprints/prestamos.py`/`blueprints/prestamos_mejorado.py`) en archivos únicos que combinen lo mejor de ambas versiones, sin romper plantillas ni funcionalidad existente.

## Tareas

- [x] 1. Consolidar `blueprints/prestamos.py`
  - [x] 1.1 Agregar función `extraer_numero_corto` localmente y función `obtener_disponibles`
    - Definir `extraer_numero_corto(numero_inventario)` directamente en el archivo (sin importar desde `services`)
    - Definir `obtener_disponibles(query_inv)` que retorna dict con conteos por tipo: `portatiles`, `cargadores`, `hdmi`, `controles`, `teclados`
    - Cada conteo filtra `estado == 'Disponible'` con `ilike` por nombre de ítem
    - Envolver en `try/except` que retorna ceros ante fallo de DB
    - _Requerimientos: 1.2, 1.3_

  - [ ]* 1.2 Escribir prueba de propiedad para `obtener_disponibles`
    - **Propiedad 1: obtener_disponibles cuenta correctamente por tipo**
    - **Valida: Requerimiento 1.3**
    - Usar `hypothesis` con `@given` y `@settings(max_examples=100)`
    - Generar listas de inventarios con estados y nombres variados
    - Verificar que cada conteo coincide exactamente con los ítems `Disponible` de esa categoría
    - Incluir comentario: `# Feature: code-consolidation, Property 1`

  - [x] 1.3 Actualizar `agrupar_prestamos` para incluir `id_prestamo` en `equipo_info`
    - Agregar campo `'id_prestamo': prestamo.id_prestamo` dentro del dict `equipo_info`
    - Verificar que no se agregan duplicados por número de inventario
    - _Requerimientos: 1.4_

  - [ ]* 1.4 Escribir prueba de propiedad para `agrupar_prestamos`
    - **Propiedad 2: agrupar_prestamos incluye id_prestamo en cada equipo_info**
    - **Valida: Requerimiento 1.4**
    - Generar listas de objetos `PrestamoEquipo` con `hypothesis`
    - Verificar que cada elemento en `grupo['equipos'][categoria]` contiene `'id_prestamo'`
    - Verificar que el valor coincide con el `id_prestamo` del registro original
    - Incluir comentario: `# Feature: code-consolidation, Property 2`

  - [x] 1.5 Actualizar ruta `GET /prestamos/` para usar `obtener_disponibles`
    - Reemplazar los 5 conteos individuales por una llamada a `obtener_disponibles(query_inv)`
    - Asegurar que se pasan todas las variables requeridas por la plantilla: `prestamos_activos`, `prestamos_devueltos`, `prestamos_vencidos`, `total_activos`, `total_devueltos`, `total_vencidos`, `total_realizados`, `disponibles`, `sedes`
    - Mantener el bloque `except` que renderiza con valores vacíos ante fallo de DB
    - _Requerimientos: 1.3, 5.1, 5.5_

  - [x] 1.6 Actualizar `PUT /prestamos/editar/<id_prestamo>` con validación `DataValidator` y actualización masiva de grupo
    - Reemplazar validaciones manuales por `DataValidator.validate_string_field`, `DataValidator.validate_time`, `DataValidator.validate_time_range`
    - Buscar todos los registros del grupo (`id_grupo_prestamo`) en lugar de solo el registro individual
    - Aplicar cambios de `ubicacion`, `hora_inicio`, `hora_fin`, `observaciones` a todos los registros del grupo
    - Procesar campo `items` del body para actualizar `numero_inventario_equipo` por `id_prestamo`
    - Incluir `equipos` agrupados por tipo en la respuesta `GET`
    - _Requerimientos: 1.6, 1.7, 1.8_

  - [ ]* 1.7 Escribir prueba de propiedad para validación en `editar_prestamo`
    - **Propiedad 3: Validación rechaza datos inválidos en editar_prestamo**
    - **Valida: Requerimientos 1.6, 1.10**
    - Generar combinaciones de datos inválidos: ubicación >100 chars, observaciones >500 chars, hora con formato incorrecto, hora_fin anterior a hora_inicio
    - Verificar que la respuesta es HTTP 400 con campo `message`
    - Verificar que `message` no contiene `'Traceback'` ni `'Exception'`
    - Incluir comentario: `# Feature: code-consolidation, Property 3`

  - [ ]* 1.8 Escribir prueba de propiedad para actualización masiva del grupo
    - **Propiedad 4: Actualización masiva aplica cambios a todos los registros del grupo**
    - **Valida: Requerimiento 1.8**
    - Generar grupos de 1 a 5 registros con el mismo `id_grupo_prestamo`
    - Ejecutar `PUT /prestamos/editar/<id>` con datos válidos
    - Verificar que todos los registros del grupo tienen los mismos valores de `ubicacion`, `hora_inicio`, `hora_fin`
    - Incluir comentario: `# Feature: code-consolidation, Property 4`

  - [x] 1.9 Actualizar todas las llamadas a `registrar_auditoria` para incluir `usuario_documento` y `usuario_nombre`
    - En `nuevo_prestamo`, `devolver_prestamo`, `renovar_prestamo`, `editar_prestamo`
    - Agregar `usuario_documento=session.get('usuario', '')` y `usuario_nombre=session.get('nombre_completo', '')` a cada llamada
    - _Requerimientos: 1.9_

- [x] 2. Punto de control — Blueprint de préstamos
  - Asegurar que todas las pruebas del blueprint pasan. Consultar al usuario si hay dudas.

- [x] 3. Consolidar `app.py` con factory function y context processor mejorado
  - [x] 3.1 Refactorizar `app.py` para usar `create_app(config_name=None)`
    - Mover toda la inicialización de extensiones (`db`, `csrf`, `limiter`, `socketio`) dentro de `create_app`
    - Registrar los 10 blueprints dentro de `create_app`: `auth_bp`, `estadisticas_bp`, `api_bp`, `prestamos_bp`, `reservas_bp`, `inventario_bp`, `admin_bp`, `profesores_bp`, `bitacora_bp`, `salas_computo_bp`
    - Registrar el context processor `inject_module_access` dentro de `create_app`
    - Registrar la ruta `GET /` (`index`) dentro de `create_app`
    - Agregar bloque `if __name__ == '__main__': app = create_app(); socketio.run(app, ...)`
    - _Requerimientos: 2.1, 2.2, 2.10_

  - [x] 3.2 Implementar `inject_module_access` con lógica de tres ramas basada en DB
    - Rama 1: si `rol` es `admin` o `superadmin` → retornar todos los módulos en `True` sin consultar DB
    - Rama 2: si `usuario` no está en sesión → retornar todos los módulos en `False` sin consultar DB
    - Rama 3: usuario normal → consultar `UserPermission` y construir dict de acceso
    - Módulos cubiertos: `prestamos`, `reservas`, `inventario`, `profesores`, `estadisticas`, `bitacora`, `salas_computo`
    - Envolver en `try/except` que retorna todos en `False` como fallback seguro
    - _Requerimientos: 2.3, 2.4, 2.5_

  - [ ]* 3.3 Escribir prueba de propiedad para `inject_module_access`
    - **Propiedad 5: inject_module_access retorna permisos correctos según rol**
    - **Valida: Requerimientos 2.3, 2.4, 2.5**
    - Generar roles con `st.sampled_from(['admin', 'superadmin', 'auxiliar', None])`
    - Verificar que admins tienen todos en `True`, no autenticados todos en `False`
    - Incluir comentario: `# Feature: code-consolidation, Property 5`

  - [x] 3.4 Actualizar ruta `GET /` con filtro por `sede_id` y llamadas a `AlertService`
    - Aplicar filtro `sede_id` en queries de préstamos y reservas cuando el rol no es `admin`/`superadmin`
    - Llamar `AlertService.check_overdue_prestamos` y mostrar flash de advertencia si hay vencidos
    - Llamar `AlertService.check_upcoming_reservas(days=2)` y mostrar flash informativo si hay próximas
    - Envolver ambas llamadas en `try/except` que solo registra en log si falla (no interrumpe el dashboard)
    - _Requerimientos: 2.6, 2.7, 2.8, 2.9_

  - [ ]* 3.5 Escribir prueba de propiedad para resiliencia de `AlertService`
    - **Propiedad 7: AlertService no interrumpe el dashboard**
    - **Valida: Requerimiento 2.9**
    - Usar `mocker.patch` para que `AlertService.check_overdue_prestamos` lance excepciones arbitrarias
    - Verificar que `GET /` retorna HTTP 200 con el dashboard renderizado
    - Incluir comentario: `# Feature: code-consolidation, Property 7`

  - [ ]* 3.6 Escribir prueba de propiedad para filtro por sede en el dashboard
    - **Propiedad 6: Filtro por sede en el dashboard**
    - **Valida: Requerimiento 2.6**
    - Crear registros de préstamos en dos sedes distintas
    - Autenticar como usuario con `sede_id` específico y rol no admin
    - Verificar que las estadísticas solo incluyen registros de esa sede
    - Incluir comentario: `# Feature: code-consolidation, Property 6`

- [x] 4. Eliminar rutas duplicadas de `app.py`
  - Eliminar las rutas `/prestamos_equipos`, `/nuevo_prestamo`, `/devolver_prestamo/<id>`, `/prestamos/exportar/<formato>` de `app.py`
  - Eliminar las funciones `calcular_jornada_desde_hora`, `calcular_jornadas_completas`, `obtener_jornadas_grupo_prestamo`, `calcular_horas_academicas` de `app.py` (ya están en `services/prestamo_service.py`)
  - Eliminar la función `generar_pdf_tabla` si no es usada por ningún blueprint activo
  - _Requerimientos: 3.1, 3.2, 3.3_

  - [ ]* 4.1 Escribir prueba unitaria para verificar ausencia de rutas duplicadas
    - **Propiedad 8: Sin rutas duplicadas en el mapa de URLs**
    - **Valida: Requerimientos 3.1, 3.3**
    - Crear instancia con `create_app()` y verificar `app.url_map`
    - Verificar que `/prestamos_equipos`, `/nuevo_prestamo`, `/devolver_prestamo/<id>` no existen como rutas directas de `app`
    - Verificar que los 10 blueprints están registrados exactamente una vez
    - Incluir comentario: `# Feature: code-consolidation, Property 8`

- [x] 5. Punto de control — app.py consolidado
  - Asegurar que todas las pruebas de `app.py` pasan. Consultar al usuario si hay dudas.

- [x] 6. Verificar compatibilidad con plantillas
  - [x] 6.1 Verificar variables de contexto en rutas principales
    - Confirmar que `GET /prestamos/` pasa: `prestamos_activos`, `prestamos_devueltos`, `prestamos_vencidos`, `total_activos`, `total_devueltos`, `total_vencidos`, `total_realizados`, `disponibles`, `sedes`
    - Confirmar que `GET /prestamos/historial` pasa: `historial`
    - Confirmar que `GET /` pasa: `stats`, `top_equipo`, `top_profesor`
    - Confirmar que `mod_access` está disponible en todas las plantillas vía context processor
    - _Requerimientos: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 6.2 Escribir prueba de propiedad para variables de contexto de plantillas
    - **Propiedad 9: Variables de contexto completas en plantillas de préstamos**
    - **Valida: Requerimientos 5.1, 5.2, 5.3**
    - Para cada ruta principal, verificar que el contexto de la plantilla contiene todas las variables requeridas
    - Incluir comentario: `# Feature: code-consolidation, Property 9`

  - [ ]* 6.3 Escribir prueba de propiedad para resiliencia ante fallos de DB
    - **Propiedad 10: Resiliencia ante fallos de DB — valores vacíos en lugar de HTTP 500**
    - **Valida: Requerimientos 1.10, 5.5**
    - Usar `mocker.patch` para simular fallo de DB en `db.session.query`
    - Verificar que `GET /`, `GET /prestamos/` y `GET /prestamos/historial` retornan HTTP 200
    - Incluir comentario: `# Feature: code-consolidation, Property 10`

- [x] 7. Eliminar archivos obsoletos
  - Eliminar `Reserva/blueprints/prestamos_mejorado.py` una vez verificada la consolidación de `blueprints/prestamos.py`
  - Eliminar `Reserva/app_improved.py` una vez verificada la consolidación de `app.py`
  - _Requerimientos: 4.1, 4.2_

- [x] 8. Punto de control final — Verificar que todo pasa
  - Asegurar que todas las pruebas pasan y la aplicación inicia correctamente con `python app.py`. Consultar al usuario si hay dudas.

## Notas

- Las tareas marcadas con `*` son opcionales y pueden omitirse para un MVP más rápido
- Cada tarea referencia requerimientos específicos para trazabilidad
- Los puntos de control garantizan validación incremental antes de continuar
- Las pruebas de propiedades usan `hypothesis` con `@settings(max_examples=100)`
- El orden de las tareas es importante: consolidar el blueprint antes que `app.py` para evitar conflictos de importación
