# Plan de Implementación: sede-turno-selector

## Visión General

Implementar la selección de sede por turno: nueva tabla `auxiliar_sedes`, selector post-login, cambio de sede desde el navbar, filtrado de datos por sede activa y gestión de sedes desde el panel de administración.

## Tareas

- [x] 1. Crear modelo `AuxiliarSede` y actualizar `Auxiliar` en `database.py`
  - Agregar clase `AuxiliarSede` con PK compuesta `(usuario_documento, sede_id)` y `ondelete='CASCADE'`
  - Agregar relación `sedes_asignadas` en `Auxiliar` con `cascade="all, delete-orphan"`
  - Conservar el campo `sede_id` existente en `Auxiliar` sin modificarlo
  - _Requisitos: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.1 Test de propiedad: unicidad en `auxiliar_sedes`
    - **Propiedad 1: Unicidad en auxiliar_sedes**
    - Generar pares `(usuario_documento, sede_id)` aleatorios e intentar insertar duplicados; verificar que la BD rechaza el segundo insert sin alterar el estado existente
    - **Valida: Requisito 1.2**
    - `# Feature: sede-turno-selector, Property 1: Unicidad en auxiliar_sedes`

  - [x] 1.2 Test de propiedad: eliminación en cascada
    - **Propiedad 2: Eliminación en cascada**
    - Para cualquier auxiliar con N sedes en `auxiliar_sedes`, al eliminar el auxiliar el conteo de registros para ese documento debe ser 0
    - **Valida: Requisito 1.3**
    - `# Feature: sede-turno-selector, Property 2: Eliminación en cascada`

- [x] 2. Agregar decorador `sede_requerida` en `auth.py`
  - Implementar `sede_requerida` que verifique `session['sede_id']` no sea `None`; si lo es, redirigir a `/seleccionar-sede`
  - _Requisitos: 2.6, 4.3_

  - [x] 2.1 Test de propiedad: rutas protegidas sin sede activa redirigen al selector
    - **Propiedad 7: Rutas protegidas sin sede activa redirigen al selector**
    - Para cualquier ruta decorada con `@sede_requerida`, si `session['sede_id']` es `None`, la respuesta debe ser redirect a `/seleccionar-sede`
    - **Valida: Requisitos 2.6, 4.3**
    - `# Feature: sede-turno-selector, Property 7: Rutas protegidas sin sede activa redirigen al selector`

- [x] 3. Crear función auxiliar `obtener_sedes_usuario` y blueprint `sedes_bp`
  - Crear `blueprints/sedes.py` con `sedes_bp`
  - Implementar `obtener_sedes_usuario(documento, rol)`: admin/superadmin → todas las sedes; auxiliar → sedes en `auxiliar_sedes`
  - Implementar `GET /seleccionar-sede`: renderiza `seleccionar_sede.html` con la lista de sedes del usuario
  - Implementar `POST /seleccionar-sede`: valida que `sede_id` pertenezca a las sedes autorizadas, establece `session['sede_id']` y redirige al dashboard; devuelve 403 si no autorizado
  - Implementar `POST /cambiar-sede`: misma validación, actualiza solo `session['sede_id']` sin tocar el resto de la sesión, redirige al dashboard
  - Registrar `sedes_bp` en `app.py`
  - _Requisitos: 2.1, 2.2, 2.3, 2.5, 3.2, 3.3, 6.1, 6.2, 6.3_

  - [x] 3.1 Test de propiedad: redirección post-login según cantidad de sedes
    - **Propiedad 3: Redirección post-login según cantidad de sedes**
    - Auxiliar con >1 sede → redirect a `/seleccionar-sede` con `session['sede_id'] = None`; auxiliar con 1 sede → `session['sede_id']` establecido y redirect al dashboard
    - **Valida: Requisitos 2.1, 2.2**
    - `# Feature: sede-turno-selector, Property 3: Redirección post-login según cantidad de sedes`

  - [x] 3.2 Test de propiedad: admin ve todas las sedes en el selector
    - **Propiedad 4: Admin ve todas las sedes en el selector**
    - Para cualquier usuario con rol `admin` o `superadmin`, `obtener_sedes_usuario()` debe retornar el conjunto completo de sedes en la tabla `sedes`
    - **Valida: Requisito 2.3**
    - `# Feature: sede-turno-selector, Property 4: Admin ve todas las sedes en el selector`

  - [x] 3.3 Test de propiedad: selección y cambio de sede actualizan `session['sede_id']`
    - **Propiedad 6: Selección y cambio de sede actualizan session['sede_id']**
    - Para cualquier `sede_id` autorizado, después de POST exitoso a `/seleccionar-sede` o `/cambiar-sede`, `session['sede_id']` debe ser igual al `sede_id` enviado
    - **Valida: Requisitos 2.5, 3.2, 3.3**
    - `# Feature: sede-turno-selector, Property 6: Selección y cambio de sede actualizan session['sede_id']`

  - [x] 3.4 Test de propiedad: `sede_id` no autorizado devuelve HTTP 403
    - **Propiedad 16: sede_id no autorizado devuelve HTTP 403**
    - Para cualquier `sede_id` que no pertenezca a las sedes autorizadas del usuario, POST a `/seleccionar-sede` o `/cambiar-sede` debe retornar 403 sin modificar `session['sede_id']`
    - **Valida: Requisitos 6.2, 6.3**
    - `# Feature: sede-turno-selector, Property 16: sede_id no autorizado devuelve HTTP 403`

  - [x] 3.5 Test de propiedad: cambio de sede preserva el resto de la sesión
    - **Propiedad 15: Cambio de sede preserva el resto de la sesión**
    - Para cualquier cambio de `session['sede_id']`, los valores de `session['usuario']`, `session['rol']` y `session['mod_access']` deben permanecer iguales antes y después
    - **Valida: Requisito 6.1**
    - `# Feature: sede-turno-selector, Property 15: Cambio de sede preserva el resto de la sesión`

