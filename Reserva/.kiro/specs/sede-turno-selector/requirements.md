# Documento de Requisitos

## Introducción

Esta funcionalidad permite que un auxiliar seleccione la sede en la que va a trabajar durante su turno, inmediatamente después de autenticarse. Si el usuario tiene acceso a más de una sede, se le presenta una pantalla intermedia de selección antes de acceder al sistema. Si solo tiene una sede asignada, el acceso es directo. Además, el usuario puede cambiar de sede en cualquier momento durante la sesión activa desde el navbar, sin necesidad de cerrar sesión.

Para soportar múltiples sedes por usuario se introduce una tabla auxiliar `auxiliar_sedes` que relaciona un auxiliar con una o más sedes. Los roles `admin` y `superadmin` tienen acceso implícito a todas las sedes del sistema.

## Glosario

- **Sistema**: La aplicación Flask de gestión de préstamos, reservas e inventario.
- **Auxiliar**: Usuario registrado en la tabla `auxiliares` con rol `auxiliar`, `admin` o `superadmin`.
- **Sede**: Registro en la tabla `sedes` con un `id` y un `nombre` (ej: PERDOMO, ENGATIVA SEDE PRINCIPAL).
- **Sede_Activa**: La sede seleccionada por el Auxiliar para el turno actual, almacenada en `session['sede_id']`.
- **Selector_Sede**: Pantalla intermedia que se muestra después del login cuando el Auxiliar tiene acceso a más de una sede.
- **AuxiliarSedes**: Tabla de relación `auxiliar_sedes` que asocia un `usuario_documento` con uno o más `sede_id`.
- **Navbar**: Barra de navegación principal de la aplicación.
- **Módulo**: Cualquiera de los blueprints funcionales del sistema (préstamos, reservas, inventario, etc.).

---

## Requisitos

### Requisito 1: Tabla de relación auxiliar-sedes

**User Story:** Como administrador del sistema, quiero que cada auxiliar pueda tener asignadas múltiples sedes, para que el sistema pueda controlar a qué sedes tiene acceso cada usuario.

#### Criterios de Aceptación

1. THE Sistema SHALL mantener una tabla `auxiliar_sedes` con columnas `usuario_documento` (FK a `auxiliares.documento`) y `sede_id` (FK a `sedes.id`).
2. THE Sistema SHALL garantizar que la combinación `(usuario_documento, sede_id)` sea única en la tabla `auxiliar_sedes`.
3. WHEN se elimina un registro de `auxiliares`, THE Sistema SHALL eliminar en cascada los registros correspondientes en `auxiliar_sedes`.
4. THE Sistema SHALL mantener el campo `sede_id` existente en `auxiliares` como sede principal de referencia, sin eliminarlo.

---

### Requisito 2: Selección de sede después del login

**User Story:** Como auxiliar con acceso a múltiples sedes, quiero elegir en qué sede voy a trabajar al iniciar sesión, para que el sistema filtre los datos correctamente desde el inicio del turno.

#### Criterios de Aceptación

1. WHEN un Auxiliar se autentica correctamente y tiene acceso a más de una sede, THE Sistema SHALL redirigir al Auxiliar al Selector_Sede antes de acceder al dashboard principal.
2. WHEN un Auxiliar se autentica correctamente y tiene acceso a exactamente una sede, THE Sistema SHALL establecer esa sede como Sede_Activa y redirigir directamente al dashboard principal sin mostrar el Selector_Sede.
3. WHEN un Auxiliar con rol `admin` o `superadmin` se autentica, THE Sistema SHALL presentar el Selector_Sede con todas las sedes disponibles en el sistema.
4. THE Selector_Sede SHALL mostrar el nombre de cada sede disponible para el Auxiliar como opción seleccionable.
5. WHEN el Auxiliar selecciona una sede en el Selector_Sede, THE Sistema SHALL almacenar el `sede_id` seleccionado en `session['sede_id']` y redirigir al dashboard principal.
6. IF el Auxiliar intenta acceder a cualquier ruta protegida sin haber completado la selección de sede, THEN THE Sistema SHALL redirigir al Auxiliar al Selector_Sede.