- [x] 4. Crear plantilla `templates/seleccionar_sede.html`
  - Renderizar lista de sedes disponibles como opciones seleccionables (formulario POST a `/seleccionar-sede`)
  - Mostrar el nombre de cada sede
  - _Requisitos: 2.4_

  - [x] 4.1 Test de propiedad: selector muestra nombres de todas las sedes disponibles
    - **Propiedad 5: Selector muestra nombres de todas las sedes disponibles**
    - Para cualquier lista de sedes autorizadas, el HTML renderizado de `seleccionar_sede.html` debe contener el nombre de cada sede de esa lista
    - **Valida: Requisito 2.4**
    - `# Feature: sede-turno-selector, Property 5: Selector muestra nombres de todas las sedes disponibles`

- [x] 5. Actualizar `blueprints/auth.py` para lógica post-login con sedes
  - Después de autenticar, llamar a `obtener_sedes_usuario(doc, rol)`
  - Si 0 sedes (auxiliar sin asignación): flash de advertencia y no permitir acceso
  - Si exactamente 1 sede: establecer `session['sede_id']` y redirigir al dashboard
  - Si >1 sede o admin/superadmin: establecer `session['sede_id'] = None` y redirigir a `/seleccionar-sede`
  - _Requisitos: 2.1, 2.2, 2.3_

- [x] 6. Actualizar `templates/components/navbar.html` con control de cambio de sede
  - Si el usuario tiene >1 sede autorizada o es admin/superadmin: mostrar selector de sede (formulario POST a `/cambiar-sede`)
  - Si el usuario tiene exactamente 1 sede: mostrar solo el nombre de la sede sin control de cambio
  - Indicar visualmente la sede activa actual (`session['sede_id']`)
  - _Requisitos: 3.1, 3.4, 3.5_

  - [x] 6.1 Test de propiedad: navbar muestra control de cambio según cantidad de sedes
    - **Propiedad 8: Navbar muestra control de cambio según cantidad de sedes**
    - Para usuario con >1 sede o admin/superadmin, el HTML del navbar debe contener el control de cambio; para usuario con 1 sede, ese control no debe aparecer
    - **Valida: Requisitos 3.1, 3.5**
    - `# Feature: sede-turno-selector, Property 8: Navbar muestra control de cambio según cantidad de sedes`

  - [x] 6.2 Test de propiedad: navbar indica la sede activa
    - **Propiedad 9: Navbar indica la sede activa**
    - Para cualquier `session['sede_id']` establecido, el HTML del navbar debe contener el nombre de la sede correspondiente
    - **Valida: Requisito 3.4**
    - `# Feature: sede-turno-selector, Property 9: Navbar indica la sede activa`

- [x] 7. Checkpoint — Verificar flujo de login y selección de sede
  - Asegurarse de que todos los tests pasen hasta este punto. Consultar al usuario si surgen dudas.

- [x] 8. Aplicar filtros por `sede_id` en módulos funcionales
  - En `blueprints/prestamos.py`: filtrar listados y consultas por `session['sede_id']`; asignar `sede_id` al crear nuevos préstamos
  - En `blueprints/reservas.py`: ídem para reservas
  - En `blueprints/inventario.py`: ídem para inventario (filtrar por bodega asociada a la sede activa)
  - Aplicar decorador `@sede_requerida` a todas las rutas de estos módulos
  - _Requisitos: 4.1, 4.2, 4.3_

  - [x] 8.1 Test de propiedad: filtrado de datos por sede activa
    - **Propiedad 10: Filtrado de datos por sede activa**
    - Para cualquier `sede_id` en sesión, todas las consultas de préstamos, reservas e inventario deben retornar únicamente registros cuyo `sede_id` coincida con el de la sesión
    - **Valida: Requisito 4.1**
    - `# Feature: sede-turno-selector, Property 10: Filtrado de datos por sede activa`

  - [ ] 8.2 Test de propiedad: nuevos registros heredan la sede activa
    - **Propiedad 11: Nuevos registros heredan la sede activa**
    - Para cualquier registro creado en préstamos, reservas o inventario mientras `session['sede_id']` está establecido, el `sede_id` del registro recién creado debe ser igual a `session['sede_id']`
    - **Valida: Requisito 4.2**
    - `# Feature: sede-turno-selector, Property 11: Nuevos registros heredan la sede activa`

- [x] 9. Agregar endpoints de gestión de sedes en `blueprints/admin.py`
  - `GET /admin/usuarios/<doc>/sedes`: lista sedes asignadas al auxiliar
  - `POST /admin/usuarios/<doc>/sedes`: asigna sede (body: `{sede_id}`); si ya existe, ignorar silenciosamente (HTTP 200)
  - `DELETE /admin/usuarios/<doc>/sedes/<sid>`: revoca sede
  - Registrar auditoría en `auditorias` para cada asignación y revocación
  - _Requisitos: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ] 9.1 Test de propiedad: asignación y revocación es un round-trip
    - **Propiedad 12: Asignación y revocación de sede es un round-trip**
    - Para cualquier par `(usuario_documento, sede_id)` válido, asignar y luego revocar debe resultar en que el registro no exista en `auxiliar_sedes`
    - **Valida: Requisitos 5.2, 5.3**
    - `# Feature: sede-turno-selector, Property 12: Asignación y revocación de sede es un round-trip`

  - [ ] 9.2 Test de propiedad: asignación duplicada es idempotente
    - **Propiedad 13: Asignación duplicada es idempotente**
    - Para cualquier par ya existente en `auxiliar_sedes`, intentar asignarlo nuevamente no debe cambiar el estado de la tabla ni generar un error visible
    - **Valida: Requisito 5.4**
    - `# Feature: sede-turno-selector, Property 13: Asignación duplicada es idempotente`

  - [ ] 9.3 Test de propiedad: auditoría de asignación y revocación
    - **Propiedad 14: Auditoría de asignación y revocación**
    - Para cualquier operación de asignación o revocación ejecutada por un administrador, debe existir al menos un registro en `auditorias` con el `usuario_documento` del administrador y la acción correspondiente
    - **Valida: Requisito 5.5**
    - `# Feature: sede-turno-selector, Property 14: Auditoría de asignación y revocación`

- [x] 10. Actualizar vista de detalle/edición de usuario en el panel de administración
  - Mostrar las sedes asignadas al auxiliar en la vista de edición
  - Agregar controles para asignar y revocar sedes usando los endpoints del paso 9
  - _Requisitos: 5.1_

- [x] 11. Checkpoint final — Asegurarse de que todos los tests pasen
  - Ejecutar la suite completa de tests. Consultar al usuario si surgen dudas.

## Notas

- Las tareas marcadas con `*` son opcionales y pueden omitirse para un MVP más rápido
- Cada tarea referencia requisitos específicos para trazabilidad
- Los tests de propiedad usan **Hypothesis** (`@settings(max_examples=100)`) con el comentario `# Feature: sede-turno-selector, Property N: <texto>`
- Los tests unitarios cubren casos concretos: login con 0/1/N sedes, 403 por sede no autorizada, cascade delete, preservación de sesión al cambiar sede