---

### Requisito 3: Cambio de sede durante la sesión

**User Story:** Como auxiliar, quiero poder cambiar de sede durante mi turno sin cerrar sesión, para que pueda gestionar operaciones en otra sede sin interrumpir mi sesión activa.

#### Criterios de Aceptación

1. THE Navbar SHALL mostrar un control de cambio de sede cuando el Auxiliar tiene acceso a más de una sede o tiene rol `admin` o `superadmin`.
2. WHEN el Auxiliar selecciona una sede diferente desde el Navbar, THE Sistema SHALL actualizar `session['sede_id']` con el nuevo `sede_id` seleccionado.
3. WHEN el Auxiliar cambia de sede desde el Navbar, THE Sistema SHALL redirigir al Auxiliar al dashboard principal con la nueva Sede_Activa.
4. THE Navbar SHALL indicar visualmente cuál es la Sede_Activa actual del Auxiliar.
5. WHEN el Auxiliar con acceso a una sola sede visualiza el Navbar, THE Sistema SHALL mostrar el nombre de la sede sin ofrecer control de cambio.

---

### Requisito 4: Filtrado de datos por sede activa

**User Story:** Como auxiliar, quiero que todos los módulos del sistema muestren únicamente los datos de la sede en la que estoy trabajando, para evitar confusiones entre sedes.

#### Criterios de Aceptación

1. WHILE un Auxiliar tiene una Sede_Activa establecida en sesión, THE Sistema SHALL filtrar todos los registros de préstamos, reservas e inventario por el `sede_id` de la Sede_Activa.
2. WHEN un Auxiliar crea un nuevo registro en cualquier Módulo, THE Sistema SHALL asignar automáticamente el `sede_id` de la Sede_Activa al nuevo registro.
3. IF `session['sede_id']` es `None` al acceder a un Módulo, THEN THE Sistema SHALL redirigir al Auxiliar al Selector_Sede.

---

### Requisito 5: Gestión de sedes por usuario desde el panel de administración

**User Story:** Como administrador, quiero asignar y revocar el acceso de auxiliares a sedes desde el panel de administración, para controlar qué sedes puede gestionar cada usuario.

#### Criterios de Aceptación

1. THE Panel_Admin SHALL mostrar las sedes asignadas a cada Auxiliar en la vista de detalle o edición del usuario.
2. WHEN un administrador asigna una sede a un Auxiliar, THE Sistema SHALL insertar el registro correspondiente en `auxiliar_sedes`.
3. WHEN un administrador revoca el acceso de un Auxiliar a una sede, THE Sistema SHALL eliminar el registro correspondiente de `auxiliar_sedes`.
4. IF un administrador intenta asignar a un Auxiliar una sede que ya tiene asignada, THEN THE Sistema SHALL ignorar la operación sin generar un error visible al usuario.
5. THE Sistema SHALL registrar en `auditorias` cada asignación y revocación de sede a un Auxiliar, incluyendo el documento del administrador que realizó la acción.

---

### Requisito 6: Consistencia de la sesión al cambiar de sede

**User Story:** Como auxiliar, quiero que al cambiar de sede la sesión refleje correctamente el nuevo contexto, para que no se mezclen datos de sedes distintas.

#### Criterios de Aceptación

1. WHEN el Auxiliar cambia de Sede_Activa, THE Sistema SHALL actualizar únicamente `session['sede_id']` sin invalidar el resto de la sesión (usuario, rol, permisos).
2. THE Sistema SHALL validar que el `sede_id` recibido al seleccionar o cambiar sede pertenece a las sedes a las que el Auxiliar tiene acceso autorizado.
3. IF el `sede_id` recibido no pertenece a las sedes autorizadas del Auxiliar, THEN THE Sistema SHALL rechazar la solicitud y devolver un error HTTP 403.
